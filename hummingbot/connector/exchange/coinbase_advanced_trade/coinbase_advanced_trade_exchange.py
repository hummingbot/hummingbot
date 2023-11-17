import asyncio
import decimal
import logging
import math
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Any, AsyncGenerator, AsyncIterable, Dict, Iterable, List, Tuple

from async_timeout import timeout
from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
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
from hummingbot.logger.indenting_logger import indented_debug_decorator

from . import coinbase_advanced_trade_constants as constants, coinbase_advanced_trade_web_utils as web_utils
from .coinbase_advanced_trade_api_order_book_data_source import CoinbaseAdvancedTradeAPIOrderBookDataSource
from .coinbase_advanced_trade_api_user_stream_data_source import (
    CoinbaseAdvancedTradeAPIUserStreamDataSource,
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from .coinbase_advanced_trade_auth import CoinbaseAdvancedTradeAuth
from .coinbase_advanced_trade_order_book import CoinbaseAdvancedTradeOrderBook
from .coinbase_advanced_trade_utils import DEFAULT_FEES
from .coinbase_advanced_trade_web_utils import (
    get_timestamp_from_exchange_time,
    retry_async_api_call,
    set_exchange_time_from_timestamp,
)

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinbaseAdvancedTradeExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    @indented_debug_decorator(msg="CoinbaseAdvancedTradeExchange", bullet=":")
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

        self._multi_stream_tracker: CoinbaseAdvancedTradeAPIUserStreamDataSource | None = None

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
        # return order_type.name.upper()

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
        # Websocket feed has 'PENDING' state, but REST API does not, it also seems to be for CREATE only
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

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

    @indented_debug_decorator(bullet="S")
    async def start_network(self):
        await self._initialize_market_assets()
        await self._update_trading_rules()
        await super().start_network()

    @indented_debug_decorator(bullet="T")
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

    @indented_debug_decorator(msg="User Stream Data Source", bullet=":")
    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        # self.logger().debug("Creating user stream data source.")
        self._multi_stream_tracker = CoinbaseAdvancedTradeAPIUserStreamDataSource(
            channels=("user",),
            pairs=tuple(self._trading_pairs),
            ws_factory=self._web_assistants_factory.get_ws_assistant,  # type: ignore
            ws_url=constants.WSS_URL.format(domain=self.domain),
            pair_to_symbol=partial(self.exchange_symbol_associated_to_pair),
            symbol_to_pair=partial(self.trading_pair_associated_to_exchange_symbol),
            heartbeat_channel="heartbeats",
        )
        return self._multi_stream_tracker

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

    @indented_debug_decorator(bullet="O")
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
        reference: https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
        Maximum open orders: 500
        """
        amount_str: str = f"{amount:f}"
        price_str: str = f"{price:f}"
        type_str: str = CoinbaseAdvancedTradeExchange.coinbase_advanced_trade_order_type(order_type)
        side_str: str = constants.SIDE_BUY if trade_type is TradeType.BUY else constants.SIDE_SELL
        symbol: str = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        if type_str == "LIMIT":
            order_configuration = {
                "limit_limit_gtc": {
                    "base_size": amount_str,
                    "limit_price": price_str
                }
            }
        elif type_str == "LIMIT_MAKER":
            order_configuration = {
                "limit_limit_gtc": {
                    "base_size": amount_str,
                    "limit_price": price_str,
                    "post_only": True
                }
            }
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
            o_id = str(order_result["order_id"])
            transact_time = self.time_synchronizer.time()
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

    @indented_debug_decorator(bullet="c")
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
            new_state=OrderState.PENDING_CREATE,
        )
        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    @indented_debug_decorator(bullet="C")
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
            tracked_order = []
            for o in order_ids:
                if t := self._order_tracker.fetch_tracked_order(o):
                    tracked_order.append((o, t))

            result = await self._execute_orders_cancel(orders=[t[1] for t in tracked_order if t[1] is not None])
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

    @indented_debug_decorator(bullet="E")
    async def _execute_orders_cancel(self, orders: List[InFlightOrder]) -> List[str]:
        try:
            cancelled: List[bool] = await self._execute_orders_cancel_and_process_update(orders=orders)
            return [order.client_order_id for order, cancelled in zip(orders, cancelled) if cancelled]

        except asyncio.CancelledError:
            raise

    @indented_debug_decorator(bullet="e")
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

    @indented_debug_decorator(bullet="Q")
    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
        """
        # Requesting to cancel an empty order seems to hang the request
        if (
                tracked_order.exchange_order_id is None or
                tracked_order.exchange_order_id == "" or
                tracked_order.exchange_order_id == "UNKNOWN"
        ):
            self.logger().warning(f"Failed to cancel order {order_id} without a "
                                  f"valid exchange_id: {tracked_order.exchange_order_id} in tracked_order:\n"
                                  f"{tracked_order}")
            return False
            # raise ValueError(f"This request is Invalid: _place_cancel with {order_id} {tracked_order.exchange_order_id}")

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

    @indented_debug_decorator(bullet="D")
    async def _place_cancels(self, order_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders

        """
        api_data = {
            "order_ids": order_ids
        }
        try:
            cancel_result: Dict[str, Any] = await self._api_post(
                path_url=constants.BATCH_CANCEL_EP,
                data=api_data,
                is_auth_required=True)
            results: List[Dict[str, Any]] = cancel_result.get("results", [])
            return results
        except IOError as e:
            self.logger().error(f"Error cancelling orders: {e}", exc_info=True)
            return [{"success": False, "failure_reason": "UNKNOWN_CANCEL_FAILURE_REASON"} for _ in order_ids]

    @indented_debug_decorator(bullet="s")
    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get a list of bids/asks for a single product.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproductbook

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

    @indented_debug_decorator(bullet="R")
    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Queries Order status by order_id.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder

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
    # @indented_debug_decorator( msg="Update Rules", bullet="U")
    async def _update_trading_rules(self):
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
                    min_order_size=Decimal(product.get("base_min_size", None)),
                    max_order_size=Decimal(product.get("base_max_size", None)),
                    min_price_increment=Decimal(product.get("quote_increment", None)),
                    min_base_amount_increment=Decimal(product.get("base_increment", None)),
                    min_quote_amount_increment=Decimal(product.get("quote_increment", None)),
                    min_notional_size=Decimal(product.get("quote_min_size", None)),
                    min_order_value=Decimal(product.get("base_min_size", None)) * Decimal(
                        product.get("price", None)),
                    max_price_significant_digits=Decimal(product.get("quote_increment", None)),
                    supports_limit_orders=product.get("supports_limit_orders", None),
                    supports_market_orders=product.get("supports_market_orders", None),
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
        # self.logger().debug(f"Setting trading pair symbol map to {list(trading_pair_symbol_map.items())[:5]}...")
        self._set_trading_pair_symbol_map(trading_pair_symbol_map)

    async def _initialize_trading_pair_symbol_map(self):
        # if not self._pair_symbol_map_initialized:
        await self._update_trading_rules()
        self._pair_symbol_map_initialized: bool = True

    async def _initialize_market_assets(self):
        """
        Fetch the list of trading pairs from the exchange and map them
        """
        try:
            params: Dict[str, Any] = {
                # "limit": 1,
                # "offset": 0,
                # "product_type": "SPOT",
            }
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

    @indented_debug_decorator(msg="Update Bal", bullet="B")
    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        # self.logger().debug(f"{local_asset_names} {remote_asset_names}")

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

    @indented_debug_decorator(msg="One page", bullet="l")
    async def _list_one_page_of_accounts(self, cursor: str) -> Dict[str, Any]:
        """
        List one page of accounts with maximum of 250 accounts per page.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
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

    @indented_debug_decorator(msg="List Accounts", bullet="A")
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

    @indented_debug_decorator(msg="Last price", bullet="P")
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

    def _stop_network(self):
        super()._stop_network()

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

            # self.logger().debug(f"Received: {event_message.client_order_id} {event_message.status}")

            fillable_order: InFlightOrder = self._order_tracker.all_fillable_orders.get(event_message.client_order_id)
            updatable_order: InFlightOrder = self._order_tracker.all_updatable_orders.get(
                event_message.client_order_id)

            new_state: OrderState = constants.ORDER_STATE[event_message.status]
            partially: bool = all((event_message.cumulative_base_amount > Decimal("0"),
                                   event_message.remainder_base_amount > Decimal("0"),
                                   new_state == OrderState.OPEN))
            new_state = OrderState.PARTIALLY_FILLED if partially else new_state

            if fillable_order is not None and any((
                    new_state == OrderState.OPEN,
                    new_state == OrderState.PARTIALLY_FILLED,
                    new_state == OrderState.FILLED,
            )):
                transaction_fee: Decimal = Decimal(event_message.cumulative_fee) - fillable_order.cumulative_fee_paid(
                    "USD")
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=DEFAULT_FEES,
                    trade_type=fillable_order.trade_type,
                    percent_token=fillable_order.quote_asset,
                    flat_fees=[TokenAmount(amount=Decimal(transaction_fee),
                                           token=fillable_order.quote_asset)]
                )

                avg_exc_price: Decimal | None = fillable_order.average_executed_price
                avg_exc_price: Decimal = avg_exc_price if avg_exc_price is not None else Decimal("0")
                fill_base_amount: Decimal = event_message.cumulative_base_amount - fillable_order.executed_amount_base
                if fill_base_amount == Decimal("0"):
                    fill_price: Decimal = avg_exc_price
                else:
                    total_price: Decimal = event_message.average_price * event_message.cumulative_base_amount
                    try:
                        fill_price: Decimal = (total_price - avg_exc_price) / fill_base_amount
                    except (ZeroDivisionError, decimal.InvalidOperation) as e:
                        raise ValueError(
                            "Fill base amount is zero for an InFlightOrder, this is unexpected"
                        ) from e

                trade_update = TradeUpdate(
                    trade_id="",  # Coinbase does not provide matching trade id
                    client_order_id=event_message.client_order_id,
                    exchange_order_id=event_message.exchange_order_id,
                    trading_pair=fillable_order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_base_amount * fill_price,
                    fill_price=fill_price,
                    fill_timestamp=event_message.fill_timestamp_s,
                )
                self._order_tracker.process_trade_update(trade_update)

            if updatable_order is not None:
                order_update = OrderUpdate(
                    trading_pair=updatable_order.trading_pair,
                    update_timestamp=event_message.fill_timestamp_s,
                    new_state=new_state,
                    client_order_id=event_message.client_order_id,
                    exchange_order_id=event_message.exchange_order_id,
                )
                self._order_tracker.process_order_update(order_update)

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Binance's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Binance's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick: float = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick: float = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick: float = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick: float = self.current_timestamp / self.LONG_POLL_INTERVAL

        in_flight_orders: Dict[str, InFlightOrder] = self.in_flight_orders

        if (long_interval_current_tick > long_interval_last_tick
                or (in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = set_exchange_time_from_timestamp(self._last_trades_poll_coinbase_advanced_trade_timestamp,
                                                          "s")
            self._last_trades_poll_coinbase_advanced_trade_timestamp = self.time_synchronizer.time()
            order_by_exchange_id_map = {
                order.exchange_order_id: order
                for order in self._order_tracker.all_fillable_orders.values()
            }
            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                product_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                params = {
                    "product_id": product_id
                }
                if self.last_poll_timestamp > 0:
                    params["start_sequence_timestamp"] = query_time
                tasks.append(self._api_get(
                    path_url=constants.FILLS_EP,
                    params=params,
                    is_auth_required=True))

            # self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")

            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
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
                    fee = AddedToCostTradeFee(
                        percent_token=quote_token,
                        flat_fees=[TokenAmount(
                            amount=Decimal(trade["commission"]),
                            token=quote_token)])
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
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Queries all trades for an order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
        """
        trade_updates = []
        if order.exchange_order_id is not None:
            # self.logger().debug(f"Fetching all trades for order {order.client_order_id}/{order.exchange_order_id}")
            order_id: str = order.exchange_order_id
            product_id: str = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            params = {
                "product_id": product_id,
                "order_id": order_id
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

    @retry_async_api_call()
    async def _api_post(self, *args, **kwargs):
        return await super()._api_post(*args, **kwargs)

    @retry_async_api_call()
    async def _api_get(self, *args, **kwargs):
        return await super()._api_get(*args, **kwargs)

    async def _make_network_check_request(self):
        await self._api_get(path_url=constants.SERVER_TIME_EP, is_auth_required=False)

    async def _format_trading_rules(self, e: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_rules_request(self) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_pairs_request(self) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")
