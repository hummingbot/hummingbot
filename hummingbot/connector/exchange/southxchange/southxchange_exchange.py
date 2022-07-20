import asyncio
import json
import logging
import time
from collections import namedtuple
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.southxchange import southxchange_constants as CONSTANTS, southxchange_utils
from hummingbot.connector.exchange.southxchange.southxchange_api_order_book_data_source import SouthxchangeAPIOrderBookDataSource
from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth
from hummingbot.connector.exchange.southxchange.southxchange_order_book_tracker import SouthxchangeOrderBookTracker
from hummingbot.connector.exchange.southxchange.southxchange_user_stream_tracker import SouthxchangeUserStreamTracker
from hummingbot.connector.exchange.southxchange.southxchange_utils import build_api_factory, convert_string_to_datetime
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
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.connector.exchange.southxchange.southxchange_web_utils import RESTAssistant_SX
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.southxchange.southxchange_constants import REST_URL

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

ctce_logger = None
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal("0")

SouthxchangeOrder = namedtuple("SouthxchangeOrder", "orderId orderMarketId orderTime orderCurrencyGet orderCurrencyGive orderAmount orderOriginalAmount orderPrice orderType status")
SouthxchangeBalance = namedtuple("SouthxchangeBalance", "Currency Deposited Available Unconfirmed")


class SouthXchangeTradingRule(TradingRule):
    def __init__(self,
                 trading_pair: str,
                 min_price_increment: Decimal,
                 min_base_amount_increment: Decimal):
        super().__init__(trading_pair=trading_pair,
                         min_price_increment=min_price_increment,
                         min_base_amount_increment=min_base_amount_increment)


class SouthxchangeExchange(ExchangeBase):
    """
    SouthxchangeExchange connects with SouthxchangeExchange exchange and provides order book pricing, user account tracking and
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
            southxchange_api_key: str,
            southxchange_secret_key: str,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
    ):
        """
        :param southxchange_api_key: The API key to connect to private southxchangeEx APIs.
        :param southxchange_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__(client_config_map=client_config_map)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._time_synchronizer = TimeSynchronizer()
        self._southxchange_auth = SouthXchangeAuth(southxchange_api_key, southxchange_secret_key, self._time_synchronizer)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._api_factory = build_api_factory(throttler=self._throttler, auth=self._southxchange_auth)
        self._rest_assistant = None
        self._set_order_book_tracker(SouthxchangeOrderBookTracker(
            api_factory=self._api_factory, throttler=self._throttler, trading_pairs=self._trading_pairs, connector=self
        ))
        self._user_stream_tracker = SouthxchangeUserStreamTracker(
            connector=self,
            api_factory=self._api_factory,
            throttler=self._throttler,
            southxchange_auth=self._southxchange_auth,
            trading_pairs=self._trading_pairs,
        )
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._trading_rules = {}
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._trader_level = None
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        self._in_flight_order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)
        self._order_without_exchange_id_records = {}
        self._lock = asyncio.Lock()
        self._lockPlaceOrder = asyncio.Lock()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self.order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, SouthXchangeTradingRule]:
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
            "account_data": self._trader_level is not None
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
        This function is required by NetworkIterator base class and is called automatically.
        It starts tracking order book, polling trading rules,
        updating statuses and tracking user data.
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
        This function is required by NetworkIterator base class and is called automatically.
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
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            # since there is no ping endpoint, the lowest rate call is to get BTC-USDT ticker
            await self._api_request(method=RESTMethod.GET, path_url="markets")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _update_account_data(self):
        """
        Modify - SouthXchange
        """
        try:
            response = await self._api_request(
                method=RESTMethod.POST,
                path_url="getUserInfo",
                is_auth_required=True
            )
            if response is not None:
                self._trader_level = "ok"
        except Exception:
            raise IOError("Error parsing data from getUserInfo.")

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
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from SouthxchangeExchange. "
                                                      "Check network connection.")
                await self._sleep(0.5)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        """
        Returns a price step, a minimum price increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal):
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
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
            is_buy=True, trading_pair=trading_pair, hbot_order_id_prefix=southxchange_utils.HBOT_BROKER_ID
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
            is_buy=False, trading_pair=trading_pair, hbot_order_id_prefix=southxchange_utils.HBOT_BROKER_ID
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

    def start_tracking_order(self,
                             order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
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
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        self._in_flight_order_tracker.stop_tracking_order(client_order_id=order_id)

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        successful_cancellations = []
        failed_cancellations = []
        open_orders = [o for o in self._in_flight_order_tracker.active_orders.values() if not o.is_done]
        if len(open_orders) == 0:
            return []
        for order in open_orders:
            if order.exchange_order_id is None:
                failed_cancellations.append(CancellationResult(order.client_order_id, False))
                continue
            try:
                ex_order_id = order.exchange_order_id
                api_params = {
                    "orderCode": ex_order_id,
                }
                await self._api_request(
                    method=RESTMethod.POST,
                    path_url="cancelOrder",
                    params=api_params,
                    is_auth_required=True,
                    force_auth_path_url="order"
                )
                successful_cancellations.append(CancellationResult(order.client_order_id, True))
            except Exception:
                failed_cancellations.append(CancellationResult(order.client_order_id, False))
                self.logger().network(
                    "Unexpected error cancelling orders.",
                    exc_info=True,
                    app_warning_msg = "Failed to cancel all orders on SouthXchange. Check API key and network connection."
                )
        return successful_cancellations + failed_cancellations

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def get_open_orders(self) -> List[OpenOrder]:
        result = await self._api_request(
            method=RESTMethod.POST,
            path_url="listOrders",
            is_auth_required=True,
        )
        ret_val = []
        for order in result:
            exchange_order_id = order["Code"]
            client_order_id = None
            for in_flight_order in self._in_flight_order_tracker.fetch_order.values():
                if in_flight_order.exchange_order_id == exchange_order_id:
                    client_order_id = in_flight_order.client_order_id
            if client_order_id is None:
                self.logger().debug(f"Unrecognized Order {exchange_order_id}: {order}")
                continue
            ret_val.append(
                OpenOrder(
                    client_order_id=client_order_id,
                    trading_pair= order["ListingCurrency"] + "-" + order["ListingCurrency"],
                    price=Decimal(str(order["LimitPrice"])),
                    amount=Decimal(str(order["OriginalAmount"])),
                    executed_amount=Decimal(str(order["OriginalAmount"])) - Decimal(str(order["Amount"])),
                    status="Pending",
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["Type"].lower() == "buy" else False,
                    time = int(TimeSynchronizer.time() * 1e3),
                    exchange_order_id=exchange_order_id
                )
            )
        return ret_val

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
        with await self._lock:
            data = json.dumps(data)
            url = None
            url = f"{REST_URL}{path_url}"
            try:
                rest_assistant = await self._get_rest_assistant()
                data = await rest_assistant.execute_request(
                    url=url,
                    method=method,
                    throttler_limit_id="SXC",
                    is_auth_required=is_auth_required,
                    params=params
                )
                return data
            except Exception as exception:
                raise IOError(f"Error calling {url}. Error: {exception}")

    def quantize_order_amount(self, trading_pair: str, amount: Decimal = s_decimal_0) -> Decimal:
        quantized_amount: Decimal = super().quantize_order_amount(trading_pair, amount)
        trading_rule: SouthXchangeTradingRule = self._trading_rules[trading_pair]
        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount

    def _process_balances(self, balances: List[SouthxchangeBalance], is_complete_list: bool = True):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        for balance in balances:
            asset_name = balance.Currency
            self._account_available_balances[asset_name] = Decimal(balance.Available)
            self._account_balances[asset_name] = Decimal(balance.Deposited)
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _process_order_message(self, order_msg: SouthxchangeOrder):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        tracked_order = self._in_flight_order_tracker.fetch_order(exchange_order_id=order_msg.orderId)
        if tracked_order is None:
            return
        order_status = CONSTANTS.ORDER_STATE[order_msg.status]
        order_update = OrderUpdate(
            exchange_order_id=order_msg.orderId,
            trading_pair=tracked_order.trading_pair,
            update_timestamp= convert_string_to_datetime(order_msg.orderTime).timestamp() * 1e-3,
            new_state=order_status,
        )
        self._in_flight_order_tracker.process_order_update(order_update=order_update)

    async def _process_trade_message(self, order_msg: SouthxchangeOrder):
        exchange_order_id = order_msg.orderId
        tracked_order = self._in_flight_order_tracker.fetch_order(exchange_order_id=order_msg.orderId)
        if tracked_order is None:
            return
        order_status = CONSTANTS.ORDER_STATE[order_msg.status]
        trasanctionsOrder: Dict[any, any]
        params = {
            "transactionType": "tradesbyordercode",
            "optionalFilter": int(exchange_order_id),
            "pageSize": 50,
        }
        trasanctionsOrder = await self._api_request(
            method=RESTMethod.POST,
            path_url="listTransactions",
            params=params,
            is_auth_required=True)
        acumalatesFee = Decimal("0.000000000000")
        feeAsset: str = ""
        for transOrder in trasanctionsOrder.get('Result'):
            if(transOrder["Type"] == "tradefee"):
                acumalatesFee = acumalatesFee + Decimal(str(transOrder["Amount"] * (-1)))
                feeAsset = transOrder["CurrencyCode"]

        cumFilledQty = Decimal("0.00000000000000000")
        cumFilledQty = Decimal(str(order_msg.orderOriginalAmount)) - Decimal(str(order_msg.orderAmount))
        if (order_status in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]
                and ((cumFilledQty > tracked_order.executed_amount_base) or (cumFilledQty == Decimal("0")))):
            filled_amount = (cumFilledQty - tracked_order.executed_amount_base) if cumFilledQty != Decimal("0") else (tracked_order.amount - tracked_order.executed_amount_base)
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=tracked_order.trade_type,
                percent_token=feeAsset,
                flat_fees=[TokenAmount(amount=acumalatesFee, token=feeAsset)]
            )
            trade_update = TradeUpdate(
                trade_id=str(int(self.current_timestamp * 1e6)),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                fee=fee,
                fill_base_amount=filled_amount,
                fill_quote_amount= filled_amount * Decimal(str(order_msg.orderPrice)),
                fill_price= Decimal(str(order_msg.orderPrice)),
                fill_timestamp=float(self.current_timestamp * 1e6),
            )
            self._in_flight_order_tracker.process_trade_update(trade_update)

        order_update = OrderUpdate(
            exchange_order_id=order_msg.orderId,
            trading_pair= f"{tracked_order.base_asset}-{tracked_order.quote_asset}",
            update_timestamp=float(self.current_timestamp * 1e-3),
            new_state=order_status,
        )
        self._in_flight_order_tracker.process_order_update(order_update=order_update)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from SouthxchangeExchange. Check API key and network connection."
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        SouthxchangeAPIUserStreamDataSource
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if event_message.get("k") == "order":
                    list_orders_to_process = event_message.get("v")
                    for order_data in list_orders_to_process:
                        params = {
                            "code": order_data["c"],
                        }
                        order = await self._api_request(
                            method=RESTMethod.POST,
                            path_url="getOrder",
                            params=params,
                            is_auth_required=True)
                        order_process = SouthxchangeOrder(
                            str(order_data["c"]),
                            order_data["m"],
                            order["DateAdded"],
                            order_data["get"],
                            order_data["giv"],
                            str(order_data["a"]),
                            str(order_data["oa"]),
                            str(order_data["p"]),
                            order["Type"],
                            order["Status"]
                        )
                        if order["Status"] in {"executed", "partiallyexecuted", "partiallyexecutedbutnotenoughbalance"}:
                            await self._process_trade_message(order_process)
                        else:
                            await self._process_order_message(order_process)
                elif event_message.get("k") == "balance":
                    await self._update_balances()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(15.0)

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param trading_pair: The market trading pair
        :param order_id: The internal order id
        order.last_state to change to CANCELED
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
                # ex_order_id = tracked_order.exchange_order_id
                api_params = {
                    "orderCode": ex_order_id,
                }
                await self._api_request(
                    method=RESTMethod.POST,
                    path_url="cancelOrder",
                    params=api_params,
                    is_auth_required=True,
                    force_auth_path_url="order"
                )
            return order_id
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self._stop_tracking_order_exceed_no_exchange_id_limit(tracked_order=tracked_order)
        except Exception as e:
            self.logger().error(
                f"{str(e)}",
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
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from SouthxchangeExchange. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _update_balances(self):
        """
        Modify - SouthXchange
        Calls REST API to update total and available balances.
        """
        response = await self._api_request(
            method=RESTMethod.POST,
            path_url="listBalances",
            is_auth_required=True)
        balances = list(map(
            lambda balance: SouthxchangeBalance(
                balance["Currency"],
                balance["Deposited"],
                balance["Available"],
                balance["Unconfirmed"]
            ),
            response
        ))
        self._process_balances(balances)

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        if len(self._in_flight_order_tracker.active_orders) == 0:
            return

        tracked_orders: List[InFlightOrder] = list(self._in_flight_order_tracker.active_orders.values())

        ex_oid_to_c_oid_map: Dict[str, str] = {}
        for order in (tracked_order for tracked_order in tracked_orders if not tracked_order.is_done):
            try:
                exchange_id = await order.get_exchange_order_id()
                ex_oid_to_c_oid_map[exchange_id] = order.client_order_id
                if exchange_id is None or exchange_id == '':
                    raise Exception
                api_params = {
                    "code": exchange_id,
                }
                try:
                    response = await self._api_request(
                        method=RESTMethod.POST,
                        path_url="getOrder",
                        params=api_params,
                        is_auth_required=True)
                except Exception:
                    self.logger().exception(
                        f"There was an error requesting updates for the active orders ({ex_oid_to_c_oid_map})")
                    raise
                self.logger().debug(f"Polling for order status updates of {len(ex_oid_to_c_oid_map)} orders.")
                self.logger().debug(f"getOrder: code={exchange_id} response: {response}")

                try:
                    # for response in responses:
                    if isinstance(response, Exception):
                        raise response
                    if response is None:
                        self.logger().info(f"_update_order_status result not in resp: {response}")
                        continue
                    order_process = SouthxchangeOrder(
                        str(response["Code"]),
                        0,
                        response["DateAdded"],
                        response["ListingCurrency"],
                        response["ReferenceCurrency"],
                        str(response["Amount"]),
                        0,
                        str(response["LimitPrice"]),
                        response["Type"],
                        response["Status"]
                    )
                    await self._process_order_message(order_process)
                except Exception:
                    self.logger().info(
                        f"Unexpected error during processing order status. The Ascend Ex Response: {response}", exc_info=True
                    )
            except asyncio.TimeoutError:
                self.logger().debug(
                    f"Tracked order {order.client_order_id} does not have an exchange id. "
                    f"Attempting fetch in next polling interval."
                )
                self._stop_tracking_order_exceed_no_exchange_id_limit(tracked_order=order)
                continue

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

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Decimal):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (aka client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type
        :param price: The order price
        """
        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        if amount <= s_decimal_0:
            raise ValueError("Order amount must be greater than zero.")
        # TODO: check balance
        try:
            pair_currencies = trading_pair.split("-")
            api_params = {
                "listingCurrency": pair_currencies[0],
                "referenceCurrency": pair_currencies[1],
                "amount": f"{amount:f}",
                "limitPrice": f"{price:f}",
                "type": trade_type.name
            }
            self.start_tracking_order(
                order_id=order_id,
                trading_pair=trading_pair,
                trade_type=trade_type,
                price=price,
                amount=amount,
                order_type=order_type
            )
            try:
                async with self._lockPlaceOrder:
                    order_result = await self._api_request(
                        method=RESTMethod.POST,
                        path_url="placeOrder",
                        params=api_params,
                        is_auth_required=True,
                        force_auth_path_url="order"
                    )
                    api_params = {
                        "code": order_result,
                    }
                    order = await self._api_request(
                        method=RESTMethod.POST,
                        path_url="getOrder",
                        params=api_params,
                        is_auth_required=True
                    )
                    if(order["Status"] != 'booked'):
                        await self._sleep(1)
                if order_result is not None:
                    tracked_order = self._in_flight_order_tracker.fetch_order(client_order_id=order_id)
                    order_update = None
                    if tracked_order is not None:
                        order_update: OrderUpdate = OrderUpdate(
                            client_order_id=order_id,
                            exchange_order_id=order_result,
                            trading_pair=trading_pair,
                            update_timestamp=self.current_timestamp,
                            new_state=OrderState.OPEN,
                        )
                        self._in_flight_order_tracker.process_order_update(order_update)
            except IOError:
                self.logger().exception(f"The request to create the order {order_id} failed")
                self.stop_tracking_order(order_id)
                order_update = OrderUpdate(
                    client_order_id=order_id,
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.FAILED,
                )
                self._in_flight_order_tracker.process_order_update(order_update)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(
                f"Error submitting {trade_type.name} {order_type.name} order to SouthXchange for "
                f"{amount} {trading_pair} "
                f"{price}."
            )

    async def _update_trading_rules(self):
        """
        Modify - SouthXchange
        """
        list_fees = await self._api_request(
            method=RESTMethod.GET,
            path_url="fees")
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(list_fees.get("Currencies"), list_fees.get("Markets"))

    def _format_trading_rules(self, currencies: Dict[str, Any], markets: Dict[str, Any]) -> Dict[str, SouthXchangeTradingRule]:
        """
        Modify - SouthXchange
        Converts json API response into a dictionary of trading rules.
        """
        trading_rules = {}
        for m in markets:
            trading_pair = m['ListingCurrencyCode'] + "-" + m['ReferenceCurrencyCode']
            precision_rule = ""
            for c in currencies:
                if(c['Code'] == m['ListingCurrencyCode']):
                    precision_rule = format(c['MinAmount'], f".{c['Precision']}f")
            trading_rules[trading_pair] = SouthXchangeTradingRule(
                trading_pair,
                min_price_increment= Decimal(precision_rule),
                min_base_amount_increment= Decimal(precision_rule)
            )
        return trading_rules

    async def all_trading_pairs(self) -> List[str]:
        # This method should be removed and instead we should implement _initialize_trading_pair_symbol_map
        return await SouthxchangeAPIOrderBookDataSource.fetch_trading_pairs()

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await SouthxchangeAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=trading_pairs,
            api_factory=self._api_factory,
            throttler=self._throttler
        )

    async def _get_rest_assistant(self) -> RESTAssistant_SX:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)
