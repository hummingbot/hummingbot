import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_utils, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_api_order_book_data_source import XtAPIOrderBookDataSource
from hummingbot.connector.exchange.xt.xt_api_user_stream_data_source import XtAPIUserStreamDataSource
from hummingbot.connector.exchange.xt.xt_auth import XtAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class XtAmbiguousOrderCreateError(IOError):
    """A dispatched create has neither an acknowledgement nor a definitive rejection."""


class XtIncompleteOrderFillsError(IOError):
    """A terminal status cannot yet be reconciled with complete actual fills."""


class XtExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        xt_api_key: str,
        xt_api_secret: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = xt_api_key
        self.secret_key = xt_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def authenticator(self):
        return XtAuth(api_key=self.api_key, secret_key=self.secret_key, time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "xt"

    @property
    def domain(self):
        return self._domain

    @property
    def rate_limits_rules(self):
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
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return (CONSTANTS.TIMESTAMP_ERROR_CODE in str(request_exception)
                or CONSTANTS.TIMESTAMP_ERROR_MESSAGE in str(request_exception))

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR_CODE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR_CODE in str(cancelation_exception)

    def _create_web_assistants_factory(self):
        return web_utils.build_api_factory(throttler=self._throttler, time_synchronizer=self._time_synchronizer,
                                           domain=self.domain, auth=self._auth)

    def _create_order_book_data_source(self):
        return XtAPIOrderBookDataSource(trading_pairs=self._trading_pairs, connector=self,
                                        api_factory=self._web_assistants_factory, domain=self.domain)

    def _create_user_stream_data_source(self):
        return XtAPIUserStreamDataSource(auth=self._auth, trading_pairs=self._trading_pairs, connector=self,
                                         api_factory=self._web_assistants_factory, domain=self.domain)

    async def _api_request(self, path_url, overwrite_url=None, method=RESTMethod.GET, params=None, data=None,
                           is_auth_required=False, return_err=False, limit_id=None, headers=None, **kwargs):
        # XT also returns timestamp denials in HTTP-200 envelopes. Retry only this
        # explicit no-execution denial; never replay an uncertain order POST.
        for attempt in range(2):
            if method is RESTMethod.POST and path_url == CONSTANTS.ORDER_PATH_URL:
                response = await self._request_order_create(
                    path_url, overwrite_url, params, data, is_auth_required, limit_id, headers)
            else:
                response = await super()._api_request(
                    path_url=path_url, overwrite_url=overwrite_url, method=method, params=params, data=data,
                    is_auth_required=is_auth_required, return_err=return_err, limit_id=limit_id, headers=headers, **kwargs)
            if not is_auth_required or not web_utils.is_time_sync_error_response(response):
                return response
            if attempt == 0:
                await self._update_time_synchronizer()
        return response

    async def _request_order_create(self, path_url, overwrite_url, params, data, is_auth_required, limit_id, headers):
        # Retain HTTP status until the denial is classified. The normal native
        # JSON helper raises before exposing 4xx envelopes and retries some HTTP
        # errors; an uncertain POST must never be replayed by that retry path.
        assistant = await self._web_assistants_factory.get_rest_assistant()
        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)
        response = await assistant.execute_request_and_get_response(
            url=url, params=params, data=data, method=RESTMethod.POST, is_auth_required=is_auth_required,
            return_err=True, throttler_limit_id=limit_id or path_url, headers=headers)
        if response.status >= 500:
            raise IOError(f"XT create returned uncertain HTTP status {response.status}")
        payload = await response.json()
        if response.status >= 400 and not web_utils.is_definitive_order_create_rejection(payload):
            raise IOError(f"XT create returned an unrecognized HTTP {response.status} rejection")
        return payload

    async def _make_network_check_request(self):
        response = await self._api_get(path_url=self.check_network_request_path)
        web_utils.result_from_response(response, "network check")

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal = Decimal("NaN"), is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker if is_maker is not None else order_type is OrderType.LIMIT_MAKER
        schema = self._trading_fees.get(combine_to_hb_trading_pair(base_currency, quote_currency))
        if schema is not None:
            percent = schema.maker_percent_fee_decimal if is_maker else schema.taker_percent_fee_decimal
            return TradeFeeBase.new_spot_fee(schema, order_side, percent=percent)
        return build_trade_fee(self.name, is_maker, base_currency=base_currency, quote_currency=quote_currency,
                               order_type=order_type, order_side=order_side, amount=amount, price=price)

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal, **kwargs) -> Tuple[str, float]:
        if order_type not in self.supported_order_types():
            raise ValueError("XT supports LIMIT and LIMIT_MAKER orders")
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        body = {"symbol": symbol, "clientOrderId": order_id, "side": trade_type.name,
                "type": CONSTANTS.ORDER_TYPE_LIMIT, "bizType": CONSTANTS.BIZ_TYPE_SPOT,
                "timeInForce": CONSTANTS.TIME_IN_FORCE_GTX if order_type is OrderType.LIMIT_MAKER else CONSTANTS.TIME_IN_FORCE_GTC,
                "price": f"{price:f}", "quantity": f"{amount:f}"}
        try:
            response = await self._api_post(path_url=CONSTANTS.ORDER_PATH_URL, data=body,
                                            is_auth_required=True, limit_id=CONSTANTS.PRIVATE_ORDER_LIMIT_ID)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise XtAmbiguousOrderCreateError(f"XT create acknowledgement is unresolved for {order_id}") from error
        try:
            result = web_utils.result_from_response(response, "place order")
            if not isinstance(result, dict) or not str(result.get("orderId") or "").strip():
                raise IOError("XT place order returned no exchange order ID")
        except Exception as error:
            if web_utils.is_definitive_order_create_rejection(response):
                raise
            raise XtAmbiguousOrderCreateError(f"XT create response is unresolved for {order_id}") from error
        return str(result["orderId"]), self._time_synchronizer.time()

    def _on_order_failure(self, order_id, trading_pair, amount, trade_type, order_type, price, exception, **kwargs):
        # A timeout does not establish that XT rejected the client ID. Keep the
        # native reservation pending until exact status lookup or private events resolve it.
        if isinstance(exception, XtAmbiguousOrderCreateError):
            self.logger().warning(f"XT create acknowledgement is unresolved for {order_id}; keeping the native order pending")
            return
        super()._on_order_failure(order_id=order_id, trading_pair=trading_pair, amount=amount,
                                  trade_type=trade_type, order_type=order_type, price=price, exception=exception, **kwargs)

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, error: Exception):
        if isinstance(error, XtIncompleteOrderFillsError):
            # An exact terminal status is positive evidence that this order
            # exists. A delayed trade endpoint must not turn it into a lost order.
            self.logger().warning(f"XT terminal fills for {order.client_order_id} remain unresolved: {error}")
            return
        if order.is_pending_create and not order.exchange_order_id:
            # ORDER_005 after an uncertain POST cannot prove the create never
            # executed. XT's exact client-ID lookup may become visible later.
            self.logger().warning(f"XT pending create {order.client_order_id} remains unresolved: {error}")
            return
        await super()._handle_update_error_for_active_order(order, error)

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        if not order.exchange_order_id:
            try:
                update = await self._request_order_status(order)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not let the base's missing-ID cancellation timeout mark an
                # uncertain create as lost. A later native poll can recover it.
                return False
            await self._order_tracker.process_order_update(update)
            if update.new_state in (OrderState.CANCELED, OrderState.FAILED):
                # Recovery already emitted the terminal event and stopped tracking.
                # Return success without the base overwriting it with PENDING_CANCEL.
                return True
            if update.new_state is OrderState.FILLED:
                return False
        return await super()._execute_order_cancel_and_process_update(order)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        response = await self._api_delete(path_url=CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=exchange_order_id),
                                          is_auth_required=True, limit_id=CONSTANTS.PRIVATE_ORDER_LIMIT_ID)
        web_utils.result_from_response(response, "cancel order")
        return True

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = tracked_order.exchange_order_id
        response = await self._api_get(
            path_url=(CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=exchange_order_id)
                      if exchange_order_id else CONSTANTS.ORDER_PATH_URL),
            params=None if exchange_order_id else {"clientOrderId": tracked_order.client_order_id},
            is_auth_required=True, limit_id=CONSTANTS.PRIVATE_ORDER_LIMIT_ID)
        row = web_utils.result_from_response(response, "order status")
        if not isinstance(row, dict) or not str(row.get("orderId") or "").strip():
            raise ValueError("XT order status has no exchange order ID")
        if exchange_order_id and str(row["orderId"]) != str(exchange_order_id):
            raise ValueError("XT order status changed exchange order ID")
        if (row.get("clientOrderId") not in (None, tracked_order.client_order_id)
                or (not exchange_order_id and row.get("clientOrderId") != tracked_order.client_order_id)):
            raise ValueError("XT order status changed client order ID")
        symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        if ((row.get("symbol") is not None and row["symbol"] != symbol)
                or row.get("bizType") not in (None, CONSTANTS.BIZ_TYPE_SPOT)
                or row.get("side") not in (None, tracked_order.trade_type.name)):
            raise ValueError("XT order status changed order identity")
        for field, expected in (("price", tracked_order.price), ("quantity", tracked_order.amount),
                                ("origQty", tracked_order.amount)):
            if row.get(field) is not None and Decimal(str(row[field])) != expected:
                raise ValueError(f"XT order status changed order {field}")
        state = CONSTANTS.ORDER_STATE[row["state"]]
        timestamp = self._timestamp_ms_to_seconds(row.get("updatedTime") or row.get("time"))
        if not exchange_order_id and state is not OrderState.FAILED:
            # Recovery can discover an already filled/canceled create. Teach the
            # native tracker its ID and collect actual fills before finalization.
            await self._order_tracker.process_order_update(OrderUpdate(
                client_order_id=tracked_order.client_order_id, exchange_order_id=str(row["orderId"]),
                trading_pair=tracked_order.trading_pair, new_state=OrderState.OPEN, update_timestamp=timestamp))
            if state is OrderState.PARTIALLY_FILLED:
                for update in await self._all_trade_updates_for_order(tracked_order):
                    self._order_tracker.process_trade_update(update)
        if state in (OrderState.FILLED, OrderState.CANCELED):
            await self._reconcile_terminal_fills(tracked_order, state, row.get("executedQty"))
        return OrderUpdate(client_order_id=tracked_order.client_order_id, exchange_order_id=str(row["orderId"]),
                           trading_pair=tracked_order.trading_pair, new_state=state, update_timestamp=timestamp)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        result = web_utils.result_from_response(exchange_info_dict, "exchange info")
        rules = []
        for info in filter(xt_utils.is_exchange_information_valid, result["symbols"]):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(info["symbol"])
                filters = {entry["filter"]: entry for entry in info.get("filters", [])}
                price, quantity, quote = (filters.get(name, {}) for name in ("PRICE", "QUANTITY", "QUOTE_QTY"))
                rules.append(TradingRule(
                    trading_pair=trading_pair, min_order_size=self._decimal_or_default(quantity.get("min"), "0"),
                    max_order_size=self._decimal_or_default(quantity.get("max"), "1e56"),
                    min_price_increment=self._decimal_or_default(price.get("tickSize"), self._increment(info.get("pricePrecision"))),
                    min_base_amount_increment=self._decimal_or_default(quantity.get("tickSize"), self._increment(info.get("quantityPrecision"))),
                    min_quote_amount_increment=self._increment(info.get("quoteCurrencyPrecision")),
                    min_notional_size=self._decimal_or_default(quote.get("min"), "0"), supports_market_orders=False))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return rules

    async def _update_trading_fees(self):
        response = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        result = web_utils.result_from_response(response, "trading fees")
        for info in filter(xt_utils.is_exchange_information_valid, result["symbols"]):
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(info["symbol"])
            self._trading_fees[trading_pair] = TradeFeeSchema(
                maker_percent_fee_decimal=Decimal(str(info["makerFeeRate"])),
                taker_percent_fee_decimal=Decimal(str(info["takerFeeRate"])),
                buy_percent_fee_deducted_from_returns=self.trade_fee_schema().buy_percent_fee_deducted_from_returns)

    async def _update_balances(self):
        response = await self._api_get(path_url=CONSTANTS.BALANCES_PATH_URL, is_auth_required=True)
        result = web_utils.result_from_response(response, "balances")
        balances, available = {}, {}
        for row in result["assets"]:
            asset = row["currency"].upper()
            balances[asset] = Decimal(str(row["totalAmount"]))
            available[asset] = Decimal(str(row["availableAmount"]))
        self._account_balances.clear()
        self._account_balances.update(balances)
        self._account_available_balances.clear()
        self._account_available_balances.update(available)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        result = web_utils.result_from_response(exchange_info, "exchange info")
        mapping = bidict()
        for row in filter(xt_utils.is_exchange_information_valid, result["symbols"]):
            mapping[row["symbol"]] = combine_to_hb_trading_pair(row["baseCurrency"].upper(), row["quoteCurrency"].upper())
        self._set_trading_pair_symbol_map(mapping)

    async def get_all_pairs_prices(self) -> List[Dict[str, Any]]:
        response = await self._api_get(path_url=CONSTANTS.TICKER_PRICE_PATH_URL, limit_id=CONSTANTS.PUBLIC_TICKER_LIMIT_ID)
        return web_utils.result_from_response(response, "ticker price")

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        response = await self._api_get(path_url=CONSTANTS.TICKER_PRICE_PATH_URL, params={"symbol": symbol},
                                       limit_id=CONSTANTS.PUBLIC_TICKER_LIMIT_ID)
        result = web_utils.result_from_response(response, "ticker price")
        return float((result[0] if isinstance(result, list) else result)["p"])

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if not order.exchange_order_id:
            return []
        symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)
        params = {"symbol": symbol, "bizType": CONSTANTS.BIZ_TYPE_SPOT, "orderId": order.exchange_order_id,
                  "direction": "NEXT", "limit": 100}
        updates = {}
        for _ in range(200):
            response = await self._api_get(path_url=CONSTANTS.TRADE_HISTORY_PATH_URL, params=dict(params),
                                           is_auth_required=True)
            result = web_utils.result_from_response(response, "trade history")
            if isinstance(result, dict):
                rows = result["items"]
                has_next = result.get("hasNext")
                if has_next is not None and not isinstance(has_next, bool):
                    raise ValueError("XT trade history hasNext must be boolean")
            else:
                rows, has_next = result, None
            if not isinstance(rows, list):
                raise ValueError("XT trade history must contain an items list")
            for row in rows:
                if (str(row["orderId"]) != str(order.exchange_order_id)
                        or row.get("symbol", symbol) != symbol
                        or row.get("bizType", CONSTANTS.BIZ_TYPE_SPOT) != CONSTANTS.BIZ_TYPE_SPOT
                        or row.get("clientOrderId", order.client_order_id) != order.client_order_id
                        or row.get("side", row.get("orderSide", order.trade_type.name)) != order.trade_type.name):
                    raise ValueError("XT trade history changed order identity")
                update = self._trade_update(order, row)
                prior = updates.get(update.trade_id)
                if prior is not None and prior != update:
                    raise ValueError("XT trade history returned conflicting duplicate fills")
                updates[update.trade_id] = update
            if has_next is False or (has_next is None and len(rows) < params["limit"]):
                return sorted(updates.values(), key=lambda update: (update.fill_timestamp, update.trade_id))
            if has_next is None:
                raise IOError("XT trade history page saturated without an explicit pagination cursor")
            try:
                cursor = min(int(row["tradeId"]) for row in rows)
            except (ValueError, KeyError, TypeError):
                raise IOError("XT trade history has no advancing numeric cursor")
            if "fromId" in params and cursor >= params["fromId"]:
                raise IOError("XT trade history pagination did not advance fromId")
            params["fromId"] = cursor
        raise IOError("XT trade history page cap exceeded")

    def _trade_update(self, order: InFlightOrder, row: Dict[str, Any]) -> TradeUpdate:
        # Private trade messages do not always carry actual commission. REST
        # reconciliation supplies it before a fill is emitted to the recorder.
        if row.get("fee") is None:
            raise ValueError("XT fill has no actual fee amount")
        fee_amount = Decimal(str(row["fee"]))
        fee_currency = str(row.get("feeCurrency") or "").upper()
        if not fee_amount.is_finite() or (fee_amount != 0 and not fee_currency):
            raise ValueError("XT fill has invalid fee metadata")
        amount, price = Decimal(str(row["quantity"])), Decimal(str(row["price"]))
        quote = Decimal(str(row.get("quoteQty", amount * price)))
        if any(not value.is_finite() or value <= 0 for value in (amount, price, quote)):
            raise ValueError("XT fill has invalid execution amounts")
        fee = TradeFeeBase.new_spot_fee(
            self._trading_fees.get(order.trading_pair, self.trade_fee_schema()), order.trade_type,
            flat_fees=[TokenAmount(token=fee_currency, amount=fee_amount)] if fee_amount else [])
        timestamp = row.get("time", row.get("tradeTime"))
        if not str(row.get("tradeId") or "").strip() or timestamp is None or float(timestamp) <= 0:
            raise ValueError("XT fill has no actual trade ID or timestamp")
        return TradeUpdate(trade_id=str(row["tradeId"]), client_order_id=order.client_order_id,
                           exchange_order_id=str(order.exchange_order_id), trading_pair=order.trading_pair,
                           fill_timestamp=self._timestamp_ms_to_seconds(timestamp),
                           fill_price=price, fill_base_amount=amount, fill_quote_amount=quote, fee=fee)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                topic = event_message.get("topic")
                if topic == CONSTANTS.WS_PRIVATE_ORDER_TOPIC:
                    await self._process_user_stream_order_event(event_message)
                elif topic == CONSTANTS.WS_PRIVATE_TRADE_TOPIC:
                    await self._process_user_stream_trade_event(event_message)
                elif topic == CONSTANTS.WS_PRIVATE_BALANCE_TOPIC:
                    self._process_user_stream_balance_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(1.0)

    async def _process_user_stream_order_event(self, event_message: Dict[str, Any]):
        data = event_message["data"]
        exchange_id = str(data.get("i") or "").strip()
        order = (self._order_tracker.all_updatable_orders.get(data.get("ci"))
                 or self._order_tracker.all_updatable_orders_by_exchange_order_id.get(exchange_id))
        if order is None:
            return
        await self._validate_user_stream_identity(order, data, exchange_id)
        state = CONSTANTS.ORDER_STATE[data["st"]]
        # Let the native tracker learn an ID after an uncertain create without
        # bypassing its PENDING_CREATE -> OPEN transition and creation event.
        if not order.exchange_order_id and state is not OrderState.FAILED:
            await self._order_tracker.process_order_update(OrderUpdate(
                trading_pair=order.trading_pair, update_timestamp=self._timestamp_ms_to_seconds(data.get("t")),
                new_state=OrderState.OPEN, client_order_id=order.client_order_id, exchange_order_id=exchange_id))
        if state is OrderState.CANCELED and data.get("eq") is None:
            # A successful trade page may still lag the cancellation. Obtain
            # XT's explicit cumulative execution quantity from exact status;
            # if status is still open, leave the native order open for polling.
            update = await self._request_order_status(order)
            await self._order_tracker.process_order_update(update)
            return
        if state in (OrderState.FILLED, OrderState.CANCELED):
            await self._reconcile_terminal_fills(order, state, data.get("eq"))
        elif state is OrderState.PARTIALLY_FILLED and order.executed_amount_base < order.amount:
            for update in await self._all_trade_updates_for_order(order):
                self._order_tracker.process_trade_update(update)
        self._order_tracker.process_order_update(OrderUpdate(
            trading_pair=order.trading_pair, update_timestamp=self._timestamp_ms_to_seconds(data.get("t")),
            new_state=state, client_order_id=order.client_order_id, exchange_order_id=exchange_id))

    async def _process_user_stream_trade_event(self, event_message: Dict[str, Any]):
        data = event_message["data"]
        order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(str(data["oi"]))
        if order is None:
            return
        await self._validate_user_stream_identity(order, data, str(data["oi"]))
        if data.get("fee") is None or (Decimal(str(data["fee"])) != 0 and not data.get("feeCurrency")):
            updates = await self._all_trade_updates_for_order(order)
        else:
            updates = [self._trade_update(order, {"tradeId": data["i"], "price": data["p"], "quantity": data["q"],
                                                  "quoteQty": data.get("v", Decimal(str(data["p"])) * Decimal(str(data["q"]))),
                                                  "time": data["t"], "fee": data["fee"], "feeCurrency": data.get("feeCurrency")})]
        for update in updates:
            self._order_tracker.process_trade_update(update)

    async def _validate_user_stream_identity(self, order: InFlightOrder, data: Dict[str, Any], exchange_id: str):
        if not exchange_id or (order.exchange_order_id and str(order.exchange_order_id) != exchange_id):
            raise ValueError("XT private event changed exchange order ID")
        symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)
        expected_fields = {
            "ci": order.client_order_id, "clientOrderId": order.client_order_id,
            "orderId": exchange_id, "s": symbol, "symbol": symbol,
            "sd": order.trade_type.name, "side": order.trade_type.name, "orderSide": order.trade_type.name,
            "bizType": CONSTANTS.BIZ_TYPE_SPOT, "z": CONSTANTS.BIZ_TYPE_SPOT,
            "tp": CONSTANTS.ORDER_TYPE_LIMIT,
        }
        for field, expected in expected_fields.items():
            if field in data and str(data[field]) != str(expected):
                raise ValueError(f"XT private event changed order identity: {field}")
        if "oq" in data and Decimal(str(data["oq"])) != order.amount:
            raise ValueError("XT private event changed original order quantity")

    async def _reconcile_terminal_fills(self, order: InFlightOrder, state: OrderState, executed_quantity=None):
        try:
            # Cancellation alone does not disclose whether an execution preceded
            # it. Require XT's cumulative quantity rather than trusting a trade
            # page that can be successfully returned before indexing catches up.
            if state is OrderState.CANCELED and executed_quantity is None:
                raise ValueError("XT canceled state has no explicit executed quantity")
            expected = order.amount if state is OrderState.FILLED else None
            if executed_quantity is not None:
                reported = Decimal(str(executed_quantity))
                if (not reported.is_finite() or reported < 0 or reported > order.amount
                        or (expected is not None and reported != expected)):
                    raise ValueError("XT terminal state has inconsistent executed quantity")
                expected = reported
            updates = await self._all_trade_updates_for_order(order)
            total = sum((update.fill_base_amount for update in updates), Decimal("0"))
            if (expected is not None and total != expected) or total < order.executed_amount_base:
                raise ValueError("XT terminal trade history does not cover the executed quantity")
            for update in updates:
                self._order_tracker.process_trade_update(update)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise XtIncompleteOrderFillsError(f"Cannot reconcile {state.name} order {order.client_order_id}") from error

    def _process_user_stream_balance_event(self, event_message: Dict[str, Any]):
        data = event_message["data"]
        if data.get("z") != CONSTANTS.BIZ_TYPE_SPOT:
            return
        asset = data["c"].upper()
        total, frozen = Decimal(str(data["b"])), Decimal(str(data["f"]))
        self._account_balances[asset] = total
        self._account_available_balances[asset] = total - frozen

    @staticmethod
    def _decimal_or_default(value, default):
        return Decimal(str(default if value is None or value == "" else value))

    @staticmethod
    def _increment(precision):
        return Decimal(1).scaleb(-int(precision)) if precision is not None else Decimal("1e-18")

    def _timestamp_ms_to_seconds(self, timestamp):
        return float(timestamp) * 1e-3 if timestamp is not None else self._time_synchronizer.time()
