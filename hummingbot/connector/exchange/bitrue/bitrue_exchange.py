import asyncio
from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from cachetools import TTLCache

from hummingbot.connector.constants import DAY, MINUTE, SECOND, TWELVE_HOURS, s_decimal_NaN
from hummingbot.connector.exchange.bitrue import (
    bitrue_constants as CONSTANTS,
    bitrue_utils,
    bitrue_web_utils as web_utils,
)
from hummingbot.connector.exchange.bitrue.bitrue_api_order_book_data_source import BitrueAPIOrderBookDataSource
from hummingbot.connector.exchange.bitrue.bitrue_auth import BitrueAuth
from hummingbot.connector.exchange.bitrue.bitrue_user_stream_data_source import BitrueUserStreamDataSource
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class BitrueExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    DEFAULT_DOMAIN = ""
    _BAD_REQUEST_HTTP_STATUS_CODE = 400

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        bitrue_api_key: str,
        bitrue_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = DEFAULT_DOMAIN,
    ):
        self.api_key = bitrue_api_key
        self.secret_key = bitrue_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trades_poll_bitrue_timestamp = 1.0
        self._rate_limits_polling_task: Optional[asyncio.Task] = None
        self._ws_trades_event_ids_by_token: Dict[str, TTLCache] = dict()

        self._max_trade_id_by_symbol: Dict[str, int] = dict()
        super().__init__(client_config_map=client_config_map)

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @staticmethod
    def bitrue_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(bitrue_type: str) -> OrderType:
        return OrderType[bitrue_type]

    @property
    def authenticator(self):
        return BitrueAuth(api_key=self.api_key, secret_key=self.secret_key, time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "bitrue"

    @property
    def rate_limits_rules(self):
        # Default rate limits - will be updated from exchange info afterwards
        return CONSTANTS.RATE_LIMITS

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
    def display_name(self) -> str:
        return self.name

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    async def _get_all_pairs_prices(self) -> Dict[str, Any]:
        results = {}
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        for pair_price_data in pairs_prices:
            results[pair_price_data["symbol"]] = {
                "best_bid": pair_price_data["bidPrice"],
                "best_ask": pair_price_data["askPrice"],
            }
        return results

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = (
            "-1021" in error_description and "Timestamp for this request" in error_description
        )
        return is_time_synchronizer_related

    def _is_request_result_an_error_related_to_time_synchronizer(self, request_result: Dict[str, Any]) -> bool:
        # The exchange returns a response failure and not a valid response
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_FOUND_ERROR_CODE) in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_FOUND_ERROR_CODE) in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitrueAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitrueUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def start_network(self):
        await super().start_network()
        self._rate_limits_polling_task = safe_ensure_future(self._rate_limits_polling_loop())

    async def stop_network(self):
        await super().stop_network()
        if self._rate_limits_polling_task is not None:
            self._rate_limits_polling_task.cancel()
            self._rate_limits_polling_task = None

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = True if is_maker is None else is_maker
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = BitrueExchange.bitrue_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {
            "symbol": symbol,
            "side": side_str,
            "type": type_str,
            "quantity": amount_str,
            "newClientOrderId": order_id,
            "price": price_str,
        }
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CREATE_ORDER_RATE_LIMIT_ID,
        )
        o_id = str(order_result["orderId"])
        transact_time = order_result["transactTime"]

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        ex_oid = await tracked_order.get_exchange_order_id()
        api_params = {
            "symbol": symbol,
            # "origClientOrderId": tracked_order.client_order_id,
            "orderId": ex_oid,
        }
        result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_RATE_LIMIT_ID,
        )
        return str(result.get("orderId")) == ex_oid

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "symbol": "ETHBTC",
            "status": "TRADING",
            "baseAsset": "ETH",
            "baseAssetPrecision": 8,
            "quoteAsset": "BTC",
            "quotePrecision": 8,
            "orderTypes": ["LIMIT", "MARKET"],
            "icebergAllowed": false,
            "filters": [{
                        "filterType": "PRICE_FILTER",
                        "minPrice": "0.666", // price >= minPrice
                        "maxPrice": "66.600",// price <= maxPrice
                        "tickSize": "0.01",  // price % tickSize == 0
                        "priceScale": 2
                    },
                    {
                        "filterType": "PERCENT_PRICE_BY_SIDE",
                        "bidMultiplierUp": "1.3",    // Order price <= bidMultiplierUp * lastPrice
                        "bidMultiplierDown": "0.1",  // Order price >= bidMultiplierDown * lastPrice
                        "askMultiplierUp": "10.0",   // Order Price <= askMultiplierUp * lastPrice
                        "askMultiplierDown": "0.7",  // Order Price >= askMultiplierDown * lastPrice
                        "avgPriceMins": "1"
                    },
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.1",  // quantity >= minQty
                        "minVal": "10.0", // quantity * lastPrice >= minVal
                        "maxQty": "999999999999999", // quantity <= maxQty
                        "stepSize": "0.01", // (quantity-minQty) % stepSize == 0
                        "volumeScale": 2
                    }]
        }
        """
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        retval = []
        for rule in filter(bitrue_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))
                filters = rule.get("filters")
                price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]

                min_order_size = Decimal(lot_size_filter.get("minQty"))
                tick_size = price_filter.get("tickSize")
                step_size = Decimal(lot_size_filter.get("stepSize"))
                min_notional = Decimal(lot_size_filter.get("minVal"))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=Decimal(str(tick_size)),
                        min_base_amount_increment=Decimal(str(step_size)),
                        min_notional_size=Decimal(str(min_notional)),
                    )
                )

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
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                # Refer to https://github.com/Bitrue-exchange/Spot-official-api-docs in websocket section
                if event_type in ("executionReport", "ORDER"):
                    order_status = event_message.get("X")
                    client_order_id = event_message.get("C")

                    if order_status in (2, 3):
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is not None:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=event_message["N"].upper(),
                                flat_fees=[
                                    TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"].upper())
                                ],
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(event_message["t"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["i"]),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(event_message["l"]),
                                fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
                                fill_price=Decimal(event_message["L"]),
                                fill_timestamp=event_message["T"] * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None and event_message["X"] != 0:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_message["E"] * 1e-3,
                            new_state=CONSTANTS.WS_ORDER_STATE.get(event_message["X"], OrderState.FAILED),
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message["i"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "BALANCE":
                    event_ts = int(event_message["E"])
                    balances = event_message["B"]
                    for balance_entry in balances:
                        # Balance message is incomplete when trade occurs, example:
                        # 'B': [{'a': 'usdt', 'F': '33.1869051824000000', 'T': 1704524454000,
                        # 'f': '13.3048484580000000', 't': 0}, {'a': 'eth', 'T': 0, 'L': '0.0000000000000000',
                        # 'l': '-0.006', 't': 1704524454000}]
                        asset_name = balance_entry["a"].upper()
                        # To prevent race condition on ws balance updates, check the event timestamp before proceeding
                        if asset_name not in self._ws_trades_event_ids_by_token:
                            self._ws_trades_event_ids_by_token[asset_name] = TTLCache(maxsize=1000, ttl=5)
                        if event_ts < max(self._ws_trades_event_ids_by_token[asset_name].values(), default=0):
                            continue
                        self._ws_trades_event_ids_by_token[asset_name][event_ts] = event_ts

                        # free = self._account_available_balances[asset_name]
                        if "F" in balance_entry:
                            free = Decimal(balance_entry["F"])
                            self._account_available_balances[asset_name] = free
                            # locked = self._account_balances[asset_name] - self._account_available_balances[asset_name]
                            if "L" in balance_entry:
                                locked = Decimal(balance_entry["L"])
                                self._account_balances[asset_name] = free + locked

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # We have overridden `_update_orders_fills` to utilize batch trade updates to reduce API limit consumption.
        # See implementation in `_request_batch_order_fills(...)` function.
        pass

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        if orders:
            # Since we are keeping the last trade id referenced to improve the query performance
            # it is necessary to evaluate updates for all possible fillable orders every time (to avoid loosing updates)
            candidate_orders = list(self._order_tracker.all_fillable_orders.values())
            try:
                if candidate_orders:
                    trade_updates = await self._all_trade_updates_for_orders(candidate_orders)
                    for trade_update in trade_updates:
                        self._order_tracker.process_trade_update(trade_update)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                order_ids = [order.client_order_id for order in candidate_orders]
                self.logger().warning(f"Failed to fetch trade updates for orders {order_ids}. Error: {request_error}")

    async def _all_trade_updates_for_orders(self, orders: List[InFlightOrder]) -> List[TradeUpdate]:
        # This endpoint is the only one on v2 for some reason
        url = CONSTANTS.REST_URL + CONSTANTS.MY_TRADES_PATH_URL
        symbols = {await self.exchange_symbol_associated_to_pair(trading_pair=o.trading_pair) for o in orders}
        trade_updates = []
        orders_to_process = {order.client_order_id: order for order in orders}
        for symbol in symbols:
            for _ in range(2):
                params = {"symbol": symbol, "limit": 1000}
                if symbol in self._max_trade_id_by_symbol:
                    params["fromId"] = self._max_trade_id_by_symbol[symbol]
                result = await self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params=params,
                    is_auth_required=True,
                    overwrite_url=url,
                )

                for trade_data in result:
                    if str(trade_data["orderId"]) in orders_to_process:
                        order = orders_to_process[str(trade_data["orderId"])]
                        fee_token = trade_data["commissionAsset"].upper()  # typo in the json by the exchange
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=bitrue_utils.DEFAULT_FEES,
                            trade_type=order.trade_type,
                            percent_token=fee_token,
                            flat_fees=[TokenAmount(amount=Decimal(trade_data["commission"]), token=fee_token)],
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade_data["tradeId"]),
                            client_order_id=order.client_order_id,
                            exchange_order_id=str(trade_data["id"]),
                            trading_pair=order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade_data["qty"]),
                            fill_quote_amount=Decimal(trade_data["qty"]) * Decimal(trade_data["price"]),
                            fill_price=Decimal(trade_data["price"]),
                            fill_timestamp=trade_data["time"] * 1e-3,
                        )
                        trade_updates.append(trade_update)
                if len(result) > 0:
                    self._max_trade_id_by_symbol[symbol] = max(int(t["tradeId"]) for t in result)
                if len(result) < 1000:
                    break

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={"symbol": trading_pair, "orderId": await tracked_order.get_exchange_order_id()},
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_STATUS_RATE_LIMIT_ID,
        )

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data["updateTime"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(path_url=CONSTANTS.ACCOUNTS_PATH_URL, is_auth_required=True)

        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            free_balance = Decimal(balance_entry["free"])
            total_balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["locked"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(bitrue_utils.is_exchange_information_valid, exchange_info["symbols"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(
                base=symbol_data["baseAsset"].upper(), quote=symbol_data["quoteAsset"].upper()
            )
        self._set_trading_pair_symbol_map(mapping)

    # === loops and sync related methods ===
    #
    async def _rate_limits_polling_loop(self):
        """
        Updates the rate limits by requesting the latest constraints from the exchange.
        Executes regularly every 12 hours
        """
        while True:
            try:
                await self._update_rate_limits()
                await self._sleep(TWELVE_HOURS)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching rate limits.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch new rate limits from {self.name_cap}"
                    " Check network connection.",
                )
                await self._sleep(0.5)

    async def _update_rate_limits(self):
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        self._initialize_rate_limits_from_exchange_info(exchange_info=exchange_info)

    def _initialize_rate_limits_from_exchange_info(self, exchange_info: Dict[str, Any]):
        # Update rate limits
        rate_limits_copy = deepcopy(self._throttler._rate_limits)
        for rate_limit in exchange_info["rateLimits"]:
            limit_id = None
            if rate_limit["prefix"] == CONSTANTS.GENERAL:
                limit_id = CONSTANTS.GENERAL
            elif rate_limit["prefix"] == CONSTANTS.ORDERS_IP:
                limit_id = CONSTANTS.ORDERS_IP
            elif rate_limit["prefix"] == CONSTANTS.ORDERS_USER:
                limit_id = CONSTANTS.ORDERS_USER
            else:
                continue

            interval = None
            if rate_limit["timeUnit"] == "SECONDS":
                interval = SECOND * rate_limit["timeCount"]
            if rate_limit["timeUnit"] == "MINUTES":
                interval = MINUTE * rate_limit["timeCount"]
            if rate_limit["timeUnit"] == "DAYS":
                interval = DAY * rate_limit["timeCount"]

            limit = rate_limit["burstCapacity"]

            if limit_id is not None and interval is not None:
                for r_l in rate_limits_copy:
                    if r_l.limit_id == limit_id:
                        rate_limits_copy.remove(r_l)
                rate_limits_copy.append(
                    RateLimit(
                        limit_id=limit_id,
                        limit=limit,
                        time_interval=interval,
                    )
                )
        self._throttler.set_rate_limits(rate_limits_copy)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}
        resp_json = await self._api_get(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, params=params)
        return float(resp_json[0]["lastPrice"])

    async def _get_all_market_symbol_orders(self, trading_pair: str) -> List[InFlightOrder]:
        in_flight_orders = []
        try:
            response = await self._api_get(
                path_url=CONSTANTS.OPEN_ORDERS_PATH_URL,
                params={"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)},
                is_auth_required=True,
            )
            order_type_mappings = {
                "LIMIT": OrderType.LIMIT,
                "MARKET": OrderType.MARKET,
            }
            trade_type_mapping = {"SELL": TradeType.SELL, "BUY": TradeType.BUY}
            for open_order in response:
                in_flight_orders.append(
                    InFlightOrder(
                        client_order_id=open_order.get("clientOrderId"),
                        trading_pair=trading_pair,
                        order_type=order_type_mappings[open_order["type"]],
                        trade_type=trade_type_mapping[open_order["side"]],
                        amount=Decimal(open_order["origQty"]),
                        creation_timestamp=int(open_order["time"]) * 1e-3,
                        price=Decimal(open_order["price"]),
                        exchange_order_id=str(open_order["orderId"]),
                        initial_state=CONSTANTS.ORDER_STATE[open_order["status"]],
                    )
                )
        except asyncio.CancelledError:
            raise
        return in_flight_orders

    async def _api_request(
        self,
        path_url,
        overwrite_url: Optional[str] = None,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:

        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()

        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)

        for _ in range(2):
            try:
                response = await rest_assistant.execute_request_and_get_response(
                    url=url,
                    throttler_limit_id=limit_id if limit_id else path_url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    timeout=None,
                    headers=None,
                )
                if self._BAD_REQUEST_HTTP_STATUS_CODE <= response.status and return_err:
                    error_response = await response.json()
                    return error_response

                # Defaults to using text
                result = await response.text()
                try:
                    result = await response.json()
                except Exception:
                    pass  # pass-through
                return result
            except IOError as request_exception:
                last_exception = request_exception
                if self._is_request_exception_related_to_time_synchronizer(request_exception=request_exception):
                    self._time_synchronizer.clear_time_offset_ms_samples()
                    await self._update_time_synchronizer()
                else:
                    raise

        # Failed even after the last retry
        raise last_exception
