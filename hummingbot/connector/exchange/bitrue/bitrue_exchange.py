import asyncio
import gzip
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bitrue import (
    bitrue_constants as CONSTANTS,
    bitrue_utils,
    bitrue_web_utils as web_utils,
)
from hummingbot.connector.exchange.bitrue.bitrue_api_order_book_data_source import BitrueAPIOrderBookDataSource
from hummingbot.connector.exchange.bitrue.bitrue_api_user_stream_data_source import BitrueAPIUserStreamDataSource
from hummingbot.connector.exchange.bitrue.bitrue_auth import BitrueAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class BitrueExchange(ExchangePyBase):
    # SHORT_POLL_INTERVAL = 3.0
    # LONG_POLL_INTERVAL = 3.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 bitrue_api_key: str,
                 bitrue_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = bitrue_api_key
        self.secret_key = bitrue_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_bitrue_timestamp = 1.0
        super().__init__(client_config_map)

    @staticmethod
    def bitrue_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(bitrue_type: str) -> OrderType:
        return OrderType[bitrue_type]

    @property
    def authenticator(self):
        return BitrueAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "bitrue_main":
            return "bitrue"
        else:
            return f"bitrue_{self._domain}"

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
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return any(str(code) in str(request_exception) for code in CONSTANTS.TIME_SYNC_ERROR_CODES) and \
            "timestamp" in str(request_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return any(str(code) in str(status_update_exception) for code in CONSTANTS.ORDER_NOT_EXIST_ERROR_CODES)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return any(str(code) in str(cancelation_exception) for code in CONSTANTS.UNKNOWN_ORDER_ERROR_CODES)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitrueAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitrueAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
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
        is_maker = order_type is OrderType.LIMIT
        trade_base_fee = build_trade_fee(
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
        order_result = None
        amount_str = f"{amount:f}"
        type_str = BitrueExchange.bitrue_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"symbol": symbol,
                      "side": side_str,
                      "quantity": amount_str,
                      "type": type_str,
                      "newClientOrderId": order_id}
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            price_str = f"{price:f}"
            api_params["price"] = price_str
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result["orderId"])
            transact_time = order_result["transactTime"] * 1e-3
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description)
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = self._time_synchronizer.time()
            else:
                raise
        return (o_id, transact_time)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "origClientOrderId": order_id,
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True)
        if cancel_result.get("origClientOrderId") == order_id:
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "symbol": "ETHBTC",
            "baseAssetPrecision": 8,
            "quotePrecision": 8,
            "orderTypes": ["LIMIT", "MARKET"],
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.00000100",
                    "maxPrice": "100000.00000000",
                    "tickSize": "0.00000100"
                }, {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00100000",
                    "maxQty": "100000.00000000",
                    "minVal": "10.0",
                    "stepSize": "0.00100000"
                }
            ]
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
                min_value = Decimal(lot_size_filter.get("minVal"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(step_size),
                                min_notional_size=min_value))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _update_order_fills_from_trades(self):

        query_time = int(self._last_trades_poll_bitrue_timestamp * 1e3)
        self._last_trades_poll_bitrue_timestamp = self._time_synchronizer.time()
        order_by_exchange_id_map = {}
        for order in self._order_tracker.all_fillable_orders.values():
            if order.exchange_order_id is not None:     # ones which already have exchange_order_id
                order_by_exchange_id_map[order.exchange_order_id] = order

        tasks = []
        trading_pairs = self.trading_pairs
        for trading_pair in trading_pairs:
            params = {
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                "limit": 1000,
            }
            if self._last_poll_timestamp > 0:
                params["startTime"] = query_time
            tasks.append(self._api_get(
                "",  # path_url is not used, using overwrite_url instead
                overwrite_url=f"{CONSTANTS.REST_URL}{CONSTANTS.PRIVATE_API_VERSION_V2}/{CONSTANTS.MY_TRADES_PATH_URL}",
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL))

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
                exchange_order_id = str(trade["orderId"])
                if exchange_order_id in order_by_exchange_id_map:
                    # This is a fill for a tracked order
                    tracked_order = order_by_exchange_id_map[exchange_order_id]
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        percent_token=trade["commissionAssert"].upper(),    # it's actually misspelled in the API as "commissionAssert"
                        flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAssert"].upper())]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade["tradeId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["qty"]),
                        fill_quote_amount=Decimal(trade["qty"]) * Decimal(trade["price"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=trade["time"] * 1e-3,
                    )
                    self._order_tracker.process_trade_update(trade_update)
                elif self.is_confirmed_new_order_filled_event(str(trade["tradeId"]), exchange_order_id, trading_pair):
                    # This is a fill of an order registered in the DB but not tracked any more
                    self._current_trade_fills.add(TradeFillOrderDetails(
                        market=self.display_name,
                        exchange_trade_id=str(trade["tradeId"]),
                        symbol=trading_pair))
                    self.trigger_event(
                        MarketEvent.OrderFilled,
                        OrderFilledEvent(
                            timestamp=float(trade["time"]) * 1e-3,
                            order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
                            trading_pair=trading_pair,
                            trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                            order_type=OrderType.LIMIT if trade["isMaker"] else OrderType.MARKET,    # Bitrue doesn't have LIMIT_MAKER orders
                            price=Decimal(trade["price"]),
                            amount=Decimal(trade["qty"]),
                            trade_fee=DeductedFromReturnsTradeFee(
                                flat_fees=[
                                    TokenAmount(
                                        trade["commissionAssert"].upper(),    # it's actually misspelled in the API as "commissionAsser
                                        Decimal(trade["commission"])
                                    )
                                ]
                            ),
                            exchange_trade_id=str(trade["tradeId"])
                        ))
                    self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                # Refer to https://github.com/Bitrue-exchange/Spot-official-api-docs#user-data-streams-websocketafter-2021-11-05
                # As per the order update section in Bitrue the ID of the order being canceled is under the "C" key
                if event_type == "ORDER":
                    execution_type = CONSTANTS.ORDER_EVENT[int(event_message.get("x"))]
                    client_order_id = event_message.get("C")

                    if execution_type == "TRADE" and int(event_message.get("t", -1)) != -1:
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is not None:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=event_message["N"].upper(),
                                flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"].upper())]
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
                    if tracked_order is not None:
                        # NEW is already assumed on order creation, if the order on exchange fails to be created, it will be noted as such fromm the user stream event
                        order_state = CONSTANTS.ORDER_STATE_WS[int(event_message["X"])]
                        if order_state == CONSTANTS.OrderState.OPEN or order_state == CONSTANTS.OrderState.PENDING_CREATE:
                            order_state = tracked_order.current_state

                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_message["E"] * 1e-3,
                            new_state=order_state,
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message["i"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "BALANCE" or event_type == "OutboundAccountPositionOrderEvent":
                    balances = event_message["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"].upper()
                        free_balance = balance_entry.get("F", None)
                        locked_balance = balance_entry.get("L", None)

                        if free_balance is None or locked_balance is None:
                            # If either free or locked balance is missing, we need to update all balances
                            if free_balance is not None:
                                self._account_available_balances[asset_name] = Decimal(free_balance)
                            if locked_balance is not None:
                                locked_balance_diff = Decimal(balance_entry["l"])
                                self._account_available_balances[asset_name] -= locked_balance_diff
                        else:
                            total_balance = Decimal(free_balance) + Decimal(locked_balance)
                            self._account_available_balances[asset_name] = Decimal(free_balance)
                            self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        # Bitrue doesn't have a way to get all trades for an order, so we have to get the order status and
        # then get the trades from _update_order_fills_from_trades

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        params = {
            "symbol": trading_pair,
            "orderId": await tracked_order.get_exchange_order_id(),
            "origClientOrderId": tracked_order.client_order_id
        }

        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=params,
            is_auth_required=True)

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        # NEW is already assumed on order creation, if the order on exchange fails to be created, it will be noted as such fromm the user stream event
        if new_state == CONSTANTS.OrderState.OPEN or new_state == CONSTANTS.OrderState.PENDING_CREATE:
            new_state = tracked_order.current_state

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

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True)

        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["asset"].upper()
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
            mapping[symbol_data["symbol"].upper()] = combine_to_hb_trading_pair(base=symbol_data["baseAsset"].upper(),
                                                                                quote=symbol_data["quoteAsset"].upper())
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        )

        return float(resp_json["price"])

    async def _api_request(self,
                           path_url,
                           overwrite_url: Optional[str] = None,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)
        local_headers = {
            "Content-Type": "application/x-www-form-urlencoded"}
        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    headers=local_headers,
                    throttler_limit_id=limit_id if limit_id else path_url,
                )
                return request_result
            except IOError as request_exception:
                last_exception = request_exception
                if self._is_request_exception_related_to_time_synchronizer(request_exception=request_exception):
                    self._time_synchronizer.clear_time_offset_ms_samples()
                    await self._update_time_synchronizer()
                else:
                    raise

        # Failed even after the last retry
        raise last_exception

    def decompress_ws_data(self, raw_msg: str) -> Dict[str, Any]:
        msg_str = gzip.decompress(raw_msg).decode("utf-8")
        msg = json.loads(msg_str)
        return msg
