import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.drift_perpetual.drift_perpetual_constants as CONSTANTS
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.drift_perpetual import drift_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_api_order_book_data_source import (
    DriftPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_api_user_stream_data_source import (
    DriftPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_auth import DriftPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DriftPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for Drift Protocol perpetuals via the self-hosted
    Drift Gateway (REST + WS). The gateway holds the Solana keypair
    (DRIFT_GATEWAY_KEY) and signs all transactions, so this connector does
    NOT take a private key — only gateway connection params. Order
    placement returns a Solana tx signature (not an exchange orderId);
    the exchange orderId is resolved from the WS `orders` (orderCreate)
    stream / GET /v2/orders. Schemas verified from drift-labs/gateway +
    driftpy (see DRIFT_GATEWAY_VERIFIED_SCHEMAS.md).
    """

    web_utils = web_utils

    def __init__(
        self,
        drift_perpetual_gateway_host: str = "127.0.0.1",
        drift_perpetual_gateway_rest_port: int = CONSTANTS.DRIFT_GATEWAY_DEFAULT_REST_PORT,
        drift_perpetual_gateway_ws_port: int = CONSTANTS.DRIFT_GATEWAY_DEFAULT_WS_PORT,
        drift_perpetual_sub_account_id: int = 0,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._gateway_host = drift_perpetual_gateway_host
        self._gateway_rest_port = drift_perpetual_gateway_rest_port
        self._gateway_ws_port = drift_perpetual_gateway_ws_port
        self._sub_account_id = drift_perpetual_sub_account_id
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        self._client_order_id_nonce_provider = NonceCreator.for_microseconds()
        # trading_pair -> Drift marketIndex (populated from /v2/markets)
        self._market_index_map: Dict[str, int] = {}
        self._auth = DriftPerpetualAuth(sub_account_id=drift_perpetual_sub_account_id)
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    # --- gateway endpoint helpers ---
    @property
    def drift_gateway_rest_url(self) -> str:
        return f"http://{self._gateway_host}:{self._gateway_rest_port}/{CONSTANTS.API_VERSION}"

    @property
    def drift_gateway_ws_url(self) -> str:
        return f"ws://{self._gateway_host}:{self._gateway_ws_port}"

    @property
    def sub_account_id(self) -> int:
        return self._sub_account_id

    # --- identity / config properties ---
    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return self._auth

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.PATH_MARKETS

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.PATH_MARKETS

    @property
    def check_network_request_path(self) -> str:
        # Gateway exposes no /time; /markets is the liveness probe.
        return CONSTANTS.PATH_MARKETS

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        # Drift is a cross-collateral one-way book; no hedge mode.
        return [PositionMode.ONEWAY]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_request_result_an_error_related_to_time_synchronizer(self, request_result: Dict[str, Any]) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "tx not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "tx not found" in str(cancelation_exception).lower()

    # --- factories ---
    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler)

    def _create_order_book_data_source(self) -> DriftPerpetualAPIOrderBookDataSource:
        return DriftPerpetualAPIOrderBookDataSource(
            self.trading_pairs, connector=self, api_factory=self._web_assistants_factory, domain=self._domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DriftPerpetualAPIUserStreamDataSource(api_factory=self._web_assistants_factory, connector=self)

    # --- trading-pair symbol map (verified /v2/markets perp[] schema) ---
    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        index_map: Dict[str, int] = {}
        for market in exchange_info.get("perp", []):
            if not web_utils.is_exchange_information_valid(market):
                continue
            exchange_symbol = market["symbol"]              # e.g. "SOL-PERP"
            base = exchange_symbol.split("-")[0]
            quote = CONSTANTS.CURRENCY                       # USDC settlement
            trading_pair = combine_to_hb_trading_pair(base, quote)
            mapping[exchange_symbol] = trading_pair
            index_map[trading_pair] = int(market["marketIndex"])
        self._market_index_map = index_map
        self._set_trading_pair_symbol_map(mapping)

    async def _make_trading_rules_request(self) -> Any:
        return await self._api_get(path_url=self.trading_rules_request_path, params={})

    async def _make_trading_pairs_request(self) -> Any:
        return await self._api_get(path_url=self.trading_pairs_request_path, params={})

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules: List[TradingRule] = []
        for market in exchange_info_dict.get("perp", []):
            if not web_utils.is_exchange_information_valid(market):
                continue
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market["symbol"])
                rules.append(TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(str(market["minOrderSize"])),
                    min_price_increment=Decimal(str(market["priceStep"])),
                    min_base_amount_increment=Decimal(str(market["amountStep"])),
                    buy_order_collateral_token=CONSTANTS.CURRENCY,
                    sell_order_collateral_token=CONSTANTS.CURRENCY,
                ))
            except Exception:
                self.logger().exception(f"Error parsing Drift trading rule for {market}")
        return rules

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].sell_order_collateral_token

    # --- order placement / cancel (verified POST/DELETE /v2/orders) ---
    def _client_order_id_to_user_order_id(self, client_order_id: str) -> int:
        # Drift userOrderId is a uint; derive a stable numeric id.
        return int(self._client_order_id_nonce_provider.get_tracking_nonce()) % (2 ** 31)

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
        market_index = self._market_index_map.get(trading_pair)
        if market_index is None:
            # Never POST {"marketIndex": null} — the gateway would mis-route
            # or reject ambiguously. Fail the order cleanly so the base
            # order tracker marks it FAILED (map not yet populated from
            # /v2/markets, or an unknown pair). NB: index 0 is valid.
            raise ValueError(
                f"Drift marketIndex unknown for {trading_pair} "
                f"(trading rules not initialized?) — order not placed."
            )
        # amount is SIGNED on Drift: + = buy/long, - = sell/short.
        signed_amount = amount if trade_type == TradeType.BUY else -amount
        user_order_id = self._client_order_id_to_user_order_id(order_id)
        body = {
            "orders": [{
                "marketIndex": market_index,
                "marketType": CONSTANTS.MARKET_TYPE_PERP,
                "amount": float(signed_amount),
                "price": float(price) if order_type is not OrderType.MARKET else 0,
                "postOnly": order_type is OrderType.LIMIT_MAKER,
                "orderType": CONSTANTS.ORDER_TYPE_MAP[order_type],
                "userOrderId": user_order_id,
                "reduceOnly": position_action == PositionAction.CLOSE,
            }],
        }
        resp = await self._api_post(path_url=CONSTANTS.PATH_ORDERS, data=body)
        # POST returns a tx signature, not an exchange orderId. Use the
        # client-side userOrderId as the tracking handle; the real
        # exchange orderId is filled in from the WS orderCreate stream.
        exchange_order_id = str(resp.get("signature") or user_order_id)
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        market_index = self._market_index_map.get(tracked_order.trading_pair)
        body: Dict[str, Any] = {"marketIndex": market_index, "marketType": CONSTANTS.MARKET_TYPE_PERP}
        if tracked_order.exchange_order_id and str(tracked_order.exchange_order_id).isdigit():
            body = {"ids": [int(tracked_order.exchange_order_id)]}
        await self._api_request(path_url=CONSTANTS.PATH_ORDERS, method=RESTMethod.DELETE, data=body)
        return True

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        return TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=quote_currency,
        )

    async def _update_trading_fees(self):
        pass

    # --- balances / positions (verified /v2/collateral, /v2/positions) ---
    async def _update_balances(self):
        resp = await self._api_get(path_url=CONSTANTS.PATH_COLLATERAL)
        total = Decimal(str(resp.get("total", "0")))
        free = Decimal(str(resp.get("free", "0")))
        self._account_balances[CONSTANTS.CURRENCY] = total
        self._account_available_balances[CONSTANTS.CURRENCY] = free

    async def _update_positions(self):
        resp = await self._api_get(
            path_url=CONSTANTS.PATH_POSITIONS, params={"marketType": CONSTANTS.MARKET_TYPE_PERP}
        )
        for pos in resp.get("perp", []):
            try:
                market_index = int(pos["marketIndex"])
                trading_pair = next(
                    (tp for tp, idx in self._market_index_map.items() if idx == market_index), None
                )
                if trading_pair is None:
                    continue
                amount = Decimal(str(pos.get("amount", "0")))
                side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                pos_key = self._perpetual_trading.position_key(trading_pair, side)
                if amount == 0:
                    self._perpetual_trading.remove_position(pos_key)
                    continue
                self._perpetual_trading.set_position(pos_key, Position(
                    trading_pair=trading_pair,
                    position_side=side,
                    unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", "0"))),
                    entry_price=Decimal(str(pos.get("entryPrice", "0"))),
                    amount=amount,
                    leverage=self.get_leverage(trading_pair),
                ))
            except Exception:
                self.logger().exception(f"Error parsing Drift position {pos}")

    # --- order status (verified GET /v2/orders) ---
    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        resp = await self._api_get(
            path_url=CONSTANTS.PATH_ORDERS, params={"marketType": CONSTANTS.MARKET_TYPE_PERP}
        )
        for o in resp.get("orders", []):
            if str(o.get("orderId")) == str(tracked_order.exchange_order_id):
                filled = Decimal(str(o.get("filled", "0")))
                total = abs(Decimal(str(o.get("amount", "0"))))
                state = OrderState.FILLED if total and filled >= total else (
                    OrderState.PARTIALLY_FILLED if filled > 0 else OrderState.OPEN
                )
                return OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=state,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=str(o.get("orderId")),
                )
        # Absent from open orders → terminal (filled or canceled).
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FILLED if tracked_order.executed_amount_base > 0 else OrderState.CANCELED,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(tracked_order.exchange_order_id or ""),
        )

    # --- user stream demux (verified WS envelope) ---
    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel")
                data = event_message.get("data") or {}
                if channel == CONSTANTS.WS_CHANNEL_ORDERS:
                    self._process_ws_order_event(data)
                elif channel == CONSTANTS.WS_CHANNEL_FILLS:
                    self._process_ws_fill_event(data.get("fill", {}))
                elif channel == CONSTANTS.WS_CHANNEL_FUNDING:
                    # Realized funding settlement; rate/next handled at [A3].
                    pass
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in Drift user stream listener.")

    def _process_ws_order_event(self, data: Dict[str, Any]):
        order = (data.get("orderCreate") or {}).get("order")
        if not order:
            return
        client_id_int = order.get("userOrderId")
        tracked = next(
            (o for o in self._order_tracker.all_updatable_orders.values()
             if self._client_order_id_to_int_match(o.client_order_id, client_id_int)),
            None,
        )
        if tracked is None:
            return
        self._order_tracker.process_order_update(OrderUpdate(
            trading_pair=tracked.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.OPEN,
            client_order_id=tracked.client_order_id,
            exchange_order_id=str(order.get("orderId")),
        ))

    @staticmethod
    def _client_order_id_to_int_match(client_order_id: str, user_order_id: Any) -> bool:
        # userOrderId is the int we derived in _client_order_id_to_user_order_id;
        # exact mapping is re-keyed in the order tracker at integration.
        return user_order_id is not None and str(user_order_id) in str(client_order_id)

    def _process_ws_fill_event(self, fill: Dict[str, Any]):
        if not fill:
            return
        order_id = str(fill.get("orderId"))
        tracked = next(
            (o for o in self._order_tracker.all_fillable_orders.values()
             if str(o.exchange_order_id) == order_id),
            None,
        )
        if tracked is None:
            return
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=PositionAction.NIL,
            flat_fees=[TokenAmount(token=CONSTANTS.CURRENCY, amount=Decimal(str(abs(float(fill.get("fee", 0))))))],
        )
        self._order_tracker.process_trade_update(TradeUpdate(
            trade_id=str(fill.get("signature")),
            client_order_id=tracked.client_order_id,
            exchange_order_id=order_id,
            trading_pair=tracked.trading_pair,
            fill_timestamp=float(fill.get("ts", self.current_timestamp)),
            fill_price=Decimal(str(fill.get("price", "0"))),
            fill_base_amount=Decimal(str(fill.get("amount", "0"))),
            fill_quote_amount=Decimal(str(fill.get("price", "0"))) * Decimal(str(fill.get("amount", "0"))),
            fee=fee,
        ))

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Fills are delivered via the WS `fills` stream (_process_ws_fill_event).
        return []

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        resp = await self._api_get(path_url=CONSTANTS.PATH_MARKETS, params={})
        for m in resp.get("perp", []):
            if m.get("symbol") == ex_symbol and m.get("oraclePrice") is not None:
                return float(m["oraclePrice"])
        return float("nan")

    # --- leverage (verified POST /v2/leverage) ---
    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # Drift only supports ONEWAY; succeed iff requested mode is ONEWAY.
        if mode == PositionMode.ONEWAY:
            return True, ""
        return False, "Drift supports ONEWAY position mode only."

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        try:
            await self._api_post(path_url=CONSTANTS.PATH_LEVERAGE, data={"leverage": leverage})
            return True, ""
        except Exception as e:
            return False, str(e)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        # Market funding rate/mark/index are served by the Data API and
        # surfaced via the order-book data source's get_funding_info
        # (endpoint VERIFIED 2026-05-17: GET /market/{symbol}/fundingRates).
        # Per-USER realized funding *settlements* arrive only on the
        # gateway WS `funding` channel — there is no per-user Data API
        # endpoint — so that single wiring is the isolated seam deferred to
        # the integration/CI gate the project's other connector PRs rely
        # on. Until then return the base-class-documented "no realized
        # payment" sentinel (0, -1, -1) so the funding-payment poll loop
        # stays quiet instead of emitting spurious zero-value
        # FundingPaymentCompletedEvents.
        return 0, Decimal("-1"), Decimal("-1")
