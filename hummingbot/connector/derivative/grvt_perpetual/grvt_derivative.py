import asyncio
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

try:
    from bidict import bidict
except Exception:  # pragma: no cover - fallback for lightweight environments
    class bidict(dict):
        @property
        def inverse(self):
            return {value: key for key, value in self.items()}

import hummingbot.connector.derivative.grvt_perpetual.grvt_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_api_order_book_data_source import (
    GrvtAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_auth import GrvtAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_exchange_info import (
    exchange_symbol_to_hb_trading_pair,
    extract_symbol_map,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_user_stream_data_source import (
    GrvtUserStreamDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_utils import DEFAULT_FEES, is_exchange_information_valid
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GrvtDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
        self,
        client_config_map,
        grvt_api_key: str,
        grvt_api_secret: str,
        grvt_ethereum_private_key: str,
        grvt_account_address: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self._client_config_map = client_config_map
        self._domain = domain
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._grvt_api_key = grvt_api_key
        self._grvt_api_secret = grvt_api_secret
        self._grvt_ethereum_private_key = grvt_ethereum_private_key
        self._grvt_account_address = grvt_account_address
        self._auth: Optional[GrvtAuth] = None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> GrvtAuth:
        if self._auth is None:
            self._auth = GrvtAuth(
                api_key=self._grvt_api_key,
                api_secret=self._grvt_api_secret,
                ethereum_private_key=self._grvt_ethereum_private_key,
                account_address=self._grvt_account_address,
                time_provider=self._time_synchronizer,
            )
        return self._auth

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.ORDER_ID_MAX_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        rule = self._trading_rules.get(trading_pair)
        if rule is not None and getattr(rule, "buy_order_collateral_token", None):
            return rule.buy_order_collateral_token
        return trading_pair.split("-")[1]

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        rule = self._trading_rules.get(trading_pair)
        if rule is not None and getattr(rule, "sell_order_collateral_token", None):
            return rule.sell_order_collateral_token
        return trading_pair.split("-")[1]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        message = str(request_exception).lower()
        return "timestamp" in message and ("expired" in message or "invalid" in message or "drift" in message)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        message = str(status_update_exception).lower()
        return "order not found" in message or "unknown order" in message or "404" in message

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        message = str(cancelation_exception).lower()
        return "order not found" in message or "unknown order" in message or "404" in message

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GrvtAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GrvtUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        payload: Dict[str, Any] = {
            "type": "cancel",
            "market": symbol,
            "clientOrderId": order_id,
        }
        if tracked_order.exchange_order_id:
            payload["orderId"] = tracked_order.exchange_order_id
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=payload,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_PATH_URL,
        )
        error = self._extract_error_message(cancel_result)
        if error is not None:
            raise IOError(error)
        order_data = self._extract_order_payload(
            cancel_result,
            client_order_id=order_id,
            exchange_order_id=tracked_order.exchange_order_id,
        )
        if order_data:
            status = str(
                order_data.get("status")
                or order_data.get("state")
                or order_data.get("orderStatus")
                or ""
            ).strip().lower()
            if status in {"cancelled", "canceled", "closed"}:
                return True
        return self._response_indicates_success(cancel_result)

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        quantized_amount = self._quantize_size_for_api(trading_pair=trading_pair, amount=amount)
        payload: Dict[str, Any] = {
            "type": "order",
            "market": symbol,
            "clientOrderId": order_id,
            "side": "buy" if trade_type == TradeType.BUY else "sell",
            "orderType": "market" if order_type == OrderType.MARKET else "limit",
            "size": str(quantized_amount),
            "reduceOnly": position_action == PositionAction.CLOSE,
        }
        if order_type == OrderType.LIMIT_MAKER:
            payload["timeInForce"] = "post_only"
        elif order_type == OrderType.MARKET:
            payload["timeInForce"] = "ioc"
        else:
            payload["timeInForce"] = "gtc"
        if order_type.is_limit_type():
            quantized_price = self._quantize_price_for_api(trading_pair=trading_pair, price=price)
            payload["price"] = str(quantized_price)

        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_PATH_URL,
            data=payload,
            is_auth_required=True,
            limit_id=CONSTANTS.CREATE_ORDER_PATH_URL,
        )
        error = self._extract_error_message(order_result)
        if error is not None:
            raise IOError(f"Error submitting order {order_id}: {error}")

        order_payload = self._extract_order_payload(order_result, client_order_id=order_id)
        exchange_order_id = str(
            order_payload.get("orderId")
            or order_payload.get("id")
            or order_payload.get("exchangeOrderId")
            or order_id
        )
        creation_ts = self._extract_timestamp(order_payload, default=self.current_timestamp or self._time())
        return exchange_order_id, creation_ts

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        exchange_order_id: Optional[str] = tracked_order.exchange_order_id
        if exchange_order_id is None:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
            except asyncio.TimeoutError:
                exchange_order_id = None
        params: Dict[str, Any] = {
            "market": symbol,
            "clientOrderId": tracked_order.client_order_id,
        }
        if exchange_order_id is not None:
            params["orderId"] = exchange_order_id

        order_result = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_STATUS_PATH_URL,
        )
        error = self._extract_error_message(order_result)
        if error is not None:
            raise IOError(error)

        order_payload = self._extract_order_payload(
            order_result,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )
        if not order_payload:
            raise IOError(f"Order not found: {tracked_order.client_order_id}")
        state = str(
            order_payload.get("status")
            or order_payload.get("state")
            or order_payload.get("orderStatus")
            or ""
        ).strip().lower()
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._extract_timestamp(order_payload, default=self.current_timestamp or self._time()),
            new_state=CONSTANTS.ORDER_STATE.get(state, tracked_order.current_state),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(
                order_payload.get("orderId")
                or order_payload.get("id")
                or order_payload.get("exchangeOrderId")
                or exchange_order_id
                or ""
            ),
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        exchange_order_id: Optional[str] = order.exchange_order_id
        if exchange_order_id is None:
            try:
                exchange_order_id = await order.get_exchange_order_id()
            except asyncio.TimeoutError:
                return []

        order_result = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            params={
                "market": symbol,
                "clientOrderId": order.client_order_id,
                "orderId": exchange_order_id,
            },
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_STATUS_PATH_URL,
        )
        if self._extract_error_message(order_result) is not None:
            return []

        order_payload = self._extract_order_payload(
            order_result,
            client_order_id=order.client_order_id,
            exchange_order_id=exchange_order_id,
        )
        updates: List[TradeUpdate] = []
        for fill in self._extract_fill_rows(order_payload):
            trade_update = self._trade_update_from_fill_payload(fill=fill, tracked_order=order)
            if trade_update is not None:
                updates.append(trade_update)
        return updates

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = str(
                    event_message.get("channel")
                    or event_message.get("topic")
                    or event_message.get("stream")
                    or ""
                ).lower()
                if not channel:
                    continue
                if CONSTANTS.WS_ORDERS_CHANNEL in channel:
                    self._process_order_ws_event(event_message)
                elif CONSTANTS.WS_FILLS_CHANNEL in channel or "trade" in channel:
                    self._process_trade_ws_event(event_message)
                elif CONSTANTS.WS_POSITIONS_CHANNEL in channel:
                    await self._process_position_ws_event(event_message)
                elif CONSTANTS.WS_ACCOUNT_CHANNEL in channel:
                    self._process_balance_ws_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(1.0)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules: List[TradingRule] = []
        rows = self._extract_rows(exchange_info_dict)
        symbol_map = extract_symbol_map(rows)

        for row in rows:
            try:
                if not is_exchange_information_valid(row):
                    continue
                ex_symbol = str(row.get("symbol") or row.get("market") or row.get("instrument") or "").strip()
                if not ex_symbol:
                    continue
                trading_pair = symbol_map.get(ex_symbol) or exchange_symbol_to_hb_trading_pair(ex_symbol)
                if "-" not in trading_pair:
                    continue
                quote = trading_pair.split("-")[1]

                min_order_size = self._decimal_from_keys(
                    row,
                    ["minOrderSize", "minQty", "quantityMin", "minSize", "qtyStep", "sizeStep"],
                    default=Decimal("0.001"),
                )
                min_base_increment = self._decimal_from_keys(
                    row,
                    ["qtyStep", "sizeStep", "quantityStep", "minBaseAmountIncrement"],
                    default=min_order_size,
                )
                min_price_increment = self._decimal_from_keys(
                    row,
                    ["tickSize", "priceStep", "minPriceIncrement"],
                    default=Decimal("0.01"),
                )
                last_price = self._decimal_from_keys(
                    row,
                    ["lastPrice", "markPrice", "price"],
                    default=Decimal("1"),
                )
                min_notional = self._decimal_from_keys(
                    row,
                    ["minNotional", "notionalMin"],
                    default=min_order_size * (last_price if last_price > Decimal("0") else Decimal("1")),
                )

                rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_increment,
                        min_notional_size=min_notional,
                        buy_order_collateral_token=quote,
                        sell_order_collateral_token=quote,
                    )
                )
            except Exception:
                self.logger().exception("Error parsing trading rule for GRVT row: %s", row)
        return rules

    async def _update_balances(self):
        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.ACCOUNT_INFO_PATH_URL,
        )
        balance_rows = self._extract_balance_rows(account_info)

        local_assets = set(self._account_balances.keys())
        remote_assets = set()
        for balance in balance_rows:
            asset = str(
                balance.get("asset")
                or balance.get("currency")
                or balance.get("token")
                or balance.get("coin")
                or ""
            ).upper().strip()
            if not asset:
                continue
            total_balance = self._decimal_from_keys(
                balance,
                ["balance", "total", "walletBalance", "equity", "totalBalance"],
                default=Decimal("0"),
            )
            available_balance = self._decimal_from_keys(
                balance,
                ["available", "free", "availableBalance", "availableMargin"],
                default=total_balance,
            )
            self._account_balances[asset] = total_balance
            self._account_available_balances[asset] = available_balance
            remote_assets.add(asset)

        for asset in local_assets.difference(remote_assets):
            del self._account_balances[asset]
            del self._account_available_balances[asset]

    async def _update_positions(self):
        positions_info = await self._api_get(
            path_url=CONSTANTS.POSITION_INFO_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.POSITION_INFO_PATH_URL,
        )
        position_rows = self._extract_position_rows(positions_info)
        for position_data in position_rows:
            await self._upsert_position_from_payload(position_data)

    async def _upsert_position_from_payload(self, position_data: Dict[str, Any]):
        ex_symbol = str(
            position_data.get("symbol")
            or position_data.get("market")
            or position_data.get("instrument")
            or ""
        ).strip()
        if not ex_symbol:
            return

        try:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_symbol)
        except KeyError:
            return
        if trading_pair not in self._trading_pairs:
            return

        side, abs_amount = self._position_side_and_amount(position_data)
        pos_key = self._perpetual_trading.position_key(trading_pair, side)
        if abs_amount == Decimal("0"):
            self._perpetual_trading.remove_position(pos_key)
            return

        entry_price = self._decimal_from_keys(
            position_data,
            ["entryPrice", "avgEntryPrice", "averagePrice", "markPrice"],
            default=Decimal("0"),
        )
        unrealized_pnl = self._decimal_from_keys(
            position_data,
            ["unrealizedPnl", "pnl", "uPnl"],
            default=Decimal("0"),
        )
        leverage = self._decimal_from_keys(
            position_data,
            ["leverage", "lev"],
            default=Decimal("1"),
        )
        signed_amount = abs_amount if side == PositionSide.LONG else Decimal("-1") * abs_amount

        position = Position(
            trading_pair=trading_pair,
            position_side=side,
            unrealized_pnl=unrealized_pnl,
            entry_price=entry_price,
            amount=signed_amount,
            leverage=leverage,
        )
        self._perpetual_trading.set_position(pos_key, position)
        self._perpetual_trading.set_leverage(trading_pair, int(leverage) if leverage > Decimal("0") else 1)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode == PositionMode.ONEWAY:
            return True, ""
        return False, "Only ONEWAY position mode is supported by this connector."

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        payload = {
            "type": "updateleverage",
            "market": symbol,
            "leverage": int(leverage),
        }
        response = await self._api_post(
            path_url=CONSTANTS.POSITION_INFO_PATH_URL,
            data=payload,
            is_auth_required=True,
            limit_id=CONSTANTS.POSITION_INFO_PATH_URL,
        )
        error = self._extract_error_message(response)
        if error is not None:
            return False, error
        self._perpetual_trading.set_leverage(trading_pair, int(leverage))
        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.FUNDING_INFO_PATH_URL,
            params={"market": symbol},
            is_auth_required=False,
            limit_id=CONSTANTS.FUNDING_INFO_PATH_URL,
        )
        rows = self._extract_rows(response)
        latest = rows[0] if rows else self._extract_data(response) if isinstance(self._extract_data(response), dict) else {}
        if not isinstance(latest, dict):
            return 0, Decimal("-1"), Decimal("-1")

        payment = self._decimal_from_keys(
            latest,
            ["fundingPayment", "payment", "fundingFee", "paid"],
            default=None,
        )
        if payment is None:
            return 0, Decimal("-1"), Decimal("-1")

        rate = self._decimal_from_keys(latest, ["fundingRate", "rate"], default=Decimal("-1"))
        timestamp = self._extract_timestamp(latest, default=0)
        return timestamp, rate, payment

    async def _update_trading_fees(self):
        # Fees are static defaults for now; endpoint mapping can override this when confirmed.
        return

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = Decimal("NaN"),
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        maker = (
            bool(is_maker)
            if is_maker is not None
            else order_type in {OrderType.LIMIT, OrderType.LIMIT_MAKER}
        )
        percent = DEFAULT_FEES.maker_percent_fee_decimal if maker else DEFAULT_FEES.taker_percent_fee_decimal
        return TradeFeeBase.new_perpetual_fee(
            fee_schema=DEFAULT_FEES,
            position_action=position_action,
            percent=percent,
            percent_token=quote_currency,
        )

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        prices = await self._orderbook_ds.get_last_traded_prices([trading_pair], domain=self._domain)
        if trading_pair not in prices:
            raise IOError(f"No last traded price found for {trading_pair}")
        return float(prices[trading_pair])

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        rows = self._extract_rows(exchange_info)
        symbols_map = extract_symbol_map(rows)
        mapping = bidict()
        for exchange_symbol, trading_pair in symbols_map.items():
            if trading_pair in mapping.inverse:
                continue
            mapping[exchange_symbol] = trading_pair
        if mapping:
            self._set_trading_pair_symbol_map(mapping)

    def _process_order_ws_event(self, event_message: Dict[str, Any]):
        for order_msg in self._extract_event_rows(event_message):
            tracked_order = self._tracked_order_from_payload(order_msg, include_cached=False)
            if tracked_order is None:
                continue
            state = str(
                order_msg.get("status")
                or order_msg.get("state")
                or order_msg.get("orderStatus")
                or ""
            ).strip().lower()
            exchange_order_id = str(
                order_msg.get("orderId")
                or order_msg.get("id")
                or order_msg.get("exchangeOrderId")
                or tracked_order.exchange_order_id
                or ""
            )
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self._extract_timestamp(order_msg, default=self.current_timestamp or self._time()),
                new_state=CONSTANTS.ORDER_STATE.get(state, tracked_order.current_state),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=exchange_order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update)

    def _process_trade_ws_event(self, event_message: Dict[str, Any]):
        for trade_msg in self._extract_event_rows(event_message):
            tracked_order = self._tracked_order_from_payload(trade_msg, include_cached=True)
            if tracked_order is None:
                continue
            trade_update = self._trade_update_from_fill_payload(fill=trade_msg, tracked_order=tracked_order)
            if trade_update is not None:
                self._order_tracker.process_trade_update(trade_update=trade_update)

    async def _process_position_ws_event(self, event_message: Dict[str, Any]):
        for pos_msg in self._extract_event_rows(event_message):
            await self._upsert_position_from_payload(pos_msg)

    def _process_balance_ws_event(self, event_message: Dict[str, Any]):
        for balance_msg in self._extract_event_rows(event_message):
            asset = str(
                balance_msg.get("asset")
                or balance_msg.get("currency")
                or balance_msg.get("token")
                or balance_msg.get("coin")
                or ""
            ).upper().strip()
            if not asset:
                continue
            total = self._decimal_from_keys(
                balance_msg,
                ["balance", "total", "walletBalance", "equity"],
                default=Decimal("0"),
            )
            available = self._decimal_from_keys(
                balance_msg,
                ["available", "free", "availableBalance"],
                default=total,
            )
            self._account_balances[asset] = total
            self._account_available_balances[asset] = available

    def _tracked_order_from_payload(self, payload: Dict[str, Any], include_cached: bool) -> Optional[InFlightOrder]:
        client_order_id = str(
            payload.get("clientOrderId")
            or payload.get("client_order_id")
            or payload.get("clientOid")
            or payload.get("clOrdId")
            or ""
        )
        exchange_order_id = str(
            payload.get("orderId")
            or payload.get("id")
            or payload.get("exchangeOrderId")
            or ""
        )
        if include_cached:
            by_client = self._order_tracker.all_fillable_orders
            by_exchange = self._order_tracker.all_fillable_orders_by_exchange_order_id
        else:
            by_client = self._order_tracker.all_updatable_orders
            by_exchange = self._order_tracker.all_updatable_orders_by_exchange_order_id
        tracked_order = by_client.get(client_order_id)
        if tracked_order is None and exchange_order_id:
            tracked_order = by_exchange.get(exchange_order_id)
        return tracked_order

    def _trade_update_from_fill_payload(
        self,
        fill: Dict[str, Any],
        tracked_order: InFlightOrder,
    ) -> Optional[TradeUpdate]:
        fill_size = self._decimal_from_keys(
            fill,
            ["size", "qty", "quantity", "filledSize", "fillQty", "tradeSize"],
            default=Decimal("0"),
        )
        if fill_size == Decimal("0"):
            return None
        fill_price = self._decimal_from_keys(
            fill,
            ["price", "fillPrice", "avgPrice", "tradePrice", "executionPrice"],
            default=tracked_order.price or Decimal("0"),
        )
        fee_asset = str(
            fill.get("feeAsset")
            or fill.get("feeCurrency")
            or fill.get("feeToken")
            or tracked_order.quote_asset
        )
        fee_amount = self._decimal_from_keys(fill, ["fee", "feeAmount", "tradeFee"], default=Decimal("0"))
        position_action = tracked_order.position if tracked_order.position != PositionAction.NIL else PositionAction.OPEN
        flat_fees = [TokenAmount(token=fee_asset, amount=fee_amount)] if fee_amount != Decimal("0") else []
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=DEFAULT_FEES,
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )
        trade_id = str(
            fill.get("tradeId")
            or fill.get("id")
            or fill.get("fillId")
            or f"{tracked_order.client_order_id}-{self._extract_timestamp(fill, default=self.current_timestamp or self._time())}"
        )
        exchange_order_id = str(
            fill.get("orderId")
            or fill.get("exchangeOrderId")
            or tracked_order.exchange_order_id
            or ""
        )
        return TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=self._extract_timestamp(fill, default=self.current_timestamp or self._time()),
            fill_price=fill_price,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_size * fill_price,
            fee=fee,
        )

    def _extract_fill_rows(self, order_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(order_payload, dict):
            return []
        for key in ("fills", "trades", "executions"):
            value = order_payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        last_fill_price = self._decimal_from_keys(
            order_payload,
            ["lastFillPrice", "avgFillPrice"],
            default=Decimal("0"),
        )
        last_fill_size = self._decimal_from_keys(
            order_payload,
            ["lastFillSize", "filledQty", "filledSize"],
            default=Decimal("0"),
        )
        if last_fill_size > Decimal("0"):
            return [
                {
                    "tradeId": order_payload.get("lastTradeId"),
                    "price": last_fill_price,
                    "size": last_fill_size,
                    "fee": order_payload.get("lastFee", "0"),
                    "feeAsset": order_payload.get("feeCurrency"),
                    "orderId": order_payload.get("orderId"),
                    "timestamp": order_payload.get("updatedAt") or order_payload.get("timestamp"),
                }
            ]
        return []

    def _extract_event_rows(self, event_message: Dict[str, Any]) -> List[Dict[str, Any]]:
        payload = self._extract_data(event_message)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("items", "rows", "orders", "fills", "positions", "balances", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]

    def _extract_order_payload(
        self,
        payload: Any,
        client_order_id: Optional[str] = None,
        exchange_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        rows = self._extract_rows(payload)
        if client_order_id is None and exchange_order_id is None:
            return rows[0] if rows else {}
        for row in rows:
            row_client_id = str(
                row.get("clientOrderId")
                or row.get("client_order_id")
                or row.get("clientOid")
                or row.get("clOrdId")
                or ""
            )
            row_exchange_id = str(row.get("orderId") or row.get("id") or row.get("exchangeOrderId") or "")
            if client_order_id is not None and row_client_id == client_order_id:
                return row
            if exchange_order_id is not None and row_exchange_id == str(exchange_order_id):
                return row
        return rows[0] if rows else {}

    def _extract_rows(self, payload: Any) -> List[Dict[str, Any]]:
        data = self._extract_data(payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("items", "rows", "markets", "instruments", "orders", "positions", "balances"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [data]
        return []

    def _extract_balance_rows(self, payload: Any) -> List[Dict[str, Any]]:
        data = self._extract_data(payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("balances", "assets", "wallets", "accounts"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [data]
        return []

    def _extract_position_rows(self, payload: Any) -> List[Dict[str, Any]]:
        data = self._extract_data(payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("positions", "items", "rows"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [data]
        return []

    def _extract_data(self, payload: Any) -> Any:
        current = payload
        while isinstance(current, dict):
            next_value = None
            for key in ("data", "result", "payload"):
                if key in current:
                    next_value = current[key]
                    break
            if next_value is None:
                break
            current = next_value
        return current

    def _extract_error_message(self, payload: Any) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        if payload.get("error"):
            return str(payload.get("error"))
        code = payload.get("code")
        if code is not None:
            code_text = str(code).lower()
            is_ok_code = code_text in {"0", "200", "ok", "success", "true"}
            if not is_ok_code and not (code_text.isdigit() and 200 <= int(code_text) < 300):
                return str(payload.get("message") or payload.get("msg") or f"code={code}")
        status = payload.get("status")
        if status is not None and str(status).lower() in {"error", "failed", "fail"}:
            return str(payload.get("message") or payload.get("msg") or "request failed")
        success = payload.get("success")
        if success is False:
            return str(payload.get("message") or payload.get("msg") or "request failed")
        return None

    def _response_indicates_success(self, payload: Any) -> bool:
        if payload is None:
            return False
        if not isinstance(payload, dict):
            return bool(payload)
        if self._extract_error_message(payload) is not None:
            return False
        if payload.get("success") is True:
            return True
        code = payload.get("code")
        if code is not None:
            code_text = str(code).lower()
            if code_text in {"0", "200", "ok", "success", "true"}:
                return True
            if code_text.isdigit() and 200 <= int(code_text) < 300:
                return True
        status = payload.get("status")
        if status is not None:
            return str(status).lower() in {"ok", "success", "done"}
        return True

    def _position_side_and_amount(self, payload: Dict[str, Any]) -> Tuple[PositionSide, Decimal]:
        raw_amount = self._decimal_from_keys(
            payload,
            ["size", "qty", "quantity", "positionAmt", "amount", "positionSize"],
            default=Decimal("0"),
        )
        side_text = str(
            payload.get("side")
            or payload.get("positionSide")
            or payload.get("direction")
            or ""
        ).strip().lower()
        if side_text in {"short", "sell"}:
            side = PositionSide.SHORT
        elif side_text in {"long", "buy"}:
            side = PositionSide.LONG
        elif raw_amount < Decimal("0"):
            side = PositionSide.SHORT
        else:
            side = PositionSide.LONG
        return side, abs(raw_amount)

    def _extract_timestamp(self, payload: Dict[str, Any], default: float) -> float:
        if not isinstance(payload, dict):
            return float(default)
        timestamp = None
        for key in ("timestamp", "time", "ts", "updatedAt", "updateTime", "createdAt", "createdTime"):
            value = payload.get(key)
            if value is not None:
                timestamp = value
                break
        if timestamp is None:
            return float(default)
        try:
            ts = float(timestamp)
        except Exception:
            return float(default)
        if ts > 1e12:
            ts /= 1000.0
        elif ts > 1e11:
            ts /= 1000.0
        return float(ts)

    def _decimal_from_keys(self, payload: Dict[str, Any], keys: List[str], default: Optional[Decimal]) -> Optional[Decimal]:
        if not isinstance(payload, dict):
            return default
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            try:
                if isinstance(value, Decimal):
                    return value
                if isinstance(value, (float, int)) and not math.isfinite(float(value)):
                    continue
                return Decimal(str(value))
            except Exception:
                continue
        return default

    def _quantize_size_for_api(self, trading_pair: str, amount: Decimal) -> Decimal:
        rule = self._trading_rules.get(trading_pair)
        if rule is None:
            return amount
        step = getattr(rule, "min_base_amount_increment", None) or getattr(rule, "min_order_size", None)
        if step is None:
            return amount
        return self._truncate_to_step(value=amount, step=step)

    def _quantize_price_for_api(self, trading_pair: str, price: Decimal) -> Decimal:
        rule = self._trading_rules.get(trading_pair)
        if rule is None:
            return price
        tick = getattr(rule, "min_price_increment", None)
        if tick is None:
            return price
        return self._truncate_to_step(value=price, step=tick)

    def _truncate_to_step(self, value: Decimal, step: Decimal) -> Decimal:
        step_decimal = Decimal(str(step))
        value_decimal = Decimal(str(value))
        if step_decimal <= Decimal("0"):
            return value_decimal
        if value_decimal == Decimal("0"):
            return Decimal("0")
        return (value_decimal // step_decimal) * step_decimal
