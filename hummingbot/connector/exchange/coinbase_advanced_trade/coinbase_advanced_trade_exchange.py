import asyncio
import logging
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncGenerator, AsyncIterable, Dict, Iterable, List, Tuple

from async_timeout import timeout
from bidict import bidict

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as constants
import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils as web_utils
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_api_order_book_data_source import (
    CoinbaseAdvancedTradeAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_api_user_stream_data_source import (
    CoinbaseAdvancedTradeAPIUserStreamDataSource,
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_order_book import (
    CoinbaseAdvancedTradeOrderBook,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_timestamp_from_exchange_time,
    set_exchange_time_from_timestamp,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinbaseAdvancedTradeExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 2.5

    web_utils = web_utils

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 coinbase_advanced_trade_api_key: str,
                 coinbase_advanced_trade_api_secret: str,
                 trading_pairs: List[str] | None = None,
                 trading_required: bool = True,
                 domain: str = constants.DEFAULT_DOMAIN,
                 ):
        self._api_key = coinbase_advanced_trade_api_key
        self.secret_key = coinbase_advanced_trade_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_coinbase_advanced_trade_timestamp = -1
        super().__init__(client_config_map)

        self._asset_uuid_map: Dict[str, str] = {}
        self._pair_symbol_map_initialized = False
        self._market_assets_initialized = False
        self._market_assets: List[Dict[str, Any]] = []

        # Update the time synchronizer logger to the current class logger
        self._time_synchronizer.logger = self.logger
        self.logger().debug(f"{self.name} instance created {self}.")

    def __repr__(self) -> str:
        rep: str = (
            f"CoinbaseAdvancedTradeExchange({self._domain})\n"
            f"  - trading_pairs: {self._trading_pairs}\n"
            f"  - trading_required: {self._trading_required}\n"
            f"  - asset_uuid_map: {self._asset_uuid_map}\n"
            f"  - market_assets_initialized: {self._market_assets_initialized}\n"
            f"  - pair_symbol_map_initialized: {self._market_assets}\n"
            f"  - time_synchronizer: {self._time_synchronizer}\n"
            f"  - last_poll_timestamp: {self._last_poll_timestamp}\n"
            f"  - in_flight_orders: {self._order_tracker.active_orders}\n"
            f"  - status_dict: {self.status_dict}\n"
        )
        return rep

    @property
    def asset_uuid_map(self) -> Dict[str, str]:
        return self._asset_uuid_map

    @staticmethod
    def coinbase_advanced_trade_order_type(order_type: OrderType) -> str:
        if order_type is OrderType.LIMIT_MAKER:
            return "LIMIT_MAKER"
        if order_type is OrderType.LIMIT:
            return "LIMIT"
        if order_type is OrderType.MARKET:
            return "MARKET"

    @staticmethod
    def to_hb_order_type(coinbase_advanced_trade_type: str) -> OrderType:
        return OrderType[coinbase_advanced_trade_type]

    @property
    def authenticator(self):
        return CoinbaseAdvancedTradeAuth(
            api_key=self._api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "coinbase_advanced_trade"
        else:
            return f"coinbase_advanced_trade_{self._domain}"

    @property
    def rate_limits_rules(self):
        return constants.RATE_LIMITS

    @property
    def real_time_balance_update(self):
        return False

    @property
    def domain(self):
        return self._domain

    @property
    def last_poll_timestamp(self) -> float:
        # Defined in ExchangePyBase
        return self._last_poll_timestamp

    @property
    def client_order_id_max_length(self):
        return constants.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return constants.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return constants.ALL_PAIRS_EP

    @property
    def trading_pairs_request_path(self):
        return constants.ALL_PAIRS_EP

    @property
    def check_network_request_path(self):
        return constants.SERVER_TIME_EP

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def time_synchronizer(self) -> TimeSynchronizer:
        # Defined in ExchangePyBase
        return self._time_synchronizer

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        # Websocket feed has 'PENDING' state, but REST API does not, it also seems PENDING is for CREATE only
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        self.logger().debug(
            f"\n   symbols_mapping_initialized: {self.trading_pair_symbol_map_ready()}\n"
            f"   order_books_initialized: {self.order_book_tracker.ready}\n"
            f"   account_balance: {len(self._account_balances) > 0}\n"
            f"   account_balance: {len(self._account_available_balances) > 0}\n"
            f"   trading_required: {self.is_trading_required}\n"
            f"   trading_rule_initialized: {len(self._trading_rules) > 0 if self.is_trading_required else True}\n"
            f"   user_stream_initialized: {self._is_user_stream_initialized()}\n"
        )
        return {
            "symbols_mapping_initialized": self.trading_pair_symbol_map_ready(),
            "order_books_initialized": self.order_book_tracker.ready,
            "account_balance": not self.is_trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self.is_trading_required else True,
            "user_stream_initialized": self._is_user_stream_initialized(),
        }

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def all_trading_pairs(self) -> List[str]:
        """
        List of all trading pairs supported by the connector

        :return: List of trading pair symbols in the Hummingbot format
        """
        # Defined in ExchangeBase, but need to debug!
        mapping = await self.trading_pair_symbol_map()
        return list(mapping.values())

    async def start_network(self):
        await self._initialize_market_assets()
        await self._update_trading_rules()
        self.logger().info("Coinbbase currently not returning trading pairs for USDC in orderbook public messages. setting to USD currently pending fix.")
        await super().start_network()

    def _stop_network(self):
        super()._stop_network()

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        # Overriding ExchangePyBase: Synchronizer expects time in ms
        try:
            await self._time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=self.web_utils.get_current_server_time_ms(
                    throttler=self._throttler,
                    domain=self.domain,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if not pass_on_non_cancelled_error:
                self.logger().exception(f"Error requesting time from {self.name_cap} server")
                raise

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # time endpoint does not communicate an error code
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinbaseAdvancedTradeAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinbaseAdvancedTradeAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return (
            constants.ORDER_STATUS_NOT_FOUND_ERROR_CODE in str(status_update_exception) or
            "Not Found" in str(status_update_exception) or
            "INVALID_ARGUMENT" in str(status_update_exception)
        )

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "UNKNOWN_CANCEL_ORDER" in str(cancelation_exception)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: bool | None = None) -> TradeFeeBase:
        trade_base_fee: TradeFeeBase = build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency,
            quote_currency=quote_currency
        )
        return trade_base_fee

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        """
        Places an order with the exchange and returns the order ID and the timestamp of the order.
        reference: https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_postorder
        Maximum open orders: 500
        """
        amount_str: str = f"{amount:f}"
        price_str: str = f"{price:f}"
        type_str: str = CoinbaseAdvancedTradeExchange.coinbase_advanced_trade_order_type(order_type)
        side_str: str = constants.SIDE_BUY if trade_type is TradeType.BUY else constants.SIDE_SELL
        symbol: str = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        if type_str in {"LIMIT", "LIMIT_MAKER"}:
            order_configuration = {
                "limit_limit_gtc": {
                    "base_size": amount_str,
                    "limit_price": price_str
                }
            }
        # elif type_str == "LIMIT_MAKER":
        #     order_configuration = {
        #         "limit_limit_gtc": {
        #             "base_size": amount_str,
        #             "limit_price": price_str,
        #             # As per HB dev team, LIMIT_MAKER should be converted to LIMIT
        #             # "post_only": True
        #         }
        #     }
        elif type_str == "MARKET":
            if side_str == constants.SIDE_BUY:
                quote_size: Decimal = (amount * price).quantize(
                    self._trading_rules[trading_pair].min_quote_amount_increment)
                order_configuration = {
                    "market_market_ioc": {
                        "quote_size": str(quote_size),
                    }
                }
            else:
                order_configuration = {
                    "market_market_ioc": {
                        "base_size": amount_str,
                    }
                }
        else:
            raise ValueError(f"Invalid order type {order_type}.")

        api_params = {
            "client_order_id": f"{order_id}",
            "product_id": symbol,
            "side": side_str,
            "order_configuration": order_configuration
        }

        order_result = await self._api_post(
            path_url=constants.ORDER_EP,
            data=api_params,
            is_auth_required=True,
        )

        if order_result["success"]:
            o_id = str(order_result["success_response"]["order_id"])
            transact_time = self.time_synchronizer.time()
            self.logger().debug(f"Placed {type_str} order {side_str} {amount_str} {symbol} @ {price_str}")
            return o_id, transact_time

        elif "INSUFFICIENT_FUND" in order_result['error_response']["error"]:
            self.logger().error(
                f"{self.name} reports insufficient funds for {side_str} {amount_str} {symbol} @ {price_str}")
            return "UNKNOWN", self.time_synchronizer.time()

        elif "INVALID_LIMIT_PRICE_POST_ONLY" in order_result['error_response']["error"]:
            self.logger().error(
                f"{self.name} cannot place {type_str} order {side_str} {symbol} @ {price_str}. Likely not POST-able.")
            return "UNKNOWN", self.time_synchronizer.time()

        else:
            raise ValueError(f"Failed to place order on {self.name}. Error: {order_result['error_response']}")

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        # Overriding ExchangePyBase since it sets the status to OPEN
        exchange_order_id, update_timestamp = await self._place_order(
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            amount=order.amount,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            **kwargs,
        )

        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=str(exchange_order_id),
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=OrderState.PENDING_CREATE if exchange_order_id != "UNKNOWN" else OrderState.FAILED,
        )
        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run
        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """

        async def execute_cancels(order_ids: List[str]) -> List[str]:
            """
            Requests the exchange to cancel an active order

            :param order_ids: the client id of the orders to cancel
            """
            tracked_orders = [(o, t) for o in order_ids if (t := self._order_tracker.fetch_tracked_order(o))]
            result = await self._execute_orders_cancel(orders=[t[1] for t in tracked_orders if t[1] is not None])
            return result

        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        tasks = [execute_cancels([o.client_order_id for o in incomplete_orders])]
        order_id_set = {o.client_order_id for o in incomplete_orders}
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for task in cancellation_results:
                    if isinstance(task, Exception):
                        continue
                    for client_order_id in task:
                        if client_order_id is not None:
                            order_id_set.remove(client_order_id)
                            successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order. Check API key and network connection."
            )
        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def _cancel_lost_orders(self):
        await self._execute_orders_cancel(orders=[l for _, l in self._order_tracker.lost_orders.items()])

    async def _execute_orders_cancel(self, orders: List[InFlightOrder]) -> List[str]:
        try:
            cancelled: List[bool] = await self._execute_orders_cancel_and_process_update(orders=orders)
            return [order.client_order_id for order, cancelled in zip(orders, cancelled) if cancelled]

        except asyncio.CancelledError:
            raise

    async def _execute_orders_cancel_and_process_update(self, orders: List[InFlightOrder]) -> List[bool]:
        cancelled = await self._place_cancels(order_ids=[o.exchange_order_id for o in orders])
        for o, c in zip(orders, cancelled):
            if c["success"]:
                update_timestamp = self.current_timestamp
                if update_timestamp is None or math.isnan(update_timestamp):
                    update_timestamp = self.time_synchronizer.time()

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=o.client_order_id,
                    trading_pair=o.trading_pair,
                    update_timestamp=update_timestamp,
                    new_state=OrderState.CANCELED,
                )
                self._order_tracker.process_order_update(order_update)

            elif c["failure_reason"] in ["UNKNOWN_CANCEL_ORDER", "DUPLICATE_CANCEL_REQUEST"]:
                self.logger().warning(
                    f"Failed to cancel order {o.client_order_id} (order not found OR duplicate request)")
                await self._order_tracker.process_order_not_found(o.client_order_id)
            else:
                self.logger().error(f"Failed to cancel order {o.client_order_id}", exc_info=True)

        return [c["success"] for c in cancelled]

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_cancelorders

        :param order_id: str
        :param tracked_order: InFlightOrder
        :return: bool
        """
        # Requesting to cancel an empty order seems to hang the request
        if tracked_order.exchange_order_id is None:
            self.logger().warning(f"Failed to cancel order {order_id} with exchange_id: None")
            self.logger().debug(f"tracked_order: {tracked_order.attributes}")
            return False
        if tracked_order.exchange_order_id == "":
            self.logger().warning(f"Failed to cancel order {order_id} with an empty exchange_id in tracked_order")
            self.logger().debug(f"tracked_order: {tracked_order.attributes}")
            return False
        if tracked_order.exchange_order_id == "UNKNOWN":
            self.logger().error(f"Failed to cancel order {order_id} without exchange_id: UNKNOWN"
                                "File a bug report with the Hummingbot team.")
            raise ValueError(f"Failed to cancel order {order_id} with exchange_id: UNKNOWN")

        result = await self._place_cancels(order_ids=[tracked_order.exchange_order_id])

        if result[0]["success"]:
            return True

        if result[0]["failure_reason"] in ["UNKNOWN_CANCEL_ORDER", "DUPLICATE_CANCEL_REQUEST"]:
            self.logger().warning(f"Failed to cancel order {order_id} (order not found OR duplicate request)")
            await self._order_tracker.process_order_not_found(order_id)

        if result[0]["failure_reason"] in ["UNKNOWN_CANCEL_FAILURE_REASON",
                                           "INVALID_CANCEL_REQUEST",
                                           "COMMANDER_REJECTED_CANCEL_ORDER"]:
            self.logger().error(f"Failed to cancel order {order_id} (Rejected by Coinbase Advanced Trade or Invalid "
                                f"request)")
        return False

    async def _place_cancels(self, order_ids: List[str], max_size: int = 100) -> List[Dict[str, Any]]:
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_cancelorders
        MAX_ORDERS is 100 (ChangeLog: 2024-JAN-16)

        :param order_ids: List[str]
        :return: List[Dict[str, Any]]
        """
        # Safeguarding the API call
        order_ids = [o for o in order_ids if o is not None and o != "" and o != "UNKNOWN"]

        if not order_ids:
            return [{"success": True, "failure_reason": "EMPTY_CANCEL_REQUEST"}]

        all_results = []
        for i in range(0, len(order_ids), max_size):
            batched_order_ids = order_ids[i:i + max_size]
            api_data = {
                "order_ids": batched_order_ids
            }
            try:
                cancel_result: Dict[str, Any] = await self._api_post(
                    path_url=constants.BATCH_CANCEL_EP,
                    data=api_data,
                    is_auth_required=True)

                if cancel_result.get("error", False) == 'InvalidArgument':
                    # Error message is 'Too many orderIDs entered, limit is ' + str(NEW_LIMIT)
                    limit = cancel_result.get("message", "").split(" ")[-1]
                    # Resubmit for the remaining orders
                    all_results.extend(await self._place_cancels(order_ids=order_ids[i:], max_size=int(limit)))
                    return all_results

                results: List[Dict[str, Any]] = cancel_result.get("results", [])
                all_results.extend(results)

            except OSError as e:
                self.logger().error(f"Error cancelling orders: {str(e)}\n   {api_data}", exc_info=False)
                return [{"success": False, "failure_reason": "UNKNOWN_CANCEL_FAILURE_REASON"} for _ in order_ids]

        return all_results

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get a list of bids/asks for a single product.
        https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getproductbook

        :param trading_pair: str
        :return: OrderBookMessage
        """
        params = {
            "product_id": await self.trading_pair_associated_to_exchange_symbol(trading_pair)
        }

        snapshot: Dict[str, Any] = await self._api_get(
            path_url=constants.SNAPSHOT_EP,
            params=params,
            is_auth_required=True,
            limit_id=constants.SNAPSHOT_EP,
        )

        snapshot_timestamp: float = self.time_synchronizer.time()

        snapshot_msg: OrderBookMessage = CoinbaseAdvancedTradeOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Queries Order status by order_id.
        https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_gethistoricalorder

        :param tracked_order: InFlightOrder
        :return: OrderUpdate
        """
        if (
                tracked_order.exchange_order_id is None or
                tracked_order.exchange_order_id == "" or
                tracked_order.exchange_order_id == "UNKNOWN"
        ):
            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id="",
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.time_synchronizer.time(),
                new_state=OrderState.FAILED,
            )

        updated_order_data = await self._api_get(
            path_url=constants.GET_ORDER_STATUS_EP.format(order_id=tracked_order.exchange_order_id),
            params={},
            is_auth_required=True,
            limit_id=constants.GET_ORDER_STATUS_RATE_LIMIT_ID,
        )

        status: str = updated_order_data['order']["status"]
        if status != "UNKNOWN_ORDER_STATUS":
            completion: Decimal = Decimal(updated_order_data['order']["completion_percentage"])
            if status == "OPEN" and completion < Decimal("100"):
                status = "PARTIALLY_FILLED"
        if status not in ["QUEUED", "CANCEL_QUEUED"]:
            new_state = constants.ORDER_STATE[status]

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(updated_order_data['order']["order_id"]),
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.time_synchronizer.time(),
                new_state=new_state,
            )

            return order_update

    # Overwriting this method from ExchangePyBase that seems to force mis-handling data flow
    # as well as duplicating expensive API calls (call for all products)
    async def _update_trading_rules(self):
        def decimal_or_none(x: Any) -> Decimal | None:
            return Decimal(x) if x is not None else None

        self.trading_rules.clear()
        trading_pair_symbol_map: bidict[str, str] = bidict()

        if not self._market_assets_initialized:
            await self._initialize_market_assets()

        products: List[Dict[str, Any]] = self._market_assets

        if products is None or not products:
            return

        for product in products:
            # Coinbase Advanced Trade API returns the trading pair in the format of "BASE-QUOTE"
            trading_pair: str = product.get("product_id")
            try:
                trading_rule: TradingRule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=decimal_or_none(product.get("base_min_size", None)),
                    max_order_size=decimal_or_none(product.get("base_max_size", None)),
                    min_price_increment=decimal_or_none(product.get("quote_increment", None)),
                    min_base_amount_increment=decimal_or_none(product.get("base_increment", None)),
                    min_quote_amount_increment=decimal_or_none(product.get("quote_increment", None)),
                    min_notional_size=decimal_or_none(product.get("quote_min_size", None)),
                    min_order_value=decimal_or_none(product.get("base_min_size", None)) * decimal_or_none(
                        product.get("price", None)),
                    max_price_significant_digits=Decimal(
                        abs(math.floor(
                            math.log10(
                                abs(float(product.get("quote_increment", 0))))))),
                    supports_limit_orders=product.get("supports_limit_orders", False),
                    supports_market_orders=product.get("supports_market_orders", False),
                    buy_order_collateral_token=None,
                    sell_order_collateral_token=None
                )
            except TypeError:
                self.logger().error(
                    f"Error parsing trading pair rule for {product.get('product_id')}, skipping.", exc_info=True,
                )
                continue

            self.trading_rules[trading_pair] = trading_rule

            trading_pair_symbol_map[product.get("product_id", None)] = trading_pair
        self.logger().info("Coinbbase currently not returning trading pairs for USDC in orderbook public messages. setting to USD currently pending fix.")
        self._set_trading_pair_symbol_map(trading_pair_symbol_map)

    async def _initialize_trading_pair_symbol_map(self):
        await self._update_trading_rules()
        self._pair_symbol_map_initialized: bool = True

    async def _initialize_market_assets(self):
        """
        Fetch the list of trading pairs from the exchange and map them
        """
        try:
            params: Dict[str, Any] = {}
            products: Dict[str, Any] = await self._api_get(
                path_url=constants.ALL_PAIRS_EP,
                params=params,
                is_auth_required=True)
            self._market_assets = [p for p in products.get("products") if all((p.get("product_type", None) == "SPOT",
                                                                               p.get("trading_disabled", None) is False,
                                                                               p.get("is_disabled", None) is False,
                                                                               p.get("cancel_only", None) is False,
                                                                               p.get("auction_mode", None) is False))]
            self._market_assets_initialized = True
        except Exception as e:
            self.logger().exception(f"Error getting all trading pairs from Coinbase Advanced Trade: {e}")

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    def update_balance(self, asset: str, balance: Decimal):
        self._account_balances[asset] = balance

    def update_available_balance(self, asset: str, balance: Decimal):
        self._account_available_balances[asset] = balance

    def remove_balances(self, assets: Iterable[str]):
        for asset in assets:
            self._account_balances.pop(asset, None)
            self._account_available_balances.pop(asset, None)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        self.logger().debug("DBG:Balance _update_balance")
        async for account in self._list_trading_accounts():  # type: ignore # Known Pycharm issue
            asset_name: str = account.get("currency")
            hold_value: Decimal = Decimal(account.get("hold").get("value"))
            available_balance: Decimal = Decimal(account.get("available_balance").get("value"))

            # Skip assets with zero balance
            if hold_value == Decimal("0") and available_balance == Decimal("0"):
                continue

            self.update_balance(asset_name, hold_value + available_balance)
            self.update_available_balance(asset_name, available_balance)
            remote_asset_names.add(asset_name)

        # Request removal of non-valid assets
        self.remove_balances(local_asset_names.difference(remote_asset_names))
        self.logger().debug(f"DBG:Balance '-> Balance updated: {self._account_balances}")

    async def _list_one_page_of_accounts(self, cursor: str) -> Dict[str, Any]:
        """
        List one page of accounts with maximum of 250 accounts per page.
        https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getaccounts
        """
        params = {"limit": 250}
        if cursor != "0":
            params["cursor"] = cursor
        response: Dict[str, Any] = await self._api_get(
            path_url=constants.ACCOUNTS_LIST_EP,
            params=params,
            is_auth_required=True,
        )
        return response

    async def _list_trading_accounts(self) -> AsyncGenerator[Dict[str, Any], None]:
        has_next_page = True
        cursor = "0"

        while has_next_page:
            page: Dict[str, Any] = await self._list_one_page_of_accounts(cursor)
            has_next_page = page.get("has_next")
            cursor = page.get("cursor")
            for account in page.get("accounts"):
                self._asset_uuid_map[account.get("currency")] = account.get("uuid")
                yield account

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        product_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params: Dict[str, Any] = {
            "limit": 1,
        }

        trade: Dict[str, Any] = await self._api_get(
            path_url=constants.PAIR_TICKER_24HR_EP.format(product_id=product_id),
            params=params,
            limit_id=constants.PAIR_TICKER_24HR_RATE_LIMIT_ID,
            is_auth_required=True
        )
        return float(trade.get("trades")[0]["price"])

    async def get_all_pairs_prices(self) -> AsyncGenerator[Dict[str, str], None]:
        """
        Fetches the prices of all symbols in the exchange with a default quote of USD
        """
        products: List[Dict[str, str]] = await self._api_get(
            path_url=constants.ALL_PAIRS_EP,
            is_auth_required=True)
        for p in products:
            if all((
                    p.get("product_type", None) == "SPOT",
                    p.get("trading_disabled", None) is False,
                    p.get("is_disabled", None) is False,
                    p.get("cancel_only", None) is False,
                    p.get("auction_mode", None) is False
            )):
                yield {p.get("product_id"): p.get("price")}

    async def get_exchange_rates(self, quote_token: str) -> Dict[str, str] | None:
        """
        Fetches the prices of all symbols in the exchange with a default quote of USD
        """
        response: Dict[str, Any] = await self._api_get(
            path_url=constants.EXCHANGE_RATES_QUOTE_EP.format(quote_token=quote_token),
            limit_id=constants.EXCHANGE_RATES_QUOTE_LIMIT_ID,
            is_auth_required=False)

        data = response.get("data")
        if data is not None and data.get("rates") is not None:
            return data.get("rates")

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        fees: Dict[str, Any] = await self._api_get(path_url=constants.TRANSACTIONS_SUMMARY_EP,
                                                   is_auth_required=True)
        self._trading_fees = fees

    async def _iter_user_event_queue(self) -> AsyncIterable[CoinbaseAdvancedTradeCumulativeUpdate]:
        """
        Called by _user_stream_event_listener.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error while reading user events queue. Retrying in 1s.")
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are order updates.
        """
        async for event_message in self._iter_user_event_queue():
            if isinstance(event_message, dict):
                if (
                        event_message.get("channel") != "user"
                        or event_message.get("sequence_num") != 1
                ):
                    self.logger().error(
                        "Skipping non-cumulative update. This is unintended, but possible, notify devs."
                        f"\n   event_message: {event_message}"
                    )
                continue

            self.logger().debug(f"_user_stream_event_listener: {event_message.client_order_id} {event_message.status}")

            fillable_order: InFlightOrder = self._order_tracker.all_fillable_orders.get(event_message.client_order_id)
            updatable_order: InFlightOrder = self._order_tracker.all_updatable_orders.get(
                event_message.client_order_id)
            state = event_message.status
            if state not in ["QUEUED", "CANCEL_QUEUED"]:
                new_state: OrderState = constants.ORDER_STATE[event_message.status]
                partially: bool = all((event_message.cumulative_base_amount > Decimal("0"),
                                       event_message.remainder_base_amount > Decimal("0"),
                                       new_state == OrderState.OPEN))
                new_state = OrderState.PARTIALLY_FILLED if partially else new_state

                if fillable_order is not None and new_state == OrderState.FILLED:
                    self.logger().debug(
                        f" '-> Fillable: {event_message.client_order_id}. "
                        f"Trigger FILL request at :{self.time_synchronizer.time()}")
                    # This fails the tests, but it is not a problem for the connector
                    # safe_ensure_future(self._update_order_fills_from_trades())
                    await self._update_order_fills_from_trades()

                if updatable_order is not None:
                    self.logger().debug(f" '-> Updatable order: {event_message.client_order_id}")
                    order_update = OrderUpdate(
                        trading_pair=updatable_order.trading_pair,
                        update_timestamp=event_message.fill_timestamp_s,
                        new_state=new_state,
                        client_order_id=event_message.client_order_id,
                        exchange_order_id=event_message.exchange_order_id,
                    )
                    self._order_tracker.process_order_update(order_update)
                else:
                    self.logger().debug(f"Skipping non-updatable order: {event_message.client_order_id}")

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Coinbaase's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Coinbaase's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is UPDATE_ORDER_STATUS_MIN_INTERVAL seconds.
        """

        def is_execution_time() -> bool:
            """Sets execution time for small and long intervals."""
            small_interval_last_tick: float = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
            small_interval_current_tick: float = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
            long_interval_last_tick: float = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
            long_interval_current_tick: float = self.current_timestamp / self.LONG_POLL_INTERVAL

            in_flight_orders: int = len(self.in_flight_orders)

            return (long_interval_current_tick > long_interval_last_tick
                    or (in_flight_orders > 0 and small_interval_current_tick > small_interval_last_tick))

        async def query_trades(pair: str, timestamp=None) -> List[Dict[str, Any]]:
            """Queries trades for a trading pair."""
            trading_pairs = []
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=pair)
            trading_pairs.append(trading_pair)
            p = {"product_ids": trading_pairs}
            if timestamp is not None:
                p["start_sequence_timestamp"] = timestamp

            t: List[Dict[str, Any]] = await self._api_get(
                path_url=constants.FILLS_EP,
                params=p,
                is_auth_required=True)
            return t

        if is_execution_time():
            self.logger().debug(f" '-> Fill request at: {self.time_synchronizer.time()}")
            query_time = set_exchange_time_from_timestamp(self._last_trades_poll_coinbase_advanced_trade_timestamp, "s")
            self._last_trades_poll_coinbase_advanced_trade_timestamp = self.time_synchronizer.time()

            order_by_exchange_id_map = {
                order.exchange_order_id: order
                for order in self._order_tracker.all_fillable_orders.values()
            }

            pairs = self.trading_pairs
            results = await safe_gather(*[query_trades(p, query_time) for p in pairs], return_exceptions=True)

            for trades, trading_pair in zip(results, pairs):
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order >{trading_pair}<: >{trades}<.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue

                for trade in trades["fills"]:
                    exchange_order_id = trade["order_id"]
                    quote_token: str = trading_pair.split("-")[1]

                    if not isinstance(trade["trade_time"], float):
                        trade_time = float(get_timestamp_from_exchange_time(trade["trade_time"], "s"))
                    else:
                        trade_time = trade["trade_time"]

                    f_fee: TokenAmount = TokenAmount(amount=Decimal(trade["commission"]), token=quote_token)
                    fee = AddedToCostTradeFee(percent_token=quote_token, flat_fees=[f_fee])

                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]

                        if trade["size_in_quote"] is True:
                            fill_quote_amount: Decimal = Decimal(trade["size"])
                            fill_base_amount: Decimal = Decimal(trade["size"]) / Decimal(trade["price"])
                        else:
                            fill_base_amount: Decimal = Decimal(trade["size"])
                            fill_quote_amount: Decimal = Decimal(trade["size"]) * Decimal(trade["price"])

                        trade_update = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=fill_base_amount,
                            fill_quote_amount=fill_quote_amount,
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=trade_time,
                            is_taker=False
                        )
                        self._order_tracker.process_trade_update(trade_update)

                    elif self.is_confirmed_new_order_filled_event(str(trade["trade_id"]),
                                                                  str(exchange_order_id),
                                                                  trading_pair):
                        # This is a fill of an order registered in the DB but not tracked anymore
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["trade_id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=trade_time,
                                order_id=self._exchange_order_ids.get(str(trade["order_id"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["side"] == "BUY" else TradeType.SELL,
                                order_type=OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["size"]),
                                trade_fee=fee,
                                exchange_trade_id=str(trade["trade_id"])
                            ))
                        self.logger().info(
                            f"Recreating missing trade {trade['side']} {trade['size']} {trading_pair} @ {trade['price']}")
                    else:
                        self.logger().debug(f"Trade without matching order_id and not in the DB: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Queries all trades for an order.
        https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getfills
        """
        trade_updates = []
        if order.exchange_order_id is not None:
            order_ids = []
            order_id: str = order.exchange_order_id
            order_ids.append(str(order_id))
            # product_id: str = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            params = {
                "order_ids": order_ids
            }
            all_fills_response: Dict[str, Any] = await self._api_get(
                path_url=constants.FILLS_EP,
                params=params,
                is_auth_required=True)

            for trade in all_fills_response["fills"]:
                exchange_order_id = trade["order_id"]
                quote_token: str = order.trading_pair.split("-")[1]
                if not isinstance(trade["trade_time"], float):
                    trade_time = float(get_timestamp_from_exchange_time(trade["trade_time"], "s"))
                else:
                    trade_time = trade["time"]
                fee = AddedToCostTradeFee(
                    percent_token=quote_token,
                    flat_fees=[TokenAmount(
                        amount=Decimal(trade["commission"]),
                        token=quote_token)])
                if trade["size_in_quote"] is True:
                    fill_quote_amount: Decimal = Decimal(trade["size"])
                    fill_base_amount: Decimal = Decimal(trade["size"]) / Decimal(trade["price"])
                else:
                    fill_base_amount: Decimal = Decimal(trade["size"])
                    fill_quote_amount: Decimal = Decimal(trade["size"]) * Decimal(trade["price"])
                trade_update = TradeUpdate(
                    trade_id=str(trade["trade_id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_quote_amount,
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade_time,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _api_post(self, *args, **kwargs):
        return await super()._api_post(*args, **kwargs)

    async def _api_get(self, *args, **kwargs):
        return await super()._api_get(*args, **kwargs)

    async def _make_network_check_request(self):
        self.logger().debug(f"Checking network status of {self.name} by querying server time.")
        await self._api_get(path_url=constants.SERVER_TIME_EP)

    async def _format_trading_rules(self, e: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_rules_request(self) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_pairs_request(self) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")
