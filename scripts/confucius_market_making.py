"""
Confucius Market Making Strategy

A market making strategy that dynamically adjusts bid/ask spreads based on
the Chinese Lunar Calendar's WuXing (Five Elements) system.

The strategy interprets daily elemental energy to modulate risk:
- Fire (火) / Water (水): Volatile days → Widen spreads for protection
- Metal (金) / Earth (土): Stable days → Tighten spreads for aggressive scalping
- Wood (木): Growth days → Skew spreads to accumulate inventory

"Don't fight the stars, trade with them."

Dependencies:
    pip install lunar_python
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

# Attempt to import lunar_python; gracefully handle if not installed
try:
    from lunar_python import Lunar, Solar
    LUNAR_AVAILABLE = True
except ImportError:
    LUNAR_AVAILABLE = False


class ConfuciusMarketMaking(ScriptStrategyBase):
    """
    WuXing (Five Elements) Dynamic Spread Market Making Strategy.

    Quantifies ancient wisdom into volatility parameters by adjusting
    market making risk based on elemental cycles derived from the
    Chinese Lunar Calendar.
    """

    # ==========================================================================
    # Configuration Parameters
    # ==========================================================================

    # Exchange and trading pair configuration
    exchange: str = "binance_paper_trade"
    trading_pair: str = "ETH-USDT"

    # Order configuration
    order_amount: Decimal = Decimal("0.01")
    order_refresh_time: int = 15  # seconds

    # Spread configuration by element (as decimal, e.g., 0.008 = 0.8%)
    # Fire/Water: Volatile - wide spreads for protection
    spread_volatile: Decimal = Decimal("0.008")  # 0.8%

    # Metal/Earth: Stable - tight spreads for scalping
    spread_stable: Decimal = Decimal("0.002")  # 0.2%

    # Wood: Growth - asymmetric spreads for accumulation
    spread_wood_bid: Decimal = Decimal("0.002")  # 0.2% (closer to market)
    spread_wood_ask: Decimal = Decimal("0.008")  # 0.8% (further from market)

    # Price source for reference price
    price_source: PriceType = PriceType.MidPrice

    # Status logging interval (seconds)
    status_log_interval: int = 60

    # ==========================================================================
    # WuXing (Five Elements) Mapping
    # ==========================================================================

    # Heavenly Stems (天干) to Five Elements (五行) mapping
    # The 10 Heavenly Stems cycle through the 5 elements, each appearing twice
    STEM_TO_ELEMENT: Dict[str, str] = {
        "甲": "Wood",   # Jia - Yang Wood
        "乙": "Wood",   # Yi - Yin Wood
        "丙": "Fire",   # Bing - Yang Fire
        "丁": "Fire",   # Ding - Yin Fire
        "戊": "Earth",  # Wu - Yang Earth
        "己": "Earth",  # Ji - Yin Earth
        "庚": "Metal",  # Geng - Yang Metal
        "辛": "Metal",  # Xin - Yin Metal
        "壬": "Water",  # Ren - Yang Water
        "癸": "Water",  # Gui - Yin Water
    }

    # Element descriptions for logging
    ELEMENT_DESCRIPTIONS: Dict[str, str] = {
        "Wood": "Growth/Accumulation - Skewing spreads to accumulate inventory",
        "Fire": "Volatility High - Widening spreads for protection",
        "Earth": "Stability - Tightening spreads for aggressive scalping",
        "Metal": "Stability - Tightening spreads for aggressive scalping",
        "Water": "Fluidity High - Widening spreads for protection",
    }

    # Chinese characters for elements
    ELEMENT_CHINESE: Dict[str, str] = {
        "Wood": "木",
        "Fire": "火",
        "Earth": "土",
        "Metal": "金",
        "Water": "水",
    }

    # ==========================================================================
    # Instance Variables
    # ==========================================================================

    markets = {exchange: {trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.create_timestamp: int = 0
        self.last_status_timestamp: int = 0
        self._current_element: str = "Earth"  # Default fallback
        self._current_bid_spread: Decimal = self.spread_stable
        self._current_ask_spread: Decimal = self.spread_stable
        self._day_stem: str = ""

        # Validate lunar_python availability
        if not LUNAR_AVAILABLE:
            self.logger().warning(
                "[CONFUCIUS] lunar_python not installed. Install with: pip install lunar_python. "
                "Using default Earth element (stable spreads)."
            )

    # ==========================================================================
    # Core Strategy Logic
    # ==========================================================================

    def on_tick(self):
        """
        Main strategy tick handler.

        On each tick:
        1. Update the current day's element and spreads
        2. Log status periodically
        3. Refresh orders based on current spreads
        """
        # Update element and spreads based on lunar calendar
        self._update_wuxing_spreads()

        # Log status periodically
        if self.last_status_timestamp + self.status_log_interval <= self.current_timestamp:
            self._log_wuxing_status()
            self.last_status_timestamp = self.current_timestamp

        # Refresh orders on schedule
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def _get_day_element(self) -> Tuple[str, str]:
        """
        Get the current day's Five Element (WuXing) based on the Lunar Calendar.

        Returns:
            Tuple of (element_name, day_stem)
        """
        if not LUNAR_AVAILABLE:
            return "Earth", "戊"  # Default fallback

        try:
            # Get current date and convert to lunar
            now = datetime.now()
            solar = Solar.fromYmd(now.year, now.month, now.day)
            lunar = solar.getLunar()

            # Get the Day Heavenly Stem (日干)
            day_stem = lunar.getDayGan()

            # Map stem to element
            element = self.STEM_TO_ELEMENT.get(day_stem, "Earth")

            return element, day_stem

        except Exception as e:
            self.logger().warning(f"[CONFUCIUS] Error getting lunar date: {e}. Using default Earth element.")
            return "Earth", "戊"

    def _update_wuxing_spreads(self) -> None:
        """
        Update bid/ask spreads based on the current day's WuXing element.
        """
        element, day_stem = self._get_day_element()
        self._current_element = element
        self._day_stem = day_stem

        if element in ("Fire", "Water"):
            # Volatile/Fluid days: Widen spreads for protection
            self._current_bid_spread = self.spread_volatile
            self._current_ask_spread = self.spread_volatile

        elif element in ("Metal", "Earth"):
            # Stable/Solid days: Tighten spreads for aggressive scalping
            self._current_bid_spread = self.spread_stable
            self._current_ask_spread = self.spread_stable

        elif element == "Wood":
            # Growth days: Skew spreads to accumulate inventory
            # Bid closer (easier to buy), Ask further (harder to sell)
            self._current_bid_spread = self.spread_wood_bid
            self._current_ask_spread = self.spread_wood_ask

    def _log_wuxing_status(self) -> None:
        """
        Log the current WuXing status to the Hummingbot console.
        """
        element_cn = self.ELEMENT_CHINESE.get(self._current_element, "")
        description = self.ELEMENT_DESCRIPTIONS.get(self._current_element, "")

        bid_pct = float(self._current_bid_spread) * 100
        ask_pct = float(self._current_ask_spread) * 100

        msg = (
            f"[CONFUCIUS] Today is a {self._current_element} ({element_cn}) day "
            f"({self._day_stem}). {description}. "
            f"Spreads: Bid={bid_pct:.2f}%, Ask={ask_pct:.2f}%"
        )

        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    # ==========================================================================
    # Order Management
    # ==========================================================================

    def create_proposal(self) -> List[OrderCandidate]:
        """
        Create buy and sell order proposals based on current WuXing spreads.
        """
        ref_price = self.connectors[self.exchange].get_price_by_type(
            self.trading_pair, self.price_source
        )

        buy_price = ref_price * (Decimal("1") - self._current_bid_spread)
        sell_price = ref_price * (Decimal("1") + self._current_ask_spread)

        buy_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=self.order_amount,
            price=buy_price,
        )

        sell_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=self.order_amount,
            price=sell_price,
        )

        return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """
        Adjust order proposals based on available budget.
        """
        return self.connectors[self.exchange].budget_checker.adjust_candidates(
            proposal, all_or_none=True
        )

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        """
        Place orders from the proposal list.
        """
        for order in proposal:
            if order.amount > Decimal("0"):
                self.place_order(connector_name=self.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate) -> None:
        """
        Place a single order.
        """
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def cancel_all_orders(self) -> None:
        """
        Cancel all active orders.
        """
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    # ==========================================================================
    # Event Handlers
    # ==========================================================================

    def did_fill_order(self, event: OrderFilledEvent) -> None:
        """
        Handle order fill events.
        """
        element_cn = self.ELEMENT_CHINESE.get(self._current_element, "")
        msg = (
            f"[CONFUCIUS] {event.trade_type.name} {round(event.amount, 4)} "
            f"{event.trading_pair} @ {round(event.price, 2)} "
            f"(Element: {self._current_element} {element_cn})"
        )
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    # ==========================================================================
    # Status Display
    # ==========================================================================

    def format_status(self) -> str:
        """
        Format the strategy status for display in the Hummingbot console.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []

        # Header
        lines.append("")
        lines.append("  ╔══════════════════════════════════════════════════════════════╗")
        lines.append("  ║           CONFUCIUS MARKET MAKING - WuXing Strategy          ║")
        lines.append("  ║          \"Don't fight the stars, trade with them.\"           ║")
        lines.append("  ╚══════════════════════════════════════════════════════════════╝")
        lines.append("")

        # Current Element Status
        element_cn = self.ELEMENT_CHINESE.get(self._current_element, "")
        description = self.ELEMENT_DESCRIPTIONS.get(self._current_element, "")

        lines.append(f"  Today's Element: {self._current_element} ({element_cn}) - Stem: {self._day_stem}")
        lines.append(f"  Interpretation: {description}")
        lines.append("")

        # Spread Status
        bid_pct = float(self._current_bid_spread) * 100
        ask_pct = float(self._current_ask_spread) * 100
        lines.append(f"  Current Spreads: Bid={bid_pct:.2f}% | Ask={ask_pct:.2f}%")
        lines.append("")

        # Balances
        balance_df = self.get_balance_df()
        lines.extend(["  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        lines.append("")

        # Active Orders
        try:
            df = self.active_orders_df()
            lines.extend(["  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.append("  No active maker orders.")

        lines.append("")

        return "\n".join(lines)
