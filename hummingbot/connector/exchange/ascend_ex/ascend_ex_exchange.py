import asyncio
import json
import logging
import time
from collections import namedtuple
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS, ascend_ex_utils
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import AscendExAPIOrderBookDataSource
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book_tracker import AscendExOrderBookTracker
from hummingbot.connector.exchange.ascend_ex.ascend_ex_user_stream_tracker import AscendExUserStreamTracker
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import build_api_factory
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder, OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

ctce_logger = None
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal("0")

AscendExOrder = namedtuple(
    "AscendExOrder",
    "symbol price orderQty orderType avgPx cumFee cumFilledQty errorCode feeAsset lastExecTime orderId seqNum side status stopPrice execInst",
)
AscendExBalance = namedtuple("AscendExBalance", "asset availableBalance totalBalance")


class AscendExCommissionType(Enum):
    BASE = 0
    QUOTE = 1
    RECEIVED = 2


class AscendExTradingRule(TradingRule):
    def __init__(
            self,
            trading_pair: str,
            min_price_increment: Decimal,
            min_base_amount_increment: Decimal,
            min_notional_size: Decimal,
            max_notional_size: Decimal,
            commission_type: AscendExCommissionType,
            commission_reserve_rate: Decimal,
    ):
        super().__init__(
            trading_pair=trading_pair,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
            min_notional_size=min_notional_size,
        )
        self.max_notional_size = max_notional_size
        self.commission_type = commission_type
        self.commission_reserve_rate = commission_reserve_rate


class AscendExExchange(ExchangeBase):
    """
    AscendExExchange connects with AscendEx exchange and provides order book pricing, user account tracking and
    trading functionality.
    """

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 10.0

    STOP_TRACKING_ORDER_FAILURE_LIMIT = 3
    STOP_TRACKING_ORDER_NOT_FOUND_LIMIT = 3
    STOP_TRACKING_ORDER_ERROR_LIMIT = 5

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            ascend_ex_api_key: str,
            ascend_ex_secret_key: str,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
    ):
        """
        :param ascend_ex_api_key: The API key to connect to private AscendEx APIs.
        :param ascend_ex_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__(client_config_map=client_config_map)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._ascend_ex_auth = AscendExAuth(ascend_ex_api_key, ascend_ex_secret_key)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._api_factory = build_api_factory(throttler=self._throttler, auth=self._ascend_ex_auth)
        self._rest_assistant = None
        self._set_order_book_tracker(AscendExOrderBookTracker(
            api_factory=self._api_factory, throttler=self._throttler, trading_pairs=self._trading_pairs
        ))
        self._user_stream_tracker = AscendExUserStreamTracker(
            api_factory=self._api_factory,
            throttler=self._throttler,
            ascend_ex_auth=self._ascend_ex_auth,
            trading_pairs=self._trading_pairs,
        )
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._trading_rules = {}  # Dict[trading_pair:str, AscendExTradingRule]
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._account_group = None  # required in order to make post requests
        self._account_uid = None  # required in order to produce deterministic order ids
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        self._in_flight_order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)
        self._order_without_exchange_id_records = {}

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self.order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, AscendExTradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_order_tracker.active_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        return {
            "order_books_initialized": self.order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized": (
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True
            ),
            "account_data": self._account_group is not None and self._account_uid is not None,
        }

    @property
    def ready(self) -> bool:
        """
        :return True when all statuses pass, this might take 5-10 seconds for all the connector's components and
        services to be ready.
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order() for in_flight_order in self._in_flight_order_tracker.active_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        Returns a dictionary associating current active orders client id to their JSON representation
        """
        return {
            client_order_id: in_flight_order.to_json()
            for client_order_id, in_flight_order in self._in_flight_order_tracker.active_orders.items()
            if not in_flight_order.is_done
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_order_tracker.restore_tracking_states(tracking_states=saved_states)

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def start(self, clock: Clock, timestamp: float):
        """
        This function is called automatically by the clock.
        """
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        """
        This function is called automatically by the clock.
        """
        super().stop(clock)

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector. Those tasks include:
        - The order book tracker
        - The polling loop to update the trading rules
        - The polling loop to update order status and balance status using REST API (backup for main update process)
        - The background task to process the events received through the user stream tracker (websocket connection)
        """
        self.order_book_tracker.start()
        await self._update_account_data()

        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It perform a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        # Resets timestamps for status_polling_task
        self._last_poll_timestamp = 0
        self._last_timestamp = 0

        self.order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            # since there is no ping endpoint, the lowest rate call is to get BTC-USDT ticker
            await self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.TICKER_PATH_URL)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        """
        Used by quantize_order_price() in _create_order()
        Returns a price step, a minimum price increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param price: the starting point price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal):
        """
        Used by quantize_order_price() in _create_order()
        Returns an order amount step, a minimum amount increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param order_size: the starting point order price
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self.order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self.order_book_tracker.order_books[trading_pair]

    def buy(
            self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN,
            **kwargs
    ) -> str:
        """
        Buys an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=trading_pair, hbot_order_id_prefix=ascend_ex_utils.HBOT_BROKER_ID
        )
        safe_ensure_future(self._create_order(TradeType.BUY, client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

    def sell(
            self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN,
            **kwargs
    ) -> str:
        """
        Sells an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for SellOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to sell from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=trading_pair, hbot_order_id_prefix=ascend_ex_utils.HBOT_BROKER_ID
        )
        safe_ensure_future(self._create_order(TradeType.SELL, client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        To get the cancellation result, you'll have to wait for OrderCancelledEvent.
        :param trading_pair: The market (e.g. BTC-USDT) of the order.
        :param order_id: The internal order id (also called client_order_id)
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    def start_tracking_order(
            self,
            order_id: str,
            trading_pair: str,
            trade_type: TradeType,
            price: Decimal,
            amount: Decimal,
            order_type: OrderType,
            exchange_order_id: Optional[str] = None,
    ):
        """
        Starts tracking an order by adding it to the order tracker.

        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the exchange
        :param trading_pair: the token pair for the operation
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :param order_type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
        """
        self._in_flight_order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from InFlightOrderTracker.
        """
        self._in_flight_order_tracker.stop_tracking_order(client_order_id=order_id)

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        order_ids_to_cancel = []
        cancel_payloads = []
        successful_cancellations = []
        failed_cancellations = []

        for order in filter(lambda active_order: not active_order.is_done,
                            self._in_flight_order_tracker.active_orders.values()):
            if order.exchange_order_id is not None:
                cancel_payloads.append({
                    "id": ascend_ex_utils.uuid32(),
                    "orderId": order.exchange_order_id,
                    "symbol": await AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair(order.trading_pair,
                                                                                                      self._api_factory,
                                                                                                      self._throttler),
                    "time": int(time.time() * 1e3),
                })
                order_ids_to_cancel.append(order.client_order_id)
            else:
                failed_cancellations.append(CancellationResult(order.client_order_id, False))

        if cancel_payloads:
            try:
                api_params = {"orders": cancel_payloads}
                await self._api_request(
                    method=RESTMethod.DELETE,
                    path_url=CONSTANTS.ORDER_BATCH_PATH_URL,
                    data=api_params,
                    is_auth_required=True,
                    force_auth_path_url="order/batch",
                )

                successful_cancellations = [CancellationResult(order_id, True) for order_id in order_ids_to_cancel]

            except Exception:
                self.logger().network(
                    "Failed to cancel all orders.",
                    exc_info=True,
                    app_warning_msg="Failed to cancel all orders on AscendEx. Check API key and network connection.",
                )
        return successful_cancellations + failed_cancellations

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (
            self.SHORT_POLL_INTERVAL
            if now - self._user_stream_tracker.last_recv_time > 60.0
            else self.LONG_POLL_INTERVAL
        )
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(
            self,
            base_currency: str,
            quote_currency: str,
            order_type: OrderType,
            order_side: TradeType,
            amount: Decimal,
            price: Decimal = s_decimal_NaN,
            is_maker: Optional[bool] = None
    ) -> AddedToCostTradeFee:
        """
        Calculates the estimated fee an order would pay based on the connector configuration

        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :param is_maker: is it running as a market maker or as a market taker

        :return: the estimated fee for the order
        """
        trading_pair = f"{base_currency}-{quote_currency}"
        trading_rule = self._trading_rules[trading_pair]
        fee_percent = Decimal("0")
        if order_side == TradeType.BUY:
            if trading_rule.commission_type == AscendExCommissionType.QUOTE:
                fee_percent = trading_rule.commission_reserve_rate
        elif trading_rule.commission_type == AscendExCommissionType.BASE:
            fee_percent = trading_rule.commission_reserve_rate
        return AddedToCostTradeFee(percent=fee_percent)

    async def get_open_orders(self) -> List[OpenOrder]:
        """
        Obtains open orders from the ClientOrderTracker.

        :return: a list of active orders
        """
        result = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.ORDER_OPEN_PATH_URL,
            is_auth_required=True,
            force_auth_path_url="order/open",
        )
        ret_val = []
        for order in result["data"]:
            if order["orderType"].lower() != "limit":
                self.logger().debug(f"Unsupported orderType: {order['orderType']}. Order: {order}", exc_info=True)
                continue

            exchange_order_id = order["orderId"]
            client_order_id = None
            for in_flight_order in self._in_flight_order_tracker.active_orders.values():
                if in_flight_order.exchange_order_id == exchange_order_id:
                    client_order_id = in_flight_order.client_order_id

            if client_order_id is None:
                self.logger().debug(f"Unrecognized Order {exchange_order_id}: {order}")
                continue

            ret_val.append(
                OpenOrder(
                    client_order_id=client_order_id,
                    trading_pair=await AscendExAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(order["symbol"],
                                                                                                                 self._api_factory,
                                                                                                                 self._throttler),
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["orderQty"])),
                    executed_amount=Decimal(str(order["cumFilledQty"])),
                    status=order["status"],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["side"].lower() == "buy" else False,
                    time=int(order["lastExecTime"]),
                    exchange_order_id=exchange_order_id,
                )
            )
        return ret_val

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = s_decimal_0) -> Decimal:
        """
        Applies the trading rules to calculate the correct order amount for the market

        :param trading_pair: the token pair for which the order will be created
        :param amount: the intended amount for the order
        :param price: the intended price for the order

        :return: the quantized order amount after applying the trading rules
        """
        trading_rule: AscendExTradingRule = self._trading_rules[trading_pair]
        quantized_amount: Decimal = super().quantize_order_amount(trading_pair, amount)

        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        if price == s_decimal_0:
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        # Add 1% as a safety factor in case the prices changed while making the order.
        if (
                notional_size < trading_rule.min_notional_size * Decimal("1.01")
                or notional_size > trading_rule.max_notional_size
        ):
            return s_decimal_0

        return quantized_amount

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.TICKER_PATH_URL)
        return pairs_prices

    async def _process_order_message(self, order_msg: AscendExOrder):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        tracked_order = self._in_flight_order_tracker.fetch_order(exchange_order_id=order_msg.orderId)

        if tracked_order is not None:
            order_status = CONSTANTS.ORDER_STATE[order_msg.status]
            cumulative_filled_amount = Decimal(order_msg.cumFilledQty)
            if (order_status in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]
                    and cumulative_filled_amount > tracked_order.executed_amount_base):
                filled_amount = cumulative_filled_amount - tracked_order.executed_amount_base
                cumulative_fee = Decimal(order_msg.cumFee)
                fee_already_paid = tracked_order.cumulative_fee_paid(token=order_msg.feeAsset, exchange=self)
                if cumulative_fee > fee_already_paid:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        percent_token=order_msg.feeAsset,
                        flat_fees=[TokenAmount(amount=cumulative_fee - fee_already_paid, token=order_msg.feeAsset)]
                    )
                else:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type)
                trade_update = TradeUpdate(
                    trade_id=str(order_msg.lastExecTime),
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    fee=fee,
                    fill_base_amount=filled_amount,
                    fill_quote_amount=filled_amount * Decimal(order_msg.avgPx),
                    fill_price=Decimal(order_msg.avgPx),
                    fill_timestamp=int(order_msg.lastExecTime),
                )
                self._in_flight_order_tracker.process_trade_update(trade_update)

            order_update = OrderUpdate(
                exchange_order_id=order_msg.orderId,
                trading_pair=await AscendExAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(order_msg.symbol,
                                                                                                             self._api_factory,
                                                                                                             self._throttler),
                update_timestamp=order_msg.lastExecTime * 1e-3,
                new_state=order_status,
            )

            self._in_flight_order_tracker.process_order_update(order_update=order_update)

    def _process_balances(self, balances: List[AscendExBalance], is_complete_list: bool = True):
        """
        Updates account balances and available account balances from data obtained from the exchange

        :param balances: A list of balances
        :param is_complete_list: Indicates whether the provided list is a complete list of assets of the account and
        therefore if asset elements in the local account balances and available account balances can be mirrored
        according to it
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        for balance in balances:
            asset_name = balance.asset
            self._account_available_balances[asset_name] = Decimal(balance.availableBalance)
            self._account_balances[asset_name] = Decimal(balance.totalBalance)
            remote_asset_names.add(asset_name)
        if not is_complete_list:
            return
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        """
        Listens to messages in _user_stream_tracker.user_stream queue.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from AscendEx. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to messages in _user_stream_tracker.user_stream queue. The messages are put in by
        AscendExAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if event_message.get("m") == "order":
                    order_data = event_message.get("data")
                    trading_pair = order_data["s"]
                    base_asset, quote_asset = tuple(asset for asset in trading_pair.split("/"))
                    await self._process_order_message(
                        AscendExOrder(
                            trading_pair,
                            order_data["p"],
                            order_data["q"],
                            order_data["ot"],
                            order_data["ap"],
                            order_data["cf"],
                            order_data["cfq"],
                            order_data["err"],
                            order_data["fa"],
                            int(order_data["t"]) * 1e-3,
                            order_data["orderId"],
                            order_data["sn"],
                            order_data["sd"],
                            order_data["st"],
                            order_data["sp"],
                            order_data["ei"],
                        )
                    )
                    # Handles balance updates from orders.
                    base_asset_balance = AscendExBalance(base_asset, order_data["bab"], order_data["btb"])
                    quote_asset_balance = AscendExBalance(quote_asset, order_data["qab"], order_data["qtb"])
                    self._process_balances([base_asset_balance, quote_asset_balance], False)
                elif event_message.get("m") == "balance":
                    # Handles balance updates from Deposits/Withdrawals, Transfers between Cash and Margin Accounts
                    balance_data = event_message.get("data")
                    balance = AscendExBalance(balance_data["a"], balance_data["ab"], balance_data["tb"])
                    self._process_balances([balance], False)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param trading_pair: The market trading pair
        :param order_id: The internal order id
        """
        try:
            tracked_order = self._in_flight_order_tracker.fetch_tracked_order(order_id)
            if tracked_order is None:
                non_tracked_order = self._in_flight_order_tracker.fetch_cached_order(order_id)
                if non_tracked_order is None:
                    raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
                else:
                    self.logger().info(f"The order {order_id} was finished before being canceled")
            else:
                ex_order_id = await tracked_order.get_exchange_order_id()

                api_params = {
                    "symbol": await AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair,
                                                                                                      self._api_factory,
                                                                                                      self._throttler),
                    "orderId": ex_order_id,
                    "time": ascend_ex_utils.get_ms_timestamp(),
                }
                await self._api_request(
                    method=RESTMethod.DELETE,
                    path_url=CONSTANTS.ORDER_PATH_URL,
                    data=api_params,
                    is_auth_required=True,
                    force_auth_path_url="order",
                )

            return order_id
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self._stop_tracking_order_exceed_no_exchange_id_limit(tracked_order=tracked_order)
        except Exception as e:
            self.logger().error(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
            )

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg="Could not fetch account updates from AscendEx. "
                                    "Check API key and network connection.",
                )
                await self._sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        response = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.BALANCE_PATH_URL,
            is_auth_required=True,
            force_auth_path_url="balance"
        )
        balances = list(
            map(
                lambda balance: AscendExBalance(balance["asset"], balance["availableBalance"], balance["totalBalance"]),
                response.get("data", list()),
            )
        )
        self._process_balances(balances)

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """

        if len(self._in_flight_order_tracker.active_orders) == 0:
            return

        tracked_orders: List[InFlightOrder] = list(self._in_flight_order_tracker.active_orders.values())

        ex_oid_to_c_oid_map: Dict[str, str] = {}
        # Check a second time the order is not done because it can be updated in other async process
        for order in (tracked_order for tracked_order in tracked_orders if not tracked_order.is_done):
            try:
                exchange_id = await order.get_exchange_order_id()
                ex_oid_to_c_oid_map[exchange_id] = order.client_order_id
            except asyncio.TimeoutError:
                self.logger().debug(
                    f"Tracked order {order.client_order_id} does not have an exchange id. "
                    f"Attempting fetch in next polling interval."
                )
                self._stop_tracking_order_exceed_no_exchange_id_limit(tracked_order=order)
                continue

        if ex_oid_to_c_oid_map:
            exchange_order_ids_param_str: str = ",".join(list(ex_oid_to_c_oid_map.keys()))
            params = {"orderId": exchange_order_ids_param_str}
            try:
                resp = await self._api_request(
                    method=RESTMethod.GET,
                    path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
                    params=params,
                    is_auth_required=True,
                    force_auth_path_url="order/status",
                )
            except Exception:
                self.logger().exception(
                    f"There was an error requesting updates for the active orders ({ex_oid_to_c_oid_map})")
                raise
            self.logger().debug(f"Polling for order status updates of {len(ex_oid_to_c_oid_map)} orders.")
            self.logger().debug(f"cash/order/status?orderId={exchange_order_ids_param_str} response: {resp}")
            # The data returned from this end point can be either a list or a dict depending on number of orders
            resp_records: List = []
            if isinstance(resp["data"], dict):
                resp_records.append(resp["data"])
            elif isinstance(resp["data"], list):
                resp_records = resp["data"]

            order_updates: List[OrderUpdate] = []
            try:
                for order_data in resp_records:
                    exchange_order_id = order_data["orderId"]
                    client_order_id = ex_oid_to_c_oid_map[exchange_order_id]
                    new_state: OrderState = CONSTANTS.ORDER_STATE[order_data["status"]]
                    order_updates.append(
                        OrderUpdate(
                            client_order_id=client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=await AscendExAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(order_data["symbol"],
                                                                                                                         self._api_factory,
                                                                                                                         self._throttler),
                            update_timestamp=order_data["lastExecTime"] * 1e-3,
                            new_state=new_state,
                        )
                    )
                for update in order_updates:
                    self._in_flight_order_tracker.process_order_update(update)

            except Exception:
                self.logger().info(
                    f"Unexpected error during processing order status. The Ascend Ex Response: {resp}", exc_info=True
                )

    def _update_order_after_failure(self, order_id: str, trading_pair: str):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order_id,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FAILED,
        )
        self._in_flight_order_tracker.process_order_update(order_update)

    def _stop_tracking_order_exceed_no_exchange_id_limit(self, tracked_order: InFlightOrder):
        """
        Increments and checks if the tracked order has exceed the STOP_TRACKING_ORDER_NOT_FOUND_LIMIT limit.
        If true, Triggers a MarketOrderFailureEvent and stops tracking the order.
        """
        client_order_id = tracked_order.client_order_id
        self._order_without_exchange_id_records[client_order_id] = (
            self._order_without_exchange_id_records.get(client_order_id, 0) + 1)
        if self._order_without_exchange_id_records[client_order_id] >= self.STOP_TRACKING_ORDER_NOT_FOUND_LIMIT:
            # Wait until the absence of exchange id has repeated a few times before actually treating it as failed.
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                client_order_id=tracked_order.client_order_id,
                update_timestamp=time.time(),
                new_state=OrderState.FAILED,
            )
            self._in_flight_order_tracker.process_order_update(order_update)
            del self._order_without_exchange_id_records[client_order_id]

    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            price: Decimal,
    ):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (aka client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type
        :param price: The order price
        """
        # For MarketEvents to be emitted, the order needs to be already tracked
        self.start_tracking_order(
            order_id=order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type,
        )

        trading_rule = self._trading_rules[trading_pair]

        if not order_type.is_limit_type():
            self._update_order_after_failure(order_id, trading_pair)
            raise Exception(f"Unsupported order type: {order_type}")
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        side = "Buy" if trade_type == TradeType.BUY else "Sell"
        if amount < trading_rule.min_order_size:
            self._update_order_after_failure(order_id, trading_pair)
            self.logger().error(
                f"{side} order amount {amount} is lower than the minimum order size "
                f"{trading_rule.min_order_size}.")
            return
        try:
            timestamp = ascend_ex_utils.get_ms_timestamp()
            # Order UUID is strictly used to enable AscendEx to construct a unique(still questionable) exchange_order_id
            order_uuid = f"{ascend_ex_utils.HBOT_BROKER_ID}-{ascend_ex_utils.uuid32()}"[:32]
            api_params = {
                "id": order_uuid,
                "time": timestamp,
                "symbol": await AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair,
                                                                                                  self._api_factory,
                                                                                                  self._throttler),
                "orderPrice": f"{price:f}",
                "orderQty": f"{amount:f}",
                "orderType": "limit",
                "side": side.lower(),
                "respInst": "ACCEPT",
            }

            try:
                resp = await self._api_request(
                    method=RESTMethod.POST,
                    path_url=CONSTANTS.ORDER_PATH_URL,
                    data=api_params,
                    is_auth_required=True,
                    force_auth_path_url="order",
                )

                resp_status = resp["data"]["status"].upper()

                order_data = resp["data"]["info"]
                if resp_status == "ACK":
                    # Ack request status means the server has received the request
                    return

                order_update = None
                if resp_status == "ACCEPT":
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        exchange_order_id=str(order_data["orderId"]),
                        trading_pair=trading_pair,
                        update_timestamp=order_data["lastExecTime"] * 1e-3,
                        new_state=OrderState.OPEN,
                    )
                elif resp_status == "DONE":
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        exchange_order_id=str(order_data["orderId"]),
                        trading_pair=trading_pair,
                        update_timestamp=order_data["lastExecTime"] * 1e-3,
                        new_state=CONSTANTS.ORDER_STATE[order_data["status"]],
                    )
                elif resp_status == "ERR":
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.FAILED,
                    )
                self._in_flight_order_tracker.process_order_update(order_update)
            except IOError:
                self.logger().exception(f"The request to create the order {order_id} failed")
                self._update_order_after_failure(order_id, trading_pair)
        except asyncio.CancelledError:
            self._update_order_after_failure(order_id, trading_pair)
            raise
        except Exception:
            msg = (f"Error submitting {trade_type.name} {order_type.name} order to AscendEx for "
                   f"{amount} {trading_pair} {price}.")
            self.logger().exception(msg)
            self._update_order_after_failure(order_id, trading_pair)

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rule.
        """
        while True:
            try:
                await self._update_trading_rules()
                await self._sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    f"Unexpected error while fetching trading rules. Error: {str(e)}",
                    exc_info=True,
                    app_warning_msg="Could not fetch new trading rules from AscendEx. " "Check network connection.",
                )
                await self._sleep(0.5)

    async def _update_trading_rules(self):
        """
        Updates local trading rules from rules obtained from the exchange
        """
        instruments_info = await self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.PRODUCTS_PATH_URL)
        self._trading_rules.clear()
        self._trading_rules = await self._format_trading_rules(instruments_info)

    async def _format_trading_rules(self, instruments_info: Dict[str, Any]) -> Dict[str, AscendExTradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "code": 0,
            "data": [
                {
                    "symbol":                "BTMX/USDT",
                    "baseAsset":             "BTMX",
                    "quoteAsset":            "USDT",
                    "status":                "Normal",
                    "minNotional":           "5",
                    "maxNotional":           "100000",
                    "marginTradable":         true,
                    "commissionType":        "Quote",
                    "commissionReserveRate": "0.001",
                    "tickSize":              "0.000001",
                    "lotSize":               "0.001"
                }
            ]
        }
        """
        trading_rules = {}
        for rule in instruments_info["data"]:
            try:
                trading_pair = await AscendExAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(rule["symbol"],
                                                                                                               self._api_factory,
                                                                                                               self._throttler)
                trading_rules[trading_pair] = AscendExTradingRule(
                    trading_pair,
                    min_price_increment=Decimal(rule["tickSize"]),
                    min_base_amount_increment=Decimal(rule["lotSize"]),
                    min_notional_size=Decimal(rule["minNotional"]),
                    max_notional_size=Decimal(rule["maxNotional"]),
                    commission_type=AscendExCommissionType[rule["commissionType"].upper()],
                    commission_reserve_rate=Decimal(rule["commissionReserveRate"]),
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return trading_rules

    async def _update_account_data(self):
        """
        Updates account group and uid from data obtained from the exchange
        """
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}"

        rest_assistant = await self._get_rest_assistant()

        request = RESTRequest(method=RESTMethod.GET,
                              url=url,
                              endpoint_url=CONSTANTS.INFO_PATH_URL,
                              is_auth_required=True)

        async with self._throttler.execute_task(CONSTANTS.INFO_PATH_URL):
            response = await rest_assistant.call(request)

            try:
                parsed_response = await response.json()
            except Exception as e:
                raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
            if response.status != 200:
                raise IOError(
                    f"Error fetching data from {url}. HTTP status is {response.status}. " f"Message: {parsed_response}"
                )
            if parsed_response["code"] != 0:
                raise IOError(f"{url} API call failed, response: {parsed_response}")

            self._account_group = parsed_response["data"]["accountGroup"]
            self._account_uid = parsed_response["data"]["userUID"]

    async def _api_request(
            self,
            method: RESTMethod,
            path_url: str,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            is_auth_required: bool = False,
            force_auth_path_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """

        data = json.dumps(data)

        if is_auth_required:
            if self._account_group is None:
                await self._update_account_data()

            url = f"{ascend_ex_utils.get_rest_url_private(self._account_group)}/{path_url}"
            path_url_auth = path_url if force_auth_path_url is None else force_auth_path_url
        else:
            url = f"{CONSTANTS.REST_URL}/{path_url}"

        rest_assistant = await self._get_rest_assistant()

        request = RESTRequest(method=method,
                              url=url,
                              endpoint_url=path_url_auth if is_auth_required else path_url,
                              data=data,
                              params=params,
                              is_auth_required=is_auth_required)

        async with self._throttler.execute_task(path_url):
            response = await rest_assistant.call(request)

            if response.status != 200:
                data = await response.text()
                raise IOError(f"Error calling {url}. HTTP status is {response.status}. " f"Message: {data}")
            try:
                parsed_response = await response.json()
            except Exception as e:
                raise IOError(f"Error calling {url}. Error: {str(e)}")

            if parsed_response["code"] != 0:
                raise IOError(f"{url} API call failed, response: {parsed_response}")

        return parsed_response

    async def all_trading_pairs(self) -> List[str]:
        # This method should be removed and instead we should implement _initialize_trading_pair_symbol_map
        return await AscendExAPIOrderBookDataSource.fetch_trading_pairs()

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await AscendExAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=trading_pairs,
            api_factory=self._api_factory,
            throttler=self._throttler
        )

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)
