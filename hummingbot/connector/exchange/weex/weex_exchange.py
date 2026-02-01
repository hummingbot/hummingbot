import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS, weex_utils, weex_web_utils as web_utils
from hummingbot.connector.exchange.weex.weex_api_order_book_data_source import WeexAPIOrderBookDataSource
from hummingbot.connector.exchange.weex.weex_api_user_stream_data_source import WeexAPIUserStreamDataSource
from hummingbot.connector.exchange.weex.weex_auth import WeexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
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
        # DEBUG: Log initialization
        self.logger().info(f"[WEEX_DEBUG] WeexExchange.__init__() completed. trading_pairs={trading_pairs}, trading_required={trading_required}")

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
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKERS_PATH_URL)
        return pairs_prices.get("data", []) if isinstance(pairs_prices, dict) else pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception).lower()
        return (
            "timestamp" in error_description
            or "access-timestamp" in error_description
            or "time" in error_description and "invalid" in error_description
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        msg = str(status_update_exception).lower()
        return "order not found" in msg or "order does not exist" in msg or "order not exist" in msg

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        msg = str(cancelation_exception).lower()
        return "order not found" in msg or "order does not exist" in msg or "order not exist" in msg

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
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        order_type_str = "limit" if order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER) else "market"
        api_params = {
            "symbol": symbol,
            "side": side_str,
            "orderType": order_type_str,
            "quantity": amount_str,
            "clientOrderId": order_id,
        }
        if order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER):
            api_params["price"] = f"{price:f}"
            api_params["force"] = (
                CONSTANTS.FORCE_POST_ONLY if order_type is OrderType.LIMIT_MAKER else CONSTANTS.FORCE_NORMAL
            )

        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.CREATE_ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True,
                limit_id=CONSTANTS.CREATE_ORDER_LIMIT_ID)
            order_data = order_result.get("data", {}) if isinstance(order_result, dict) else {}
            o_id = str(order_data.get("orderId"))
            transact_time = float(order_result.get("requestTime", self._time_synchronizer.time() * 1e3)) * 1e-3
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
            "clientOrderId": order_id,
        }
        if tracked_order.exchange_order_id is not None:
            api_params["orderId"] = tracked_order.exchange_order_id
        cancel_response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID)

        cancel_data = cancel_response.get("data", {}) if isinstance(cancel_response, dict) else {}
        if cancel_data.get("result") is True:
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
        self._trade_fee_schema = weex_utils.DEFAULT_FEES

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                if event_message.get("event") != "payload":
                    continue

                channel = event_message.get("channel", "")
                data = event_message.get("data")
                if data is None:
                    continue

                payloads = data if isinstance(data, list) else [data]

                if channel.startswith("account"):
                    for balance_entry in payloads:
                        asset_name = balance_entry.get("coinName") or balance_entry.get("coin") or balance_entry.get("currency")
                        if asset_name is None:
                            continue
                        free_balance = Decimal(str(balance_entry.get("available", "0")))
                        frozen_balance = Decimal(str(balance_entry.get("frozen", "0")))
                        total_balance = free_balance + frozen_balance
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

                elif channel.startswith("fill"):
                    for fill in payloads:
                        client_order_id = (
                            fill.get("clientOrderId")
                            or fill.get("clientOid")
                            or fill.get("clientOrderID")
                        )
                        if client_order_id is None:
                            continue

                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is None:
                            continue

                        fee_amount = Decimal(str(fill.get("fillFee") or fill.get("fee") or fill.get("fees") or "0"))
                        fee_token = fill.get("feeCoin") or fill.get("quoteCoin") or fill.get("feeAsset")
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=fee_token,
                            flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)] if fee_token else [],
                        )

                        trade_update = TradeUpdate(
                            trade_id=str(fill.get("fillId") or fill.get("tradeId") or fill.get("id")),
                            client_order_id=client_order_id,
                            exchange_order_id=str(fill.get("orderId")),
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(fill.get("fillQuantity") or fill.get("size") or fill.get("quantity") or "0")),
                            fill_quote_amount=Decimal(str(fill.get("fillTotalAmount") or fill.get("value") or "0")),
                            fill_price=Decimal(str(fill.get("fillPrice") or fill.get("price") or "0")),
                            fill_timestamp=float(fill.get("cTime") or fill.get("time") or self.current_timestamp) * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)

                elif channel.startswith("orders"):
                    for order_update in payloads:
                        client_order_id = (
                            order_update.get("clientOrderId")
                            or order_update.get("clientOid")
                            or order_update.get("clientOrderID")
                        )
                        if client_order_id is None:
                            continue

                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if tracked_order is None:
                            continue

                        new_state = CONSTANTS.ORDER_STATE.get(order_update.get("status", "PENDING"), OrderState.PENDING_CREATE)
                        update_time = (
                            order_update.get("uTime")
                            or order_update.get("updateTime")
                            or order_update.get("cTime")
                            or order_update.get("time")
                            or self.current_timestamp * 1e3
                        )

                        order_update_obj = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=float(update_time) * 1e-3,
                            new_state=new_state,
                            client_order_id=client_order_id,
                            exchange_order_id=str(order_update.get("orderId")),
                        )
                        self._order_tracker.process_order_update(order_update=order_update_obj)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)
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
        if not self.in_flight_orders:
            return

        tracked_orders = list(self._order_tracker.all_fillable_orders.values())
        if not tracked_orders:
            return

        tasks = [self._all_trade_updates_for_order(order) for order in tracked_orders]
        results = await safe_gather(*tasks, return_exceptions=True)

        for updates in results:
            if isinstance(updates, Exception):
                continue
            for trade_update in updates:
                self._order_tracker.process_trade_update(trade_update)
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
            all_fills_response = await self._api_post(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                data={
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_LIMIT_ID)

            fills_data = all_fills_response.get("data", {}) if isinstance(all_fills_response, dict) else {}
            fills_list = fills_data.get("fillsOrderResultList", []) if isinstance(fills_data, dict) else []

            for trade in fills_list:
                exchange_order_id = str(trade.get("orderId"))
                fee_amount = Decimal(trade.get("fees", "0"))
                fee_token = trade.get("quoteCoin")
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=fee_token,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)] if fee_token else []
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade.get("fillId")),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade.get("fillQuantity", "0")),
                    fill_quote_amount=Decimal(trade.get("fillTotalAmount", "0")),
                    fill_price=Decimal(trade.get("fillPrice", "0")),
                    fill_timestamp=float(trade.get("cTime", 0)) * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_response = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            data={
                "clientOrderId": tracked_order.client_order_id
            },
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID)

        data = updated_order_response.get("data") if isinstance(updated_order_response, dict) else None
        if isinstance(data, list) and len(data) > 0:
            updated_order_data = data[0]
        elif isinstance(data, dict):
            updated_order_data = data
        else:
            updated_order_data = {}

        new_state = CONSTANTS.ORDER_STATE[updated_order_data.get("status", "PENDING")]
        update_time = (
            updated_order_data.get("uTime")
            or updated_order_data.get("updateTime")
            or updated_order_response.get("requestTime", 0)
        )

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data.get("orderId")),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(update_time) * 1e-3,
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

    @staticmethod
    def weex_symbol_to_hb_pair(symbol: str) -> str:
        # BTCUSDT_SPBL -> BTCUSDT
        core = symbol[:-5]  # drop "_SPBL"
        for q in WeexExchange.KNOWN_QUOTES:
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
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            limit_id=CONSTANTS.TICKER_PRICE_CHANGE_LIMIT_ID,
            params=params
        )

        return float(resp_json["data"]["lastPrice"])
