import asyncio
import hashlib
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import dateutil.parser as dp
from async_timeout import timeout
from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.dexalot import (
    dexalot_constants as CONSTANTS,
    dexalot_utils,
    dexalot_web_utils as web_utils,
)
from hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source import DexalotClient
from hummingbot.connector.exchange.dexalot.dexalot_api_order_book_data_source import DexalotAPIOrderBookDataSource
from hummingbot.connector.exchange.dexalot.dexalot_api_user_stream_data_source import DexalotAPIUserStreamDataSource
from hummingbot.connector.exchange.dexalot.dexalot_auth import DexalotAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class DexalotExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 dexalot_api_key: str,
                 dexalot_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = dexalot_api_key
        self.secret_key = dexalot_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_dexalot_timestamp = 1.0

        self._orders_queued_to_create: List[GatewayInFlightOrder] = []
        self._orders_queued_to_cancel: List[GatewayInFlightOrder] = []
        self._queued_orders_task = None

        self._evm_params = {}
        self._tx_client: DexalotClient = self._create_tx_client()

        super().__init__(client_config_map)

    @staticmethod
    def dexalot_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(dexalot_type: str) -> OrderType:
        return OrderType[dexalot_type]

    @property
    def authenticator(self):
        return DexalotAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "dexalot"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def start_network(self):
        await super().start_network()
        await self._update_trading_rules()
        if self.is_trading_required:
            self._queued_orders_task = safe_ensure_future(self._process_queued_orders())

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It performs a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        await super().stop_network()
        if self._queued_orders_task is not None:
            self._queued_orders_task.cancel()
            self._queued_orders_task = None

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        # pairs_prices = await self._api_get(path_url=CONSTANTS.ALL_TICKERS_PATH_URL)
        api_factory = self._web_assistants_factory
        ws = await api_factory.get_ws_assistant()
        async with api_factory.throttler.execute_task(limit_id=CONSTANTS.WSS_URL):
            await ws.connect(ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
            payload = {
                "type": "marketsnapshotsubscribe",
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await ws.send(subscribe_orderbook_request)
        async for msg in ws.iter_messages():
            data = msg.data
            if data is not None and data["type"] == "marketSnapShot":
                price_list = data["data"]
                payload = {
                    "type": "marketsnapshotunsubscribe",
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
                await ws.send(subscribe_orderbook_request)
                await ws.disconnect()
                return price_list

    def _format_evmamount_to_amount(self, trading_pair, base_evm_amount: Decimal, quote_evm_amount: Decimal) -> Tuple:

        base_evmdecimals = self._evm_params[trading_pair].get("base_evmdecimals")
        quote_evmdecimals = self._evm_params[trading_pair].get("quote_evmdecimals")
        base_amount = base_evm_amount * Decimal(f"1e-{base_evmdecimals}")
        quote_amount = quote_evm_amount * Decimal(f"1e-{quote_evmdecimals}")

        return base_amount, quote_amount

    def _format_amount_to_evmamount(self, trading_pair, base_amount: Decimal, quote_amount: Decimal) -> Tuple:

        base_evmdecimals = self._evm_params[trading_pair].get("base_evmdecimals")
        quote_evmdecimals = self._evm_params[trading_pair].get("quote_evmdecimals")
        base_evm_amount = base_amount * Decimal(f"1e{base_evmdecimals}")
        quote_evm_amount = quote_amount * Decimal(f"1e{quote_evmdecimals}")

        return base_evm_amount, quote_evm_amount

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_tx_client(self) -> DexalotClient:
        return DexalotClient(
            self.secret_key,
            connector=self
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return DexalotAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DexalotAPIUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        trade_base_fee = build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper()
        )
        return trade_base_fee

    def _on_order_creation_failure(
            self,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            trade_type: TradeType,
            order_type: OrderType,
            price: Optional[Decimal],
            exception: Exception,
    ):
        self.logger().network(
            f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to {self.name_cap} for "
            f"{amount} {trading_pair} {price}.",
            exc_info=exception,
            app_warning_msg=f"Failed to submit {trade_type.name.upper()} order to {self.name_cap}. Check API key and network connection."
        )
        self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)

    def _update_order_after_creation_failure(self, order_id: str, trading_pair: str):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order_id,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FAILED,
        )
        self._order_tracker.process_order_update(order_update)
        return order_update

    def batch_order_cancel(self, orders_to_cancel: List[LimitOrder]):
        """
        Issues a batch order cancelation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_cancel: A list of the orders to cancel.
        """
        safe_ensure_future(coro=self._execute_batch_cancel(orders_to_cancel=orders_to_cancel))

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        incomplete_orders = {}
        limit_orders = []
        successful_cancellations = []

        for order in self.in_flight_orders.values():
            if not order.is_done:
                incomplete_orders[order.client_order_id] = order
                limit_orders.append(order.to_limit_order())

        if len(limit_orders) > 0:
            try:
                async with timeout(timeout_seconds):
                    cancellation_results = await self._execute_batch_cancel(orders_to_cancel=limit_orders)
                    for cr in cancellation_results:
                        if cr.success:
                            del incomplete_orders[cr.order_id]
                            successful_cancellations.append(CancellationResult(cr.order_id, True))
            except Exception:
                self.logger().network(
                    "Unexpected error cancelling orders.",
                    exc_info=True,
                    app_warning_msg="Failed to cancel order. Check API key and network connection."
                )
        failed_cancellations = [CancellationResult(oid, False) for oid in incomplete_orders.keys()]
        return successful_cancellations + failed_cancellations

    async def _execute_batch_cancel(self, orders_to_cancel: List[LimitOrder]) -> List[CancellationResult]:
        results = []
        tracked_orders_to_cancel = []

        for order in orders_to_cancel:
            tracked_order = self._order_tracker.all_updatable_orders.get(order.client_order_id)
            if tracked_order is not None and tracked_order.exchange_order_id:
                tracked_orders_to_cancel.append(tracked_order)
            else:
                results.append(CancellationResult(order_id=order.client_order_id, success=False))

        if len(tracked_orders_to_cancel) > 0:
            results.extend(await self._execute_batch_order_cancel(orders_to_cancel=tracked_orders_to_cancel))

        return results

    async def _execute_batch_order_cancel(self,
                                          orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancellationResult]:
        try:
            async with self._throttler.execute_task(limit_id=CONSTANTS.UID_REQUEST_WEIGHT):
                cancelation_results = []

                cancel_transaction_hash = await self._tx_client.cancel_order_list(orders_to_cancel=orders_to_cancel)
                for cancel_order_result in orders_to_cancel:
                    success = True
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=cancel_order_result.client_order_id,
                        trading_pair=cancel_order_result.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=(OrderState.CANCELED
                                   if self.is_cancel_request_in_exchange_synchronous
                                   else OrderState.PENDING_CANCEL),
                        misc_updates={"cancelation_transaction_hash": cancel_transaction_hash},
                    )
                    self._order_tracker.process_order_update(order_update)
                    cancelation_results.append(
                        CancellationResult(order_id=cancel_order_result.client_order_id, success=success)
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Failed to cancel orders {', '.join([o.client_order_id for o in orders_to_cancel])}",
                exc_info=True,
            )
            cancelation_results = [
                CancellationResult(order_id=order.client_order_id, success=False)
                for order in orders_to_cancel
            ]

        return cancelation_results

    async def _place_cancel(self, order_id: str, tracked_order: GatewayInFlightOrder):
        # Not required because of _execute_order_cancel redefinition
        raise NotImplementedError

    async def _execute_order_cancel(self, order: GatewayInFlightOrder) -> str:
        # Order cancelation requests for single orders are queued to be executed in batch if possible
        self._orders_queued_to_cancel.append(order)
        return None

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal, **kwargs) -> Tuple[str, float]:
        # Not required because of _place_order_and_process_update redefinition
        raise NotImplementedError

    async def _place_order_and_process_update(self, order: GatewayInFlightOrder, **kwargs) -> str:
        # Order creation requests for single orders are queued to be executed in batch if possible
        self._orders_queued_to_create.append(order)
        return None

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.sha256()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"

        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            slippage = CONSTANTS.MARKET_ORDER_SLIPPAGE
            market_price = mid_price * Decimal(1 + slippage)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.sha256()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            slippage = CONSTANTS.MARKET_ORDER_SLIPPAGE
            market_price = mid_price * Decimal(1 - slippage)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    async def _execute_batch_inflight_order_create(self, inflight_orders_to_create: List[GatewayInFlightOrder]):
        try:
            async with self._throttler.execute_task(limit_id=CONSTANTS.UID_REQUEST_WEIGHT):
                place_order_results = await self._tx_client.add_order_list(
                    order_list=inflight_orders_to_create
                )
                for in_flight_order in inflight_orders_to_create:
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=in_flight_order.client_order_id,
                        exchange_order_id=None,
                        trading_pair=in_flight_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=in_flight_order.current_state,
                        misc_updates={"creation_transaction_hash": place_order_results},
                    )
                    self.logger().debug(
                        f"\nCreated order {in_flight_order.client_order_id}  with TX {place_order_results}")
                    self._order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network("Batch order create failed.")
            for order in inflight_orders_to_create:
                self._on_order_creation_failure(
                    order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    trade_type=order.trade_type,
                    order_type=order.order_type,
                    price=order.price,
                    exception=ex,
                )

    async def _format_trading_rules(self, exchange_info_dict: List) -> List[TradingRule]:
        trading_pair_rules = exchange_info_dict
        retval = []
        for rule in filter(dexalot_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("pair"))
                min_order_size = Decimal(f"1e-{rule['basedisplaydecimals']}")
                min_price_inc = Decimal(f"1e-{rule['quotedisplaydecimals']}")
                min_notional = Decimal(rule['mintrade_amnt'])
                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=min_price_inc,
                                min_base_amount_increment=min_order_size,
                                min_notional_size=min_notional))

                self._evm_params[trading_pair] = {
                    "base_coin": rule["base"],
                    "quote_coin": rule["quote"],
                    "base_evmdecimals": Decimal(rule["quote_evmdecimals"]),
                    "quote_evmdecimals": Decimal(rule["base_evmdecimals"]),
                }

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                channel: str = event_message.get("type", None)
                if channel == CONSTANTS.USER_TRADES_ENDPOINT_NAME:
                    safe_ensure_future(self._process_trade_message(event_message))
                elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    self._process_order_message(event_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _create_trade_update_with_order_fill_data(
            self,
            order_fill: Dict[str, Any],
            order: InFlightOrder):

        is_maker = True if order_fill.get("addressMaker", "") == self.api_key else False
        takerSide = order_fill.get("takerSide")
        if is_maker:
            fee_amount = Decimal(order_fill.get("feeMaker", 0))
            if takerSide == "BUY":
                fee_asset = order.quote_asset
            else:
                fee_asset = order.base_asset
        else:
            fee_amount = Decimal(order_fill.get("feeTaker", 0))
            if takerSide == "BUY":
                fee_asset = order.base_asset
            else:
                fee_asset = order.quote_asset

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=fee_asset.upper(),
            flat_fees=[TokenAmount(
                amount=Decimal(fee_amount),
                token=fee_asset.upper()
            )]
        )

        trade_update = TradeUpdate(
            trade_id=str(order_fill["execId"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(order_fill["quantity"]),
            fill_quote_amount=Decimal(order_fill["quantity"]) * Decimal(order_fill["price"]),
            fill_price=Decimal(order_fill["price"]),
            fill_timestamp=order_fill["blockTimestamp"],
        )
        return trade_update

    async def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):

        exchange_order_id = trade["data"].get("makerOrder", "") \
            if trade["data"].get("addressMaker", "") == self.api_key else trade["data"].get("takerOrder", "")
        all_orders = self._order_tracker.all_fillable_orders
        self._calculate_available_balance_from_trades(trade["data"])
        try:
            for k, v in all_orders.items():
                await v.get_exchange_order_id()
        except Exception:
            pass
        _cli_tracked_orders = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
        if len(_cli_tracked_orders) == 0 or _cli_tracked_orders[0] is None:
            order_update: OrderUpdate = await self._request_order_status(tracked_order=None,
                                                                         exchange_order_id=exchange_order_id)
            # NOTE: Untracked order
            if order_update is None:
                self.logger().debug(f"Received untracked order with exchange order id of {exchange_order_id}")
                return
            client_order_id = order_update.client_order_id
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        else:
            tracked_order = _cli_tracked_orders[0]

        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
        else:
            trade_update = self._create_trade_update_with_order_fill_data(
                order_fill=trade["data"],
                order=tracked_order)
            self._order_tracker.process_trade_update(trade_update)

    def _create_order_update_with_order_status_data(self, order_status: Dict[str, Any], order: InFlightOrder):
        client_order_id = str(order_status.get("clientOrderId", ""))
        order.update_exchange_order_id(order_status["orderId"])
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=int(order_status["blockTimestamp"]),
            new_state=CONSTANTS.ORDER_STATE[order_status["status"]],
            client_order_id=client_order_id,
            exchange_order_id=str(order_status["orderId"]),
        )
        return order_update

    def _process_order_message(self, raw_msg: Dict[str, Any]):
        order_msg = raw_msg.get("data", {})
        client_order_id = str(order_msg.get("clientOrderId", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        self._calculate_available_balance_from_orders(order_msg)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        order_update = self._create_order_update_with_order_status_data(order_status=order_msg, order=tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    def _calculate_available_balance_from_trades(self, trade_msg: Dict):
        base_coin = trade_msg["pair"].split("/")[0].upper()
        quote_coin = trade_msg["pair"].split("/")[1].upper()

        is_maker = True if trade_msg.get("addressMaker", "") == self.api_key else False
        takerSide = trade_msg.get("takerSide")
        if is_maker:
            if takerSide == "BUY":
                base_collateral_value = Decimal(trade_msg["quantity"])
                quote_collateral_value = Decimal(trade_msg.get("quantity")) * Decimal(trade_msg.get("price"))
                self._account_available_balances[quote_coin] += quote_collateral_value

                self._account_balances[quote_coin] += quote_collateral_value
                self._account_balances[base_coin] -= base_collateral_value

            else:
                base_collateral_value = Decimal(trade_msg["quantity"])
                quote_collateral_value = Decimal(trade_msg.get("quantity")) * Decimal(trade_msg.get("price"))
                self._account_available_balances[base_coin] += base_collateral_value

                self._account_balances[quote_coin] -= quote_collateral_value
                self._account_balances[base_coin] += base_collateral_value
        else:
            if takerSide == "BUY":
                base_collateral_value = Decimal(trade_msg["quantity"])
                quote_collateral_value = Decimal(trade_msg.get("quantity")) * Decimal(trade_msg.get("price"))
                self._account_available_balances[base_coin] += base_collateral_value

                self._account_balances[quote_coin] -= quote_collateral_value
                self._account_balances[base_coin] += base_collateral_value

            else:
                base_collateral_value = Decimal(trade_msg["quantity"])
                quote_collateral_value = Decimal(trade_msg.get("quantity")) * Decimal(trade_msg.get("price"))
                self._account_available_balances[quote_coin] += quote_collateral_value

                self._account_balances[quote_coin] += quote_collateral_value
                self._account_balances[base_coin] -= base_collateral_value

    def _calculate_available_balance_from_orders(self, order_msg: Dict):
        if order_msg.get("pair"):
            base_coin = order_msg["pair"].split("/")[0].upper()
            quote_coin = order_msg["pair"].split("/")[1].upper()
            if order_msg["status"] in ["NEW", 0]:
                if order_msg["side"] == "BUY" or order_msg["side"] == 0:
                    quote_collateral_value = Decimal(order_msg.get("price")) * Decimal(order_msg.get("quantity"))
                    self._account_available_balances[quote_coin] -= quote_collateral_value
                else:
                    base_collateral_value = Decimal(order_msg["quantity"])
                    self._account_available_balances[base_coin] -= base_collateral_value
            # Partial status used to update _account_available_balances during update_balance
            if order_msg["status"] in [2]:
                if order_msg["side"] == 0:  # BUY
                    quote_collateral_unfilled_value = \
                        Decimal(order_msg["price"]) * Decimal(order_msg["quantity"]) - Decimal(order_msg["totalamount"])
                    self._account_available_balances[quote_coin] -= quote_collateral_unfilled_value
                else:
                    base_collateral_unfilled_value = Decimal(order_msg["quantity"]) - Decimal(
                        order_msg["quantityfilled"])
                    self._account_available_balances[base_coin] -= base_collateral_unfilled_value
            if order_msg["status"] in ["CANCELED", 4]:
                if order_msg["side"] == "BUY" or order_msg["side"] == 0:
                    quote_collateral_value = Decimal(order_msg.get("price")) * Decimal(order_msg.get("quantity"))
                    quote_filled_value = Decimal(order_msg.get("totalamount") or order_msg.get("totalAmount"))
                    self._account_available_balances[quote_coin] += quote_collateral_value
                    self._account_available_balances[quote_coin] -= quote_filled_value
                else:
                    base_collateral_value = Decimal(order_msg["quantity"])
                    base_filled_value = Decimal(order_msg["quantityfilled"])
                    self._account_available_balances[base_coin] += base_collateral_value
                    self._account_available_balances[base_coin] -= base_filled_value

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "orderid": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.IP_REQUEST_WEIGHT)

            for trade in all_fills_response:
                exchange_order_id = str(trade["orderid"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["feeunit"].upper(),
                    flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeunit"].upper())]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["execid"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["quantity"]),
                    fill_quote_amount=Decimal(trade["quantity"]) * Decimal(trade["price"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=dp.parse(trade["ts"]).timestamp(),
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder, exchange_order_id=None) -> OrderUpdate:
        try:
            if not exchange_order_id:
                exchange_order_id = await tracked_order.get_exchange_order_id()
        except asyncio.TimeoutError:
            self.logger().warning(
                f"Error fetching status update for the lost order {tracked_order.client_order_id}: TimeoutError.")
            order_update = self._update_order_after_creation_failure(
                tracked_order.client_order_id,
                tracked_order.trading_pair
            )
            return order_update
        if not tracked_order:
            all_fillable_orders_by_exchange_order_id = {
                order.exchange_order_id: order for order in self._order_tracker.all_fillable_orders.values()
            }
            tracked_order = all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL.format(exchange_order_id),
            params={},
            is_auth_required=True,
            limit_id=CONSTANTS.IP_REQUEST_WEIGHT)
        client_order_id = updated_order_data.get("clientOrderId")
        tracked_order = self._order_tracker.all_fillable_orders.get(
            client_order_id) if not tracked_order else tracked_order
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=client_order_id or tracked_order.client_order_id,
            exchange_order_id=str(exchange_order_id),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=dp.parse(updated_order_data["timestamp"]).timestamp(),
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        self._account_balances, self._account_available_balances = await self._tx_client.get_balances(
            self._account_balances, self._account_available_balances
        )

        open_orders = await self._api_get(
            path_url=CONSTANTS.ORDERS_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.IP_REQUEST_WEIGHT
        )
        for order_msg in open_orders["rows"]:
            self._calculate_available_balance_from_orders(order_msg)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()
        for symbol_data in filter(dexalot_utils.is_exchange_information_valid, exchange_info):
            mapping[symbol_data["pair"]] = combine_to_hb_trading_pair(base=symbol_data["base"].upper(),
                                                                      quote=symbol_data["quote"].upper())
        self._set_trading_pair_symbol_map(mapping)

    async def _process_queued_orders(self):
        while True:
            try:
                # Executing the batch cancelation and creation process shielded from this async task to isolate the
                # creation/cancelation process from network disconnections (network disconnections cancel this task)
                task = asyncio.create_task(self._cancel_and_create_queued_orders())
                await asyncio.shield(task)
                sleep_time = (self.clock.tick_size * 0.5
                              if self.clock is not None
                              else self._orders_processing_delta_time)
                await self._sleep(sleep_time)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while processing queued individual orders", exc_info=True)
                await self._sleep(self.clock.tick_size * 0.5)

    async def _cancel_and_create_queued_orders(self):
        if len(self._orders_queued_to_cancel) > 0:
            orders = [order.to_limit_order() for order in self._orders_queued_to_cancel]
            self._orders_queued_to_cancel = []
            await self._execute_batch_cancel(orders_to_cancel=orders)
        if len(self._orders_queued_to_create) > 0:
            orders = self._orders_queued_to_create
            self._orders_queued_to_create = []
            await self._execute_batch_inflight_order_create(inflight_orders_to_create=orders)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        last_price = self.order_books.get(trading_pair).last_trade_price

        return last_price

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path,
                            headers={"Content-Type": "application/json"},
                            limit_id=CONSTANTS.IP_REQUEST_WEIGHT)

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path,
                                            headers={"Content-Type": "application/json"},
                                            limit_id=CONSTANTS.IP_REQUEST_WEIGHT)
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path,
                                            headers={"Content-Type": "application/json"},
                                            limit_id=CONSTANTS.IP_REQUEST_WEIGHT)
        return exchange_info
