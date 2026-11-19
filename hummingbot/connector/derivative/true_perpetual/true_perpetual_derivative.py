import asyncio
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.derivative.true_perpetual import (
    true_perpetual_constants as CONSTANTS,
    true_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.true_perpetual.true_perpetual_api_order_book_data_source import (
    TruePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.true_perpetual.true_perpetual_auth import TruePerpetualAuth
from hummingbot.connector.derivative.true_perpetual.true_perpetual_user_stream_data_source import (
    TruePerpetualUserStreamDataSource,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

QUOTE_ASSET = "USDC"


class TruePerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for TRUE perps (app.truefinance.ai) over the TRUE Bot API.

    Keys come from the Bots tab (app.truefinance.ai/bots): a key id (tbk_...) and a secret (tbs_...),
    bound to one venue account with read or read+trade scope. Every write goes through the same
    guards as the app (lot alignment, price bands, leverage caps, daily loss limit, emergency stop),
    and a bot key can never withdraw or transfer.
    """

    web_utils = web_utils

    # The account stream carries balances and positions but not fills, so orders are polled at a steady pace.
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 5.0
    MARKETS_CACHE_SECONDS = 60.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            true_perpetual_api_key: str = None,
            true_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.true_perpetual_api_key = true_perpetual_api_key
        self.true_perpetual_api_secret = true_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._markets_cache: Dict[str, Dict[str, Any]] = {}
        self._markets_cache_at: float = 0.0
        self._ws_token: Optional[str] = None
        self._ws_token_expires_at: float = 0.0
        self._fills_cache: Dict[str, List[Dict[str, Any]]] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    # ── identity ────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> TruePerpetualAuth:
        return TruePerpetualAuth(
            api_key=self.true_perpetual_api_key,
            api_secret=self.true_perpetual_api_secret,
            time_provider=self._time_synchronizer,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.CLIENT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 600

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return QUOTE_ASSET

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return QUOTE_ASSET

    def time_synchronizer_time(self) -> float:
        return self._time_synchronizer.time()

    # ── error classification ────────────────────────────────────────────────

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return "timestamp_out_of_window" in str(request_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        text = str(cancelation_exception)
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in text or "order_not_open" in text or "not found" in text.lower()

    # ── factories ───────────────────────────────────────────────────────────

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return TruePerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return TruePerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    # ── shared reads ────────────────────────────────────────────────────────

    async def markets(self) -> Dict[str, Dict[str, Any]]:
        """GET /markets, cached for a minute, keyed by venue symbol (BTCUSDC)."""
        now = time.time()
        if not self._markets_cache or now - self._markets_cache_at > self.MARKETS_CACHE_SECONDS:
            response = await self._api_get(path_url=CONSTANTS.MARKETS_PATH_URL)
            rows = response.get("markets", []) if isinstance(response, dict) else []
            self._markets_cache = {str(m.get("symbol")): m for m in rows if m.get("symbol")}
            self._markets_cache_at = now
        return self._markets_cache

    def cached_market_info(self, symbol: str) -> Dict[str, Any]:
        """The market row from the last GET /markets without touching the network (empty when never read)."""
        return self._markets_cache.get(symbol, {})

    def markets_cache_is_fresh(self) -> bool:
        return bool(self._markets_cache) and time.time() - self._markets_cache_at <= self.MARKETS_CACHE_SECONDS

    async def market_info(self, symbol: str) -> Dict[str, Any]:
        markets = await self.markets()
        if symbol not in markets:
            self._markets_cache_at = 0.0
            markets = await self.markets()
        return markets.get(symbol, {})

    async def ws_token(self) -> Optional[str]:
        """POST /ws-token (signed) answers a one hour token for the market data websocket."""
        if not self._auth.configured:
            return None
        if self._ws_token and time.time() < self._ws_token_expires_at - 60:
            return self._ws_token
        try:
            response = await self._api_post(path_url=CONSTANTS.WS_TOKEN_PATH_URL, data={}, is_auth_required=True)
            self._ws_token = response.get("token")
            self._ws_token_expires_at = float(response.get("expiresAt", 0)) / 1e3
        except Exception as err:
            self.logger().warning(f"Could not fetch a TRUE websocket token ({err}); connecting without one.")
            self._ws_token = None
        return self._ws_token

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        response = await self._api_get(path_url=CONSTANTS.TICKER_PATH_URL, params={"market": "ALL"})
        rows = (response.get("data") or {}).get("results") or []
        by_symbol = {str(r.get("symbol")): r for r in rows}
        prices: Dict[str, float] = {}
        for trading_pair in trading_pairs:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            row = by_symbol.get(symbol)
            if row and row.get("last_traded_price") is not None:
                prices[trading_pair] = float(row["last_traded_price"])
        return prices

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        prices = await self.get_last_traded_prices([trading_pair])
        return prices.get(trading_pair, 0.0)

    # ── trading rules and symbols ───────────────────────────────────────────

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for market in exchange_info.get("markets", []):
            if not web_utils.is_exchange_information_valid(market):
                continue
            symbol = str(market["symbol"])
            base = str(market.get("base") or symbol.replace(QUOTE_ASSET, ""))
            quote = str(market.get("quote") or QUOTE_ASSET)
            mapping[symbol] = combine_to_hb_trading_pair(base=base, quote=quote)
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules: List[TradingRule] = []
        for market in exchange_info_dict.get("markets", []):
            if not web_utils.is_exchange_information_valid(market):
                continue
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market["symbol"])
                lot = Decimal(str(market["lotSize"]))
                tick = Decimal(str(market["tickSize"]))
                min_notional = Decimal(str(market.get("minOrderNotionalUsd") or "0"))
                rule_kwargs = {}
                if market.get("maxOrderSize"):
                    rule_kwargs["max_order_size"] = Decimal(str(market["maxOrderSize"]))
                rules.append(TradingRule(
                    trading_pair,
                    min_order_size=lot,
                    min_price_increment=tick,
                    min_base_amount_increment=lot,
                    min_notional_size=min_notional,
                    buy_order_collateral_token=QUOTE_ASSET,
                    sell_order_collateral_token=QUOTE_ASSET,
                    **rule_kwargs,
                ))
            except Exception:
                self.logger().exception(f"Error parsing the trading rule for {market}. Skipping.")
        return rules

    async def _update_trading_fees(self):
        markets = await self.markets()
        for trading_pair in self._trading_pairs or []:
            try:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                market = markets.get(symbol) or {}
                maker = market.get("makerFeePct")
                taker = market.get("takerFeePct")
                if maker is not None and taker is not None:
                    self._trading_fees[trading_pair] = {
                        "maker": Decimal(str(maker)) / Decimal("100"),
                        "taker": Decimal(str(taker)) / Decimal("100"),
                    }
            except Exception:
                self.logger().debug(f"Could not read fees for {trading_pair}", exc_info=True)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker if is_maker is not None else (order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER))
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        fees = self._trading_fees.get(trading_pair)
        if fees:
            percent = fees["maker"] if is_maker else fees["taker"]
            return TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent=percent,
                percent_token=QUOTE_ASSET,
            )
        return build_perpetual_trade_fee(
            self.name,
            is_maker,
            position_action=position_action,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    # ── orders ──────────────────────────────────────────────────────────────

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
        body: Dict[str, Any] = {
            "market": symbol,
            "side": "buy" if trade_type == TradeType.BUY else "sell",
            "type": "market" if order_type == OrderType.MARKET else "limit",
            "size": f"{amount:f}",
            "postOnly": order_type == OrderType.LIMIT_MAKER,
            "reduceOnly": position_action == PositionAction.CLOSE,
            "clientOrderId": order_id,
        }
        if order_type != OrderType.MARKET:
            body["price"] = f"{price:f}"
        response = await self._api_post(
            path_url=CONSTANTS.PLACE_ORDER_PATH_URL,
            data=body,
            is_auth_required=True,
            return_err=True,
        )
        if not response.get("ok"):
            raise IOError(f"Order refused by TRUE: {response.get('error')} {response.get('message') or ''}".strip())
        order = response.get("order") or {}
        exchange_order_id = order.get("id") or order.get("order_id") or order.get("orderId")
        if exchange_order_id is None:
            raise IOError(f"TRUE accepted the order but returned no id: {response}")
        transact_time = float(order.get("timestamp") or time.time() * 1e3) / 1e3
        return str(exchange_order_id), transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        response = await self._api_delete(
            path_url=web_utils.order_path(exchange_order_id),
            params={"market": symbol},
            is_auth_required=True,
            return_err=True,
            limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID,
        )
        if response.get("ok"):
            return True
        error = str(response.get("error") or "")
        detail = response.get("detail")
        detail_text = str(detail) if detail is not None else ""
        if self._is_order_not_found_during_cancelation_error(IOError(f"{error} {detail_text}")):
            # The base class counts the not found answer when this error is raised; nothing to count here.
            self.logger().debug(f"Order {order_id} ({exchange_order_id}) is no longer open on TRUE.")
            raise IOError(f"{CONSTANTS.ORDER_NOT_FOUND_ERROR}: {error} {detail_text}".strip())
        raise IOError(f"Cancel refused by TRUE: {error} {detail_text}".strip())

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        response = await self._api_get(
            path_url=web_utils.order_path(exchange_order_id),
            params={"market": symbol},
            is_auth_required=True,
            return_err=True,
            limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID,
        )
        if not response.get("ok"):
            error = str(response.get("error") or "unknown")
            raise IOError(f"{error}: {response.get('message') or ''}".strip())
        order = response.get("order") or {}
        status = str(order.get("status") or "").lower()
        new_state = CONSTANTS.ORDER_STATE.get(status)
        if new_state is None:
            # Older servers hand the venue word through: "closed" is settled, cancel_reason says why.
            remaining = Decimal(str(order.get("remainingSize") or "0"))
            filled = Decimal(str(order.get("filledSize") or "0"))
            cancel_reason = str(order.get("cancelReason") or "").lower()
            if status == "closed" or cancel_reason:
                new_state = OrderState.FILLED if remaining == 0 and filled > 0 and not cancel_reason else OrderState.CANCELED
            else:
                new_state = OrderState.FILLED if remaining == 0 and filled > 0 else (
                    OrderState.PARTIALLY_FILLED if filled > 0 else OrderState.OPEN)
        timestamp = float(order.get("timestamp") or time.time() * 1e3) / 1e3
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=max(timestamp, self.current_timestamp),
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(exchange_order_id),
        )

    FILLS_PAGE_SIZE = 200
    FILLS_MAX_PAGES = 50

    async def _fills_for_market(self, symbol: str, limit: int = FILLS_PAGE_SIZE,
                                since_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        GET /fills for one market, newest first, following page.next until the page is older than
        since_ms (the oldest tracked order for that market). FILLS_MAX_PAGES (10,000 fills) is only a
        guard against a runaway cursor; the since bound is what ends the walk in practice.
        """
        fills: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(self.FILLS_MAX_PAGES):
            params: Dict[str, Any] = {"market": symbol, "limit": limit}
            if cursor:
                params["cursor"] = cursor
            response = await self._api_get(
                path_url=CONSTANTS.FILLS_PATH_URL,
                params=params,
                is_auth_required=True,
            )
            page = response.get("page") or response
            rows = list(page.get("results") or [])
            fills.extend(rows)
            cursor = page.get("next")
            if not rows or not cursor or len(rows) < limit:
                break
            if since_ms is not None:
                oldest = min((int(r.get("created_at") or 0) for r in rows), default=0)
                if oldest and oldest < since_ms:
                    break
        return fills

    def _trade_update_from_fill(self, fill: Dict[str, Any], order: InFlightOrder) -> TradeUpdate:
        fee_amount = Decimal(str(fill.get("fee") or "0"))
        fee_token = str(fill.get("fee_currency") or QUOTE_ASSET)
        # A fill fee on TRUE is always taken from the USDC collateral, so it is a cost whichever way the
        # position moves; an order tracked without a position action is treated as opening one.
        position_action = order.position if order.position in (PositionAction.OPEN, PositionAction.CLOSE) else PositionAction.OPEN
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_token,
            flat_fees=[] if fee_amount == 0 else [TokenAmount(amount=fee_amount, token=fee_token)],
        )
        price = Decimal(str(fill["price"]))
        size = abs(Decimal(str(fill["size"])))
        return TradeUpdate(
            trade_id=str(fill.get("id")),
            client_order_id=order.client_order_id,
            exchange_order_id=str(fill.get("order_id")),
            trading_pair=order.trading_pair,
            fill_timestamp=float(fill.get("created_at") or time.time() * 1e3) / 1e3,
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=size * price,
            fee=fee,
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if order.exchange_order_id is None:
            return []
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        fills = self._fills_cache.get(symbol)
        if fills is None:
            fills = await self._fills_for_market(symbol)
        wanted = str(order.exchange_order_id)
        return [self._trade_update_from_fill(f, order) for f in fills if str(f.get("order_id")) == wanted]

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        """One paged GET /fills per market per poll instead of one per order."""
        self._fills_cache = {}
        try:
            oldest_by_symbol: Dict[str, int] = {}
            for order in orders:
                if order.exchange_order_id is not None:
                    symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
                    created_ms = int(order.creation_timestamp * 1e3)
                    oldest_by_symbol[symbol] = min(oldest_by_symbol.get(symbol, created_ms), created_ms)
            for symbol, since_ms in oldest_by_symbol.items():
                try:
                    self._fills_cache[symbol] = await self._fills_for_market(symbol, since_ms=since_ms)
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    self.logger().warning(f"Failed to fetch TRUE fills for {symbol}: {err}")
            await super()._update_orders_fills(orders)
        finally:
            self._fills_cache = {}

    # ── balances and positions ──────────────────────────────────────────────

    def _apply_account_snapshot(self, snapshot: Dict[str, Any]):
        account = snapshot.get("account") or {}
        equity = account.get("equityUsd")
        free = account.get("freeCollateralUsd")
        if equity is not None:
            self._account_balances[QUOTE_ASSET] = Decimal(str(equity))
        if free is not None:
            self._account_available_balances[QUOTE_ASSET] = Decimal(str(free))

    async def _update_balances(self):
        response = await self._api_get(path_url=CONSTANTS.ACCOUNT_PATH_URL, is_auth_required=True)
        self._apply_account_snapshot(response)
        if response.get("positionsOk", True) and isinstance(response.get("positions"), list):
            await self._apply_positions(response["positions"])

    async def _apply_positions(self, rows: List[Dict[str, Any]]):
        seen = set()
        for row in rows:
            symbol = str(row.get("market") or "")
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            except Exception:
                continue
            size = Decimal(str(row.get("size") or "0"))
            pos_key = self._perpetual_trading.position_key(trading_pair, PositionSide.LONG if size >= 0 else PositionSide.SHORT)
            if size == 0:
                self._perpetual_trading.remove_position(pos_key)
                continue
            seen.add(trading_pair)
            self._perpetual_trading.set_position(pos_key, Position(
                trading_pair=trading_pair,
                position_side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                unrealized_pnl=Decimal(str(row.get("unrealized_pnl") or "0")),
                entry_price=Decimal(str(row.get("entry_price") or "0")),
                amount=size,
                leverage=Decimal(str(row.get("leverage") or "1")),
            ))
        for pos_key in list(self._perpetual_trading.account_positions.keys()):
            position = self._perpetual_trading.account_positions[pos_key]
            if position.trading_pair not in seen:
                self._perpetual_trading.remove_position(pos_key)

    async def _update_positions(self):
        response = await self._api_get(path_url=CONSTANTS.POSITIONS_PATH_URL, is_auth_required=True)
        if response.get("positionsOk", True):
            await self._apply_positions(response.get("positions") or [])

    # ── leverage, position mode, funding ────────────────────────────────────

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_post(
            path_url=CONSTANTS.LEVERAGE_PATH_URL,
            data={"market": symbol, "leverage": int(leverage)},
            is_auth_required=True,
            return_err=True,
        )
        if response.get("ok"):
            return True, ""
        message = f"{response.get('error')} {response.get('message') or ''}".strip()
        if response.get("maxLeverage") is not None:
            message = f"{message} (max {response['maxLeverage']}x on {symbol})"
        return False, message

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode == PositionMode.ONEWAY:
            return True, ""
        return False, "TRUE perps run one position per market (ONEWAY); hedge mode is not available."

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        # Funding is settled into the position's realized pnl at the venue; there is no per payment feed yet.
        return 0, Decimal("-1"), Decimal("-1")

    # ── user stream ─────────────────────────────────────────────────────────

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 second.",
                    exc_info=True,
                    app_warning_msg="Could not read the TRUE account stream. Check the bot key and network.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event in self._iter_user_event_queue():
            try:
                kind = event.get("event")
                data = event.get("data") or {}
                if kind == "account":
                    self._apply_account_snapshot(data)
                    if data.get("positionsOk", True) and isinstance(data.get("positions"), list):
                        await self._apply_positions(data["positions"])
                elif kind == "warning":
                    self.logger().debug(f"TRUE account stream warning: {data}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(1.0)

    # ── request helpers ─────────────────────────────────────────────────────

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
        )
