import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.weex import (
    weex_constants as CONSTANTS,
    weex_utils,
    weex_web_utils as web_utils,
)
from hummingbot.connector.exchange.weex.weex_api_order_book_data_source import WeexAPIOrderBookDataSource
from hummingbot.connector.exchange.weex.weex_api_user_stream_data_source import WeexAPIUserStreamDataSource
from hummingbot.connector.exchange.weex.weex_auth import WeexAuth
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
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class WeexExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 weex_api_key: str,
                 weex_api_secret: str,
                 weex_api_passphrase: str = "",
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = weex_api_key
        self.secret_key = weex_api_secret
        self.api_passphrase = weex_api_passphrase
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_weex_timestamp = 1.0
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @staticmethod
    def weex_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(weex_type: str) -> OrderType:
        return OrderType[weex_type]

    @property
    def authenticator(self):
        return WeexAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.api_passphrase,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "weex"
        else:
            return f"weex_{self._domain}"

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
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.TRADING_PAIRS_PATH_URL


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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pass
    #     pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
    #     return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        pass
    #     error_description = str(request_exception)
    #     is_time_synchronizer_related = ("-1021" in error_description
    #                                     and "Timestamp for this request" in error_description)
    #     return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        pass
    #     return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
    #         status_update_exception
    #     ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        pass
    #     return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
    #         cancelation_exception
    #     ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,   # harmless if absorbed
            auth=self._auth
        )


    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return WeexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return WeexAPIUserStreamDataSource(
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
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

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
        type_str = WeexExchange.weex_order_type(order_type)
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
                path_url=CONSTANTS.CREATE_ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True,
                limit_id=CONSTANTS.CREATE_ORDER_LIMIT_ID)
            o_id = str(order_result["orderId"])
            transact_time = order_result["transactTime"] * 1e-3
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
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "origClientOrderId": order_id,
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID)
        if cancel_result.get("status") == "CANCELED":
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules: List[TradingRule] = []

        for item in exchange_info_dict.get("data", []):
            if not item.get("enableTrade", False):
                continue

            symbol = item["symbol"]
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)

            rules.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(item["minTradeAmount"]),
                    min_price_increment=Decimal(item["tickSize"]),
                    min_base_amount_increment=Decimal(item["stepSize"]),
                    min_notional_size=Decimal("0"),  # WEEX did not provide min notional in this payload
                )
            )

        return rules



    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        pass
    #     """
    #     This functions runs in background continuously processing the events received from the exchange by the user
    #     stream data source. It keeps reading events from the queue until the task is interrupted.
    #     The events received are balance updates, order updates and trade events.
    #     """
    #     async for event_message in self._iter_user_event_queue():
    #         try:
    #             event_type = event_message.get("e")
    #             # Refer to https://github.com/weex-exchange/weex-official-api-docs/blob/master/user-data-stream.md
    #             # As per the order update section in Weex the ID of the order being canceled is under the "C" key
    #             if event_type == "executionReport":
    #                 execution_type = event_message.get("x")
    #                 if execution_type != "CANCELED":
    #                     client_order_id = event_message.get("c")
    #                 else:
    #                     client_order_id = event_message.get("C")

    #                 if execution_type == "TRADE":
    #                     tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
    #                     if tracked_order is not None:
    #                         fee = TradeFeeBase.new_spot_fee(
    #                             fee_schema=self.trade_fee_schema(),
    #                             trade_type=tracked_order.trade_type,
    #                             percent_token=event_message["N"],
    #                             flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])]
    #                         )
    #                         trade_update = TradeUpdate(
    #                             trade_id=str(event_message["t"]),
    #                             client_order_id=client_order_id,
    #                             exchange_order_id=str(event_message["i"]),
    #                             trading_pair=tracked_order.trading_pair,
    #                             fee=fee,
    #                             fill_base_amount=Decimal(event_message["l"]),
    #                             fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
    #                             fill_price=Decimal(event_message["L"]),
    #                             fill_timestamp=event_message["T"] * 1e-3,
    #                         )
    #                         self._order_tracker.process_trade_update(trade_update)

    #                 tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
    #                 if tracked_order is not None:
    #                     order_update = OrderUpdate(
    #                         trading_pair=tracked_order.trading_pair,
    #                         update_timestamp=event_message["E"] * 1e-3,
    #                         new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
    #                         client_order_id=client_order_id,
    #                         exchange_order_id=str(event_message["i"]),
    #                     )
    #                     self._order_tracker.process_order_update(order_update=order_update)

    #             elif event_type == "outboundAccountPosition":
    #                 balances = event_message["B"]
    #                 for balance_entry in balances:
    #                     asset_name = balance_entry["a"]
    #                     free_balance = Decimal(balance_entry["f"])
    #                     total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
    #                     self._account_available_balances[asset_name] = free_balance
    #                     self._account_balances[asset_name] = total_balance

    #         except asyncio.CancelledError:
    #             raise
    #         except Exception:
    #             self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
    #             await self._sleep(5.0)

    async def _update_order_fills_from_trades(self):
        pass
    #     """
    #     This is intended to be a backup measure to get filled events with trade ID for orders,
    #     in case Weex's user stream events are not working.
    #     NOTE: It is not required to copy this functionality in other connectors.
    #     This is separated from _update_order_status which only updates the order status without producing filled
    #     events, since Weex's get order endpoint does not return trade IDs.
    #     The minimum poll interval for order status is 10 seconds.
    #     """
    #     small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
    #     small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
    #     long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
    #     long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

    #     if (long_interval_current_tick > long_interval_last_tick
    #             or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
    #         query_time = int(self._last_trades_poll_weex_timestamp * 1e3)
    #         self._last_trades_poll_weex_timestamp = self._time_synchronizer.time()
    #         order_by_exchange_id_map = {}
    #         for order in self._order_tracker.all_fillable_orders.values():
    #             order_by_exchange_id_map[order.exchange_order_id] = order

    #         tasks = []
    #         trading_pairs = self.trading_pairs
    #         for trading_pair in trading_pairs:
    #             params = {
    #                 "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
    #             }
    #             if self._last_poll_timestamp > 0:
    #                 params["startTime"] = query_time
    #             tasks.append(self._api_get(
    #                 path_url=CONSTANTS.MY_TRADES_PATH_URL,
    #                 params=params,
    #                 is_auth_required=True))

    #         self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
    #         results = await safe_gather(*tasks, return_exceptions=True)

    #         for trades, trading_pair in zip(results, trading_pairs):

    #             if isinstance(trades, Exception):
    #                 self.logger().network(
    #                     f"Error fetching trades update for the order {trading_pair}: {trades}.",
    #                     app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
    #                 )
    #                 continue
    #             for trade in trades:
    #                 exchange_order_id = str(trade["orderId"])
    #                 if exchange_order_id in order_by_exchange_id_map:
    #                     # This is a fill for a tracked order
    #                     tracked_order = order_by_exchange_id_map[exchange_order_id]
    #                     fee = TradeFeeBase.new_spot_fee(
    #                         fee_schema=self.trade_fee_schema(),
    #                         trade_type=tracked_order.trade_type,
    #                         percent_token=trade["commissionAsset"],
    #                         flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
    #                     )
    #                     trade_update = TradeUpdate(
    #                         trade_id=str(trade["id"]),
    #                         client_order_id=tracked_order.client_order_id,
    #                         exchange_order_id=exchange_order_id,
    #                         trading_pair=trading_pair,
    #                         fee=fee,
    #                         fill_base_amount=Decimal(trade["qty"]),
    #                         fill_quote_amount=Decimal(trade["quoteQty"]),
    #                         fill_price=Decimal(trade["price"]),
    #                         fill_timestamp=trade["time"] * 1e-3,
    #                     )
    #                     self._order_tracker.process_trade_update(trade_update)
    #                 elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
    #                     # This is a fill of an order registered in the DB but not tracked any more
    #                     self._current_trade_fills.add(TradeFillOrderDetails(
    #                         market=self.display_name,
    #                         exchange_trade_id=str(trade["id"]),
    #                         symbol=trading_pair))
    #                     self.trigger_event(
    #                         MarketEvent.OrderFilled,
    #                         OrderFilledEvent(
    #                             timestamp=float(trade["time"]) * 1e-3,
    #                             order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
    #                             trading_pair=trading_pair,
    #                             trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
    #                             order_type=OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
    #                             price=Decimal(trade["price"]),
    #                             amount=Decimal(trade["qty"]),
    #                             trade_fee=DeductedFromReturnsTradeFee(
    #                                 flat_fees=[
    #                                     TokenAmount(
    #                                         trade["commissionAsset"],
    #                                         Decimal(trade["commission"])
    #                                     )
    #                                 ]
    #                             ),
    #                             exchange_trade_id=str(trade["id"])
    #                         ))
    #                     self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_LIMIT_ID)

            for trade in all_fills_response:
                exchange_order_id = str(trade["orderId"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["commissionAsset"],
                    flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["qty"]),
                    fill_quote_amount=Decimal(trade["quoteQty"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            params={
                "symbol": trading_pair,
                "origClientOrderId": tracked_order.client_order_id},
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID)

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

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.ACCOUNTS_LIMIT_ID)

        balances = account_info["data"]
        for balance_entry in balances:
            asset_name = balance_entry["coinName"]
            free_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["available"]) + Decimal(balance_entry["frozen"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    KNOWN_QUOTES = ("USDT", "USDC", "BTC", "ETH", "EUR", "TRY", "BRL")

    def weex_symbol_to_hb_pair(symbol: str) -> str:
        # BTCUSDT_SPBL -> BTCUSDT
        core = symbol[:-5]  # drop "_SPBL"
        for q in KNOWN_QUOTES:
            if core.endswith(q) and len(core) > len(q):
                base = core[:-len(q)]
                quote = q
                return f"{base}-{quote}"
        raise ValueError(f"Cannot infer quote from WEEX symbol: {symbol}")


    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for item in exchange_info.get("data", []):
            symbol = item["symbol"]
            hb_pair = combine_to_hb_trading_pair(base=item["baseCoin"], quote=item["quoteCoin"])
            mapping[symbol] = hb_pair
        self._set_trading_pair_symbol_map(mapping)




    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONS,
            limit_id=CONSTANTS.TICKER_PRICE_CHANGE_LIMIT_IDTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        )

        return float(resp_json["lastPrice"])
