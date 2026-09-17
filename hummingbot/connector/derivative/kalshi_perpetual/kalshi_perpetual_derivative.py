import asyncio
import time
from copy import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Set, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.kalshi_perpetual import (
    kalshi_perpetual_constants as CONSTANTS,
    kalshi_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_api_order_book_data_source import (
    KalshiPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_api_user_stream_data_source import (
    KalshiPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_auth import KalshiPerpetualAuth
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KalshiPerpetualBudgetChecker(PerpetualBudgetChecker):
    """
    Executors reserve an order's margin with their own configured leverage, which Kalshi doesn't use: its margin follows
    from its own rates. Each order's leverage is capped at Kalshi's for the order's side and notional, so orders Kalshi
    would reject for margin aren't approved.
    """

    def populate_collateral_entries(self, order_candidate: OrderCandidate) -> OrderCandidate:
        if isinstance(order_candidate, PerpetualOrderCandidate) and not order_candidate.position_close:
            notional = order_candidate.amount * order_candidate.price
            max_leverage = self._exchange.max_leverage(
                order_candidate.trading_pair, order_candidate.order_side,
                notional if notional.is_finite() else Decimal("0"))
            if max_leverage is not None and order_candidate.leverage > max_leverage:
                order_candidate = copy(order_candidate)
                order_candidate.leverage = max_leverage
        return super().populate_collateral_entries(order_candidate)


class KalshiPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Kalshi quotes margin markets per contract, while Hummingbot works in underlying units: prices are divided and
    sizes multiplied by each market's contract size when read from Kalshi, and the reverse when sent to it.
    """
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0
    # Balance and position refreshes triggered by the user stream run at most this often: a balance request costs
    # BALANCE_REQUEST_COST of the READ_TOKENS_PER_SECOND read budget.
    ACCOUNT_REFRESH_MIN_INTERVAL = 1.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            kalshi_perpetual_api_key: str = None,
            kalshi_perpetual_private_key: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.kalshi_perpetual_api_key = kalshi_perpetual_api_key
        self.kalshi_perpetual_private_key = kalshi_perpetual_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._contract_sizes: Dict[str, Decimal] = {}
        self._tick_sizes: Dict[str, Decimal] = {}
        # trading pair -> side -> (notional in USD, leverage) tiers, in increasing notional
        self._leverage_estimates: Dict[str, Dict[TradeType, List[Tuple[Decimal, Decimal]]]] = {}
        # Margin totals of the last balance response (initial_margin, maintenance_margin, resting_orders_margin)
        self._margin_breakdown: Dict[str, Decimal] = {}
        # Orders the last balance response already accounts for (see get_available_balance)
        self._orders_in_balance: Set[str] = set()
        self._account_refresh_task: Optional[asyncio.Task] = None
        self._balance_refresh_pending = False
        self._positions_refresh_pending = False
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        self._budget_checker = KalshiPerpetualBudgetChecker(self)
        # real_time_balance_update stays True although there is no balance channel: Kalshi computes the available
        # margin itself, which the base class's estimate between polls (it treats fills as spot trades) would distort.

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> Optional[KalshiPerpetualAuth]:
        # Without credentials there is no auth, and no market data either: the websocket handshake is signed.
        if not self.kalshi_perpetual_private_key:
            return None
        return KalshiPerpetualAuth(
            api_key=self.kalshi_perpetual_api_key,
            private_key=self.kalshi_perpetual_private_key,
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
        return CONSTANTS.EXCHANGE_STATUS_PATH_URL

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
        return CONSTANTS.FUNDING_FEE_POLL_INTERVAL

    def supported_order_types(self) -> List[OrderType]:
        # MARKET orders are sent as immediate-or-cancel limit orders (see _place_order)
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].sell_order_collateral_token

    def get_contract_size(self, trading_pair: str) -> Decimal:
        """
        Underlying units per contract (e.g. 0.0001 for BTC-USD). Known once the symbol map is initialized.
        """
        return self._contract_sizes[trading_pair]

    def max_leverage(self, trading_pair: str, trade_type: TradeType,
                     notional: Decimal = Decimal("0")) -> Optional[Decimal]:
        """
        Kalshi's leverage (1 / initial margin rate) for a position of this side and notional in USD: the tier covering
        the notional, or the largest tier. None when Kalshi publishes no margin rate for the market.
        """
        tiers = self._leverage_estimates.get(trading_pair, {}).get(trade_type)
        if not tiers:
            return None
        return next((leverage for size, leverage in tiers if notional <= size), tiers[-1][1])

    def estimated_order_margin(self, order: InFlightOrder) -> Decimal:
        """
        Kalshi reports no margin per order, only the total of all resting orders: an order's is estimated as its
        remaining notional over Kalshi's leverage for its side and size, or the full notional when Kalshi publishes no
        margin rate.
        """
        if order.price is None or not order.price.is_finite():  # market orders sent without a price
            return Decimal("0")
        notional = (order.amount - order.executed_amount_base) * order.price
        return notional / (self.max_leverage(order.trading_pair, order.trade_type, notional) or Decimal("1"))

    def get_available_balance(self, currency: str) -> Decimal:
        """
        Kalshi's available balance accounts for the margin of positions and resting orders, but it is polled: orders
        sent since the last balance request are taken off with their estimated margin until a refresh includes them.
        Closing orders are left out, as the budget checker reserves nothing for them.
        """
        available = super().get_available_balance(currency)
        if currency != CONSTANTS.COLLATERAL_TOKEN:
            return available
        pending_margin = sum(
            (self.estimated_order_margin(order) for order in self.in_flight_orders.values()
             if order.client_order_id not in self._orders_in_balance and order.position is not PositionAction.CLOSE),
            Decimal("0"))
        return max(Decimal("0"), available - pending_margin)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return self._is_not_found_error(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return self._is_not_found_error(cancelation_exception)

    @staticmethod
    def _is_not_found_error(exception: Exception) -> bool:
        return "404" in str(exception) and "not_found" in str(exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return KalshiPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return KalshiPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def stop_network(self):
        if self._account_refresh_task is not None:
            self._account_refresh_task.cancel()
            self._account_refresh_task = None
        await super().stop_network()

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        return build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _update_trading_fees(self):
        """
        Fees are estimated with DEFAULT_FEES; the fees actually paid come in USD with every fill.
        """
        pass

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
        time_in_force = CONSTANTS.TIME_IN_FORCE_GTC
        if order_type is OrderType.MARKET:
            # Kalshi has no market orders: an immediate-or-cancel limit order priced through the book stands in.
            time_in_force = CONSTANTS.TIME_IN_FORCE_IOC
            is_buy = trade_type is TradeType.BUY
            slippage = (1 + CONSTANTS.MARKET_ORDER_SLIPPAGE) if is_buy else (1 - CONSTANTS.MARKET_ORDER_SLIPPAGE)
            price = self.quantize_order_price(trading_pair, self.get_price(trading_pair, is_buy=is_buy) * slippage)
        order = {
            "ticker": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "client_order_id": order_id,
            "side": "bid" if trade_type is TradeType.BUY else "ask",
            "count": self._to_exchange_count(trading_pair, amount),
            "price": self._to_exchange_price(trading_pair, price),
            "time_in_force": time_in_force,
            "self_trade_prevention_type": CONSTANTS.SELF_TRADE_PREVENTION_TYPE,
        }
        if order_type is OrderType.LIMIT_MAKER:
            order["post_only"] = True
        if position_action is PositionAction.CLOSE and time_in_force == CONSTANTS.TIME_IN_FORCE_IOC:
            order["reduce_only"] = True
        elif position_action is PositionAction.CLOSE and self._close_would_open_position(trading_pair, trade_type):
            # Kalshi rejects reduce_only on resting orders, so it's emulated. The cached position may not include the
            # fill this close follows yet, so it's refreshed before rejecting.
            await self._update_positions()
            if self._close_would_open_position(trading_pair, trade_type):
                raise ValueError(f"No {trading_pair} position for the {trade_type.name} order {order_id} to close.")
        response = await self._api_post(
            path_url=CONSTANTS.ORDERS_PATH_URL,
            data=order,
            is_auth_required=True,
            limit_id=CONSTANTS.CREATE_ORDER_LIMIT_ID)
        return str(response["order_id"]), self.current_timestamp

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        """
        The user stream can report an order filled (or an immediate order cancelled) before its creation request
        returns, and the base class would then publish OPEN anyway, bringing the finished order back to life. OPEN is
        only applied to an order still pending creation (the gemini_exchange precedent), and directly rather than
        queued: a queued update would run after a terminal update already waiting in the queue. The tracker never
        waits while applying an OPEN update, so the check and the update happen in one step.
        """
        exchange_order_id, update_timestamp = await self._place_order(
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            amount=order.amount,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            **kwargs,
        )
        if order.is_pending_create:
            await self._order_tracker._process_order_update(OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=str(exchange_order_id),
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=OrderState.OPEN,
            ))
        # Otherwise the stream update that moved the order on already carried its exchange order id.
        return exchange_order_id

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        try:
            await self._api_delete(
                path_url=CONSTANTS.ORDER_PATH_URL.format(order_id=exchange_order_id),
                is_auth_required=True,
                limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID)
        except asyncio.TimeoutError as timeout_error:
            # The base class reads a timeout as "no exchange order id yet" and counts it towards losing the order.
            raise IOError(f"The cancel request for order {order_id} timed out.") from timeout_error
        # Cancellation is synchronous: a 200 means the remaining contracts are cancelled.
        return True

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, error: Exception):
        """
        The base class counts every failed status request towards losing the order, so a network outage of a few
        polls fails orders still resting on Kalshi and stops tracking them, and their later fills are ignored. Only
        Kalshi's not_found, or an order that never got its exchange order id, counts; other errors are retried.
        """
        if (self._is_order_not_found_during_status_update_error(status_update_exception=error)
                or (isinstance(error, asyncio.TimeoutError) and order.exchange_order_id is None)):
            await super()._handle_update_error_for_active_order(order=order, error=error)
        else:
            self.logger().warning(
                f"Error fetching status update for the active order {order.client_order_id}: {error}.")

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        response = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL.format(order_id=exchange_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_LIMIT_ID)
        order = response["order"]
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._parse_timestamp(order.get("last_update_time")) or self.current_timestamp,
            new_state=self._order_state(tracked_order, order["fill_count"], order["remaining_count"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order["order_id"]),
        )

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        """
        The fills endpoint can't filter by order, so the base class's request per order downloads the same fills once
        for each tracked order, and during a network outage logs a failure with its traceback for each of them. The
        fills of all the orders are fetched with a single request instead.
        """
        # Orders without an exchange order id were never created (e.g. rejected), or their creation request hasn't
        # returned: there are no fills to fetch, and waiting for the id would hold up the status polling loop.
        orders = [order for order in orders if order.exchange_order_id is not None]
        if not orders:
            return
        try:
            fills = await self._request_fills(since=min(order.creation_timestamp for order in orders))
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            # Missed fills are fetched again on the next poll, as fills are requested since the orders' creation.
            self.logger().warning(f"Failed to fetch trade updates for {len(orders)} orders. Error: {request_error}")
            return
        for order in orders:
            for trade_update in self._trade_updates_from_fills(order=order, fills=fills):
                self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        A fill has the same id over REST (fill_id) and the websocket (trade_id), as checked against live fills, so the
        order tracker drops the fills the user stream already delivered and only the missing ones are added.
        """
        if order.exchange_order_id is None:
            return []
        return self._trade_updates_from_fills(order=order, fills=await self._request_fills(since=order.creation_timestamp))

    def _trade_updates_from_fills(self, order: InFlightOrder, fills: List[Dict[str, Any]]) -> List[TradeUpdate]:
        fills = [fill for fill in fills if fill["order_id"] == order.exchange_order_id]
        fills.sort(key=lambda fill: self._parse_timestamp(fill["created_time"]))
        return [
            self._trade_update(
                order=order,
                trade_id=fill["fill_id"],
                exchange_order_id=fill["order_id"],
                fill_timestamp=self._parse_timestamp(fill["created_time"]),
                price=fill["price"],
                count=fill["count"],
                fee_paid=fill["fees"],
            )
            for fill in fills
        ]

    async def _request_fills(self, since: float) -> List[Dict[str, Any]]:
        # The fills endpoint can't filter by order or market, only by time; it is paginated with a cursor.
        fills: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {"min_ts": int(since), "limit": 1000}
        while True:
            response = await self._api_get(path_url=CONSTANTS.FILLS_PATH_URL, params=params, is_auth_required=True)
            fills.extend(response.get("fills") or [])
            if not response.get("cursor"):
                return fills
            params["cursor"] = response["cursor"]

    def _trade_update(self, order: InFlightOrder, trade_id: str, exchange_order_id: str, fill_timestamp: float,
                      price: str, count: str, fee_paid: str) -> TradeUpdate:
        fee_amount = Decimal(fee_paid)
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=order.position,
            percent_token=CONSTANTS.COLLATERAL_TOKEN,
            flat_fees=[] if fee_amount == 0 else [TokenAmount(amount=fee_amount, token=CONSTANTS.COLLATERAL_TOKEN)],
        )
        return TradeUpdate(
            trade_id=str(trade_id),
            client_order_id=order.client_order_id,
            exchange_order_id=str(exchange_order_id),
            trading_pair=order.trading_pair,
            fill_timestamp=fill_timestamp,
            fill_price=self._from_exchange_price(order.trading_pair, price),
            fill_base_amount=self._from_exchange_count(order.trading_pair, count),
            fill_quote_amount=Decimal(price) * Decimal(count),
            fee=fee,
        )

    def _order_state(self, tracked_order: InFlightOrder, fill_count: str, remaining_count: str) -> OrderState:
        # Kalshi margin orders carry no status: it is derived from the filled and remaining contract counts.
        filled_amount = self._from_exchange_count(tracked_order.trading_pair, fill_count)
        if Decimal(remaining_count) > 0:
            return OrderState.PARTIALLY_FILLED if filled_amount > 0 else OrderState.OPEN
        return OrderState.FILLED if filled_amount >= tracked_order.amount else OrderState.CANCELED

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Kalshi. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Processes fill and order events queued by the user stream data source. Balances and positions have no
        websocket channel: order events trigger a refresh of balances and fills of both, on top of the status polling
        loop.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                if event_type == CONSTANTS.WS_FILL_MESSAGE:
                    self._process_fill_event(event_message["msg"])
                elif event_type == CONSTANTS.WS_USER_ORDER_MESSAGE:
                    self._process_order_event(event_message["msg"])
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _process_fill_event(self, fill: Dict[str, Any]):
        # Any fill moves the account's position, ours or not (e.g. a liquidation)
        self._schedule_account_refresh()
        tracked_order = (self._order_tracker.all_fillable_orders.get(fill.get("client_order_id"))
                         or self._order_tracker.all_fillable_orders_by_exchange_order_id.get(fill["order_id"]))
        if tracked_order is None:  # not ours, e.g. liquidation or take-profit/stop-loss orders placed by Kalshi
            return
        self._order_tracker.process_trade_update(self._trade_update(
            order=tracked_order,
            trade_id=fill["trade_id"],
            exchange_order_id=fill["order_id"],
            fill_timestamp=fill["ts_ms"] * 1e-3,
            price=fill["price"],
            count=fill["count"],
            fee_paid=fill["fee_cost"],
        ))

    def _schedule_account_refresh(self, positions: bool = True):
        """
        Positions and balances have no websocket channel, and while the user stream is active the status polling loop
        only refreshes them every LONG_POLL_INTERVAL, so the user stream triggers a refresh: order events change the
        margin of resting orders, fills the positions too. Events arriving while one runs trigger one more, so the
        refresh always covers the last event, at most every ACCOUNT_REFRESH_MIN_INTERVAL.
        """
        self._balance_refresh_pending = True
        self._positions_refresh_pending = self._positions_refresh_pending or positions
        if self._account_refresh_task is None or self._account_refresh_task.done():
            self._account_refresh_task = safe_ensure_future(self._refresh_account())

    async def _refresh_account(self):
        while self._balance_refresh_pending:
            refresh_positions = self._positions_refresh_pending
            self._balance_refresh_pending = self._positions_refresh_pending = False
            started = time.monotonic()
            try:
                await asyncio.gather(self._update_balances(), *([self._update_positions()] if refresh_positions else []))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Error refreshing balances and positions.",
                    exc_info=True,
                    app_warning_msg="Could not refresh Kalshi positions and balances. Check network connection.",
                )
            await self._sleep(max(0.0, started + self.ACCOUNT_REFRESH_MIN_INTERVAL - time.monotonic()))

    def _process_order_event(self, order: Dict[str, Any]):
        # Any order event changes the margin of resting orders, ours or not
        self._schedule_account_refresh(positions=False)
        tracked_order = (self._order_tracker.all_updatable_orders.get(order.get("client_order_id"))
                         or self._order_tracker.all_updatable_orders_by_exchange_order_id.get(order["order_id"]))
        if tracked_order is None:
            return
        update_timestamp_ms = order.get("last_updated_ts_ms") or order["created_ts_ms"]
        self._order_tracker.process_order_update(OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp_ms * 1e-3,
            new_state=self._order_state(tracked_order, order["fill_count"], order["remaining_count"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order["order_id"]),
        ))

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        for market in filter(web_utils.is_exchange_information_valid, exchange_info_dict.get("markets", [])):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market["ticker"])
                contract_size = Decimal(market["contract_size"])
                # Whole contracts, or hundredths of a contract when fractional trading is enabled
                contract_step = Decimal("0.01") if market["fractional_trading_enabled"] else Decimal("1")
                size_increment = contract_size * contract_step
                trading_rules.append(TradingRule(
                    trading_pair,
                    min_order_size=size_increment,
                    min_base_amount_increment=size_increment,
                    min_price_increment=Decimal(market["tick_size"]) / contract_size,
                    buy_order_collateral_token=CONSTANTS.COLLATERAL_TOKEN,
                    sell_order_collateral_token=CONSTANTS.COLLATERAL_TOKEN,
                ))
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}. Skipping...", exc_info=True)
        return trading_rules

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for market in filter(web_utils.is_exchange_information_valid, exchange_info.get("markets", [])):
            ticker = market["ticker"]
            base = ticker[len(CONSTANTS.MARKET_TICKER_PREFIX):-len(CONSTANTS.MARKET_TICKER_SUFFIX)]
            trading_pair = combine_to_hb_trading_pair(base=base, quote=CONSTANTS.COLLATERAL_TOKEN)
            mapping[ticker] = trading_pair
            # Kept here rather than with the trading rules: the data sources need them as soon as symbols resolve.
            self._contract_sizes[trading_pair] = Decimal(market["contract_size"])
            self._tick_sizes[trading_pair] = Decimal(market["tick_size"])
            self._leverage_estimates[trading_pair] = self._parse_leverage_estimates(market)
        self._set_trading_pair_symbol_map(mapping)

    @staticmethod
    def _parse_leverage_estimates(market: Dict[str, Any]) -> Dict[TradeType, List[Tuple[Decimal, Decimal]]]:
        # Keyed by notional in USD ("1000" ... "1000000"); leverage decreases as the position grows. Null without a
        # margin config or price data.
        tiers = {}
        for trade_type, key in ((TradeType.BUY, "long_leverage_estimates"), (TradeType.SELL, "short_leverage_estimates")):
            estimates = market.get(key) or market.get("leverage_estimates") or {}
            tiers[trade_type] = sorted((Decimal(size), Decimal(str(leverage)))
                                       for size, leverage in estimates.items() if leverage)
        return tiers

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.MARKET_PATH_URL.format(ticker=symbol),
            limit_id=CONSTANTS.MARKET_PATH_URL)
        return float(self._from_exchange_price(trading_pair, response["market"]["price"]))

    async def _update_balances(self):
        # Balances are in USD for the primary subaccount; available_balance is only computed on request. It includes
        # the margin of every order Kalshi acknowledged before the request.
        acknowledged = {order.client_order_id for order in self.in_flight_orders.values()
                        if order.exchange_order_id is not None}
        response = await self._api_get(
            path_url=CONSTANTS.BALANCE_PATH_URL,
            params={"compute_available_balance": "true"},
            is_auth_required=True)
        balance = next(
            (balance for balance in response.get("subaccount_balances", []) if balance["subaccount"] == 0), None)
        self._account_balances.clear()
        self._account_available_balances.clear()
        self._margin_breakdown = {}
        if balance is not None:
            self._account_balances[CONSTANTS.COLLATERAL_TOKEN] = Decimal(balance["account_equity"])
            self._account_available_balances[CONSTANTS.COLLATERAL_TOKEN] = Decimal(balance["available_balance"])
            self._margin_breakdown = {key: Decimal(balance[key])
                                      for key in ("initial_margin", "maintenance_margin", "resting_orders_margin")}
        self._orders_in_balance = acknowledged

    def _close_would_open_position(self, trading_pair: str, trade_type: TradeType) -> bool:
        position = self._perpetual_trading.get_position(trading_pair)
        return position is None or (position.amount > 0) == (trade_type is TradeType.BUY)

    async def _update_positions(self):
        requested_at = self.current_timestamp
        response = await self._api_get(
            path_url=CONSTANTS.POSITIONS_PATH_URL,
            params={"subaccount": 0},
            is_auth_required=True)
        open_position_keys = set()
        for position in response.get("positions", []):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(position["market_ticker"])
            except KeyError:
                # Ignore positions in markets the connector doesn't track
                continue
            contracts = Decimal(position["position"])  # signed: positive long, negative short
            if contracts == 0:
                continue
            position_side = PositionSide.LONG if contracts > 0 else PositionSide.SHORT
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            open_position_keys.add(pos_key)
            self._perpetual_trading.set_position(pos_key, Position(
                trading_pair=trading_pair,
                position_side=position_side,
                unrealized_pnl=Decimal(position["unrealized_pnl"]),
                entry_price=self._from_exchange_price(trading_pair, position["entry_price"]),
                amount=self._from_exchange_count(trading_pair, position["position"]),
                leverage=Decimal(self._perpetual_trading.get_leverage(trading_pair)),
            ))
        # Kalshi only lists open positions: anything no longer listed was closed.
        for pos_key in set(self._perpetual_trading.account_positions.keys()) - open_position_keys:
            self._perpetual_trading.remove_position(pos_key)
        # Resting close orders aren't reduce_only on Kalshi: once their position is gone, filling them would open one.
        # Orders placed after the request may follow a fill this response doesn't include yet, so they're checked
        # again by another refresh instead.
        for order in list(self.in_flight_orders.values()):
            if (order.position is PositionAction.CLOSE and order.is_open
                    and self._close_would_open_position(order.trading_pair, order.trade_type)):
                if order.creation_timestamp < requested_at:
                    safe_ensure_future(self._execute_cancel(order.trading_pair, order.client_order_id))
                else:
                    self._schedule_account_refresh()

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode == PositionMode.ONEWAY:
            return True, ""
        return False, "Kalshi only supports one-way positions."

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Kalshi has no leverage setting: its leverage follows from each market's margin rates. The leverage set here only
        sizes the margin Hummingbot reserves, so it is accepted up to Kalshi's for small positions on either side (the
        budget checker also caps it per order, see KalshiPerpetualBudgetChecker).
        """
        if trading_pair not in self._leverage_estimates:
            await self._update_trading_rules()  # set before the markets were loaded
        limits = [self.max_leverage(trading_pair, trade_type) for trade_type in (TradeType.BUY, TradeType.SELL)]
        if None in limits:
            message = f"Kalshi publishes no margin rate for {trading_pair} right now, so its leverage is unknown."
        elif leverage > int(min(limits)):
            message = (f"Kalshi allows at most {int(min(limits))}x on {trading_pair} (1 / its initial margin rate); "
                       f"requested {leverage}x. Lower the leverage in the configuration.")
        else:
            return True, ""
        # The base class only logs the failure at NETWORK level, below INFO
        self.logger().error(f"Leverage {leverage} not set for {trading_pair}: {message}")
        return False, message

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        today = datetime.fromtimestamp(self._time_synchronizer.time(), tz=timezone.utc).date()
        response = await self._api_get(
            path_url=CONSTANTS.FUNDING_HISTORY_PATH_URL,
            params={
                "ticker": symbol,
                "start_date": (today - timedelta(days=1)).isoformat(),
                "end_date": today.isoformat(),
            },
            is_auth_required=True)
        payments = response.get("funding_history") or []
        if not payments:
            return 0, Decimal("-1"), Decimal("-1")
        last_payment = max(payments, key=lambda payment: self._parse_timestamp(payment["funding_time"]))
        amount = Decimal(last_payment["funding_amount"])  # positive = received, negative = paid
        if amount == 0:
            return 0, Decimal("-1"), Decimal("-1")
        return (self._parse_timestamp(last_payment["funding_time"]),
                Decimal(str(last_payment["funding_rate"])),
                amount)

    def _to_exchange_count(self, trading_pair: str, amount: Decimal) -> str:
        return f"{(amount / self._contract_sizes[trading_pair]).quantize(Decimal('0.01')):f}"

    def _to_exchange_price(self, trading_pair: str, price: Decimal) -> str:
        contract_price = price * self._contract_sizes[trading_pair]
        return f"{contract_price.quantize(self._tick_sizes[trading_pair]):f}"

    def _from_exchange_count(self, trading_pair: str, count: str) -> Decimal:
        return Decimal(count) * self._contract_sizes[trading_pair]

    def _from_exchange_price(self, trading_pair: str, price: str) -> Decimal:
        return Decimal(price) / self._contract_sizes[trading_pair]

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[float]:
        return datetime.fromisoformat(value).timestamp() if value else None
