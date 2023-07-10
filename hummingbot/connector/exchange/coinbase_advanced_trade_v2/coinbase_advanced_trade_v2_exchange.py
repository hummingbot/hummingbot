import decimal
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Generator, Iterable, List, Optional, Tuple, cast

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

from ...client_order_tracker import ClientOrderTracker
from ...time_synchronizer import TimeSynchronizer
from ...utils import TradeFillOrderDetails
from . import coinbase_advanced_trade_v2_constants as constants, coinbase_advanced_trade_v2_web_utils as web_utils
from .coinbase_advanced_trade_v2_api_order_book_data_source import CoinbaseAdvancedTradeV2APIOrderBookDataSource
from .coinbase_advanced_trade_v2_api_user_stream_data_source import (
    CoinbaseAdvancedTradeV2APIUserStreamDataSource,
    CoinbaseAdvancedTradeV2CumulativeUpdate,
)
from .coinbase_advanced_trade_v2_auth import CoinbaseAdvancedTradeV2Auth
from .coinbase_advanced_trade_v2_utils import DEFAULT_FEES
from .coinbase_advanced_trade_v2_web_utils import get_timestamp_from_exchange_time, set_exchange_time_from_timestamp

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinbaseAdvancedTradeV2Exchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 coinbase_advanced_trade_v2_api_key: str,
                 coinbase_advanced_trade_v2_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = constants.DEFAULT_DOMAIN,
                 ):
        self._api_key = coinbase_advanced_trade_v2_api_key
        self.secret_key = coinbase_advanced_trade_v2_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_coinbase_advanced_trade_v2_timestamp = -1
        super().__init__(client_config_map)

        self._asset_uuid_map: Dict[str, str] = {}
        self._pair_symbol_map_initialized = False

    @property
    def asset_uuid_map(self) -> Dict[str, str]:
        return self._asset_uuid_map

    @staticmethod
    def coinbase_advanced_trade_v2_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(coinbase_advanced_trade_v2_type: str) -> OrderType:
        return OrderType[coinbase_advanced_trade_v2_type]

    @property
    def authenticator(self):
        return CoinbaseAdvancedTradeV2Auth(
            api_key=self._api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "coinbase_advanced_trade_v2"
        else:
            return f"coinbase_advanced_trade_v2_{self._domain}"

    @property
    def rate_limits_rules(self):
        return constants.RATE_LIMITS

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
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def order_tracker(self) -> ClientOrderTracker:
        # Defined in ExchangePyBase
        return self._order_tracker

    @property
    def exchange_order_ids(self) -> ClientOrderTracker:
        # Defined in ExchangePyBase
        return self._exchange_order_ids

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
        return CoinbaseAdvancedTradeV2APIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinbaseAdvancedTradeV2APIUserStreamDataSource(
            auth=cast(CoinbaseAdvancedTradeV2Auth, self._auth),
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return constants.ORDER_STATUS_NOT_FOUND_ERROR_CODE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "UNKNOWN_CANCEL_ORDER" in str(cancelation_exception)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return AddedToCostTradeFee(DEFAULT_FEES)

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
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = CoinbaseAdvancedTradeV2Exchange.coinbase_advanced_trade_v2_order_type(order_type)
        side_str = constants.SIDE_BUY if trade_type is TradeType.BUY else constants.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        if type_str == "MARKET":
            order_configuration = {
                "market_market_ioc": {
                    "base_size": amount_str,
                }
            }
        elif type_str == "LIMIT":
            order_configuration = {
                "limit_limit_gtc": {
                    "base_size": amount_str,
                    "limit_price": price_str,
                    "post_only": False
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
        else:
            raise ValueError(f"Invalid order type {order_type}.")

        api_params = {
            "client_order_id": order_id,
            "product_id": symbol,
            "side": side_str,
            "order_configuration": order_configuration
        }

        try:
            order_result = await self._api_post(
                path_url=constants.ORDER_EP,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result["order_id"])
            transact_time = self.time_synchronizer.time()
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = self._time_synchronizer.time()
            else:
                raise
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders
        """
        # Coinbase Advanced Trade seems to require the exchange order ID to cancel an order
        result = await self._place_cancels(order_ids=[tracked_order.exchange_order_id])
        if result[0]["success"]:
            return True
        else:
            if result[0]["failure_reason"] == "UNKNOWN_CANCEL_ORDER":
                # return False
                raise Exception(
                    f"Order {order_id}:{tracked_order.exchange_order_id} not found on the exchange. UNKNOWN_CANCEL_ORDER")

    async def _place_cancels(self, order_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders

        """
        api_data = {
            "order_ids": order_ids
        }
        cancel_result: Dict[str, Any] = await self._api_post(
            path_url=constants.BATCH_CANCEL_EP,
            data=api_data,
            is_auth_required=True)

        return [r for r in cancel_result["results"]]

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Queries Order status by order_id.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder

        """
        updated_order_data = await self._api_get(
            path_url=constants.GET_ORDER_STATUS_EP.format(order_id=tracked_order.exchange_order_id),
            params={},
            is_auth_required=True,
            limit_id=constants.GET_ORDER_STATUS_RATE_LIMIT_ID,
        )

        status: str = updated_order_data['order']["status"]
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
    async def _update_trading_rules(self):
        self.trading_rules.clear()
        trading_pair_symbol_map: Dict[str, str] = {}
        products: Generator[dict[str, Any], Any, None] = await self._initialize_market_assets()

        if products is None:
            return

        for product in products:
            # Coinbase Advanced Trade API returns the trading pair in the format of "BASE-QUOTE"
            trading_pair: str = product.get("product_id")
            try:
                trading_rule: TradingRule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(product.get("base_min_size"), None),
                    max_order_size=Decimal(product.get("base_max_size", None)),
                    min_price_increment=Decimal(product.get("quote_increment", None)),
                    min_base_amount_increment=Decimal(product.get("base_increment", None)),
                    min_quote_amount_increment=Decimal(product.get("quote_increment", None)),
                    min_notional_size=Decimal(product.get("quote_min_size", None)),
                    min_order_value=Decimal(product.get("base_min_size", None)) * Decimal(product.get("price", None)),
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
        self._set_trading_pair_symbol_map(trading_pair_symbol_map)

    async def _initialize_trading_pair_symbol_map(self):
        if not self._pair_symbol_map_initialized:
            await self._update_trading_rules()
            self._pair_symbol_map_initialized: bool = True

    async def _initialize_market_assets(self) -> Generator[Dict[str, Any], Any, None]:
        """
        Fetch the list of trading pairs from the exchange and map them
        """
        try:
            products: Dict[str, Any] = await self._api_get(path_url=constants.ALL_PAIRS_EP, is_auth_required=True)
            return (p for p in products.get("products") if all((p.get("product_type", None) == "SPOT",
                                                                p.get("trading_disabled", None) is False,
                                                                p.get("is_disabled", None) is False,
                                                                p.get("cancel_only", None) is False,
                                                                p.get("auction_mode", None) is False)))
        except Exception:
            self.logger().exception("Error getting all trading pairs from Coinbase Advanced Trade.")

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

        trade: Dict[str, Any] = await self._api_get(
            path_url=constants.PAIR_TICKER_24HR_EP.format(product_id=product_id) + "?limit=1",
            limit_id=constants.PAIR_TICKER_24HR_RATE_LIMIT_ID,
            is_auth_required=True
        )
        return float(trade.get("trades")[0]["price"])

    async def get_all_pairs_prices(self) -> Generator[dict[Any, Any], Any, None]:
        """
        Fetches the prices of all symbols in the exchange with a default quote of USD
        """
        products: List[Dict[str, Any]] = await self._api_get(path_url=constants.ALL_PAIRS_EP, is_auth_required=True)
        return ({p.get("product_id"): p.get("price")} for p in products if all((p.get("product_type", None) == "SPOT",
                                                                                p.get("trading_disabled",
                                                                                      None) is False,
                                                                                p.get("is_disabled", None) is False,
                                                                                p.get("cancel_only", None) is False,
                                                                                p.get("auction_mode", None) is False)))

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        fees: Dict[str, Any] = await self._api_request("get", constants.TRANSACTIONS_SUMMARY_EP, is_auth_required=True)
        self._trading_fees = fees

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are order updates.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                assert isinstance(event_message, CoinbaseAdvancedTradeV2CumulativeUpdate)
            except AssertionError:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)
                continue

            fillable_order: InFlightOrder = self.order_tracker.all_fillable_orders.get(event_message.client_order_id)
            updatable_order: InFlightOrder = self.order_tracker.all_updatable_orders.get(
                event_message.client_order_id)

            new_state: OrderState = constants.ORDER_STATE[event_message.status]
            partial: bool = all((event_message.cumulative_base_amount > Decimal("0"),
                                 event_message.remainder_base_amount > Decimal("0"),
                                 new_state == OrderState.OPEN))
            new_state = OrderState.PARTIALLY_FILLED if partial else new_state

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
                    percent_token="USD",
                    flat_fees=[TokenAmount(amount=Decimal(transaction_fee), token="USD")]
                )

                avg_exc_price: Optional[Decimal] = fillable_order.average_executed_price
                avg_exc_price: Decimal = avg_exc_price if avg_exc_price is not None else Decimal("0")
                fill_base_amount: Decimal = event_message.cumulative_base_amount - fillable_order.executed_amount_base
                if fill_base_amount == Decimal("0"):
                    fill_price: Decimal = avg_exc_price
                else:
                    total_price: Decimal = event_message.average_price * event_message.cumulative_base_amount
                    try:
                        fill_price: Decimal = (total_price - avg_exc_price) / fill_base_amount
                    except (ZeroDivisionError, decimal.InvalidOperation):
                        raise ValueError("Fill base amount is zero for an InFlightOrder, this is unexpected")

                trade_update = TradeUpdate(
                    trade_id="",  # Coinbase does not provide matching trade id
                    client_order_id=event_message.client_order_id,
                    exchange_order_id=event_message.exchange_order_id,
                    trading_pair=fillable_order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_base_amount * fill_price,
                    fill_price=fill_price,
                    fill_timestamp=event_message.fill_timestamp,
                )
                self.order_tracker.process_trade_update(trade_update)

            if updatable_order is not None:
                order_update = OrderUpdate(
                    trading_pair=updatable_order.trading_pair,
                    update_timestamp=event_message.fill_timestamp,
                    new_state=new_state,
                    client_order_id=event_message.client_order_id,
                    exchange_order_id=event_message.exchange_order_id,
                )
                self.order_tracker.process_order_update(order_update)

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
            query_time = set_exchange_time_from_timestamp(self._last_trades_poll_coinbase_advanced_trade_v2_timestamp,
                                                          "s")
            self._last_trades_poll_coinbase_advanced_trade_v2_timestamp = self.time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self.order_tracker.all_fillable_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

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

            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    exchange_order_id = trade["order_id"]
                    quote_token: str = trading_pair.split("-")[1]
                    fee = AddedToCostTradeFee(flat_fees=[TokenAmount(amount=Decimal(trade["commission"]),
                                                                     token=quote_token)])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        trade_update = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["size"]),
                            fill_quote_amount=Decimal("0" if trade["size_in_quote"] is True else trade["size"]),
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=trade["trade_time"],
                            is_taker=False
                        )
                        self.order_tracker.process_trade_update(trade_update)

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
                                timestamp=float(get_timestamp_from_exchange_time(trade["trade_time"], "s")),
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
            order_id = int(order.exchange_order_id)
            product_id = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response: Dict[str, Any] = await self._api_get(
                path_url=constants.FILLS_EP,
                params={
                    "product_id": product_id,
                    "order_id": order_id
                },
                is_auth_required=True)

            for trade in all_fills_response["fills"]:
                exchange_order_id = trade["order_id"]
                quote_token: str = order.trading_pair.split("-")[1]
                fee = AddedToCostTradeFee(flat_fees=[TokenAmount(amount=Decimal(trade["commission"]),
                                                                 token=quote_token)])
                trade_update = TradeUpdate(
                    trade_id=str(trade["trade_id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["size"]),
                    fill_quote_amount=Decimal("0" if trade["size_in_quote"] is True else trade["size"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["trade_time"],
                )
                trade_updates.append(trade_update)

        return trade_updates

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
