"""Quote manager for binary options market-making.

Computes two-sided quotes with signal-aware skew and emits
place/update/cancel actions without any connector dependency.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .config import QuoteConfig, RuntimeBridge


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class QuoteState(enum.Enum):
    IDLE = "IDLE"
    SYMMETRIC = "SYMMETRIC"
    SKEWED = "SKEWED"
    ONE_SIDED = "ONE_SIDED"
    FILLED = "FILLED"
    CONVERGED = "CONVERGED"


@dataclass
class QuoteAction:
    action: str  # place | cancel | update | close_order
    coin: str
    side: str  # YES | NO
    price: float = 0.0
    size: float = 0.0
    order_id: Optional[str] = None


@dataclass
class QuoteActions:
    actions: List[QuoteAction] = field(default_factory=list)


# ---------------------------------------------------------------------------
# QuoteManager
# ---------------------------------------------------------------------------

class QuoteManager:
    """Stateful per-coin quoting engine."""

    def __init__(self, config: QuoteConfig, runtime_bridge: RuntimeBridge):
        self._cfg = config
        self._rb = runtime_bridge
        # Per-coin state
        self._states: Dict[str, QuoteState] = {}
        self._fill_prices: Dict[str, Dict[str, Tuple[float, float]]] = {}  # coin -> {side: (price, size)}
        self._current_orders: Dict[str, Dict[str, Dict[str, Any]]] = {}  # coin -> {side: {price, size, order_id}}
        self._capital_used: Dict[str, float] = {}  # coin -> capital committed

    # -- public helpers --

    def state(self, coin: str) -> QuoteState:
        return self._states.get(coin, QuoteState.IDLE)

    def set_orders(self, coin: str, orders: Dict[str, Dict[str, Any]]) -> None:
        """Inject current open orders for a coin so tick() can diff."""
        self._current_orders[coin] = orders

    def set_order_id(self, coin: str, side: str, order_id: str) -> None:
        """Feed back executor id so _sync_side knows an order exists."""
        orders = self._current_orders.setdefault(coin, {})
        if side in orders:
            orders[side]["order_id"] = order_id

    def clear_order(self, coin: str, side: str) -> None:
        """Remove tracked order for a side."""
        orders = self._current_orders.get(coin, {})
        orders.pop(side, None)

    # -- tick --

    def tick(
        self,
        coins: List[str],
        signals: Dict[str, dict],
        orderbook_mids: Dict[str, float],
        reward_spreads: Dict[str, float],
        hours_left: Dict[str, float],
    ) -> QuoteActions:
        result = QuoteActions()
        total_capital = sum(self._capital_used.get(c, 0.0) for c in coins)

        for coin in coins:
            actions = self._tick_coin(
                coin, signals.get(coin, {}), orderbook_mids.get(coin, 0.5),
                reward_spreads.get(coin, 0.0), hours_left.get(coin, 0.0),
                total_capital,
            )
            result.actions.extend(actions)

        return result

    def _tick_coin(
        self, coin: str, sig: dict, mid: float,
        reward_spread: float, h_left: float, total_capital: float,
    ) -> List[QuoteAction]:
        cfg = self._cfg
        state = self._states.get(coin, QuoteState.IDLE)

        # --- FILLED / CONVERGED management ---
        if state in (QuoteState.FILLED, QuoteState.CONVERGED):
            return self._manage_filled(coin)

        # --- Market filter ---
        if mid < cfg.odds_min or mid > cfg.odds_max:
            return self._cancel_all(coin)
        if h_left < cfg.min_hours_for_quoting:
            return self._cancel_all(coin)
        coin_cap = self._capital_used.get(coin, 0.0)
        if coin_cap >= cfg.max_capital_per_market:
            return self._cancel_all(coin)
        if total_capital >= cfg.max_total_capital:
            return self._cancel_all(coin)

        # --- Z-ratio ---
        spot_z = abs(sig.get("z_score", 0.0))
        btc_z = abs(sig.get("btc_z_score", 0.0))
        combined_z = sig.get("combined_z", 0.0)

        spot_thresh = self._rb.get_coin_param(coin, "edge_z_threshold", 1.5)
        btc_thresh = self._rb.get_coin_param(coin, "btc_z_threshold", 0.5)
        combo_thresh = self._rb.get_coin_param(coin, "combined_z_threshold", 0.7)

        spot_ratio = spot_z / spot_thresh if spot_thresh > 0 else 0.0
        btc_ratio = btc_z / btc_thresh if btc_thresh > 0 else 0.0
        combo_ratio = abs(combined_z) / combo_thresh if combo_thresh > 0 else 0.0

        z_ratio = max(spot_ratio, btc_ratio, combo_ratio)
        z_ratio = max(0.0, min(1.0, z_ratio))

        combo_direction = combined_z / combo_thresh if combo_thresh > 0 else 0.0
        combo_direction = max(-1.0, min(1.0, combo_direction))

        # --- Distances ---
        inner = cfg.inner_fraction * reward_spread
        outer = cfg.outer_fraction * reward_spread
        base_dist = inner + (outer - inner) * z_ratio
        skew = combo_direction * cfg.skew_sensitivity * reward_spread
        yes_dist = max(0.0, min(reward_spread, base_dist - skew))
        no_dist = max(0.0, min(reward_spread, base_dist + skew))

        # --- State transitions ---
        if z_ratio >= 1.0:
            new_state = QuoteState.ONE_SIDED
        elif z_ratio > 0.5:
            new_state = QuoteState.SKEWED
        else:
            new_state = QuoteState.SYMMETRIC
        self._states[coin] = new_state

        # --- Compute desired prices ---
        available = min(
            cfg.base_size,
            cfg.max_capital_per_market - coin_cap,
            cfg.max_total_capital - total_capital,
        )
        available = max(0.0, available)
        size = available

        actions: List[QuoteAction] = []

        if new_state == QuoteState.ONE_SIDED:
            favored = "YES" if combined_z > 0 else "NO"
            opposing = "NO" if favored == "YES" else "YES"
            # Cancel opposing side
            actions.extend(self._cancel_side(coin, opposing))
            # Place/update favored at inner wall
            fav_dist = inner
            fav_price = (mid - fav_dist) if favored == "YES" else (mid + fav_dist)
            actions.extend(self._sync_side(coin, favored, fav_price, size))
        else:
            # Both sides
            yes_price_desired = mid - yes_dist
            no_price_desired = mid + no_dist
            actions.extend(self._sync_side(coin, "YES", yes_price_desired, size))
            actions.extend(self._sync_side(coin, "NO", no_price_desired, size))

        return actions

    # -- fill handling --

    def on_fill(self, coin: str, side: str, price: float, size: float) -> QuoteActions:
        if coin not in self._fill_prices:
            self._fill_prices[coin] = {}
        self._fill_prices[coin][side] = (price, size)
        self._capital_used[coin] = self._capital_used.get(coin, 0.0) + (price * size)

        # Check convergence (both sides filled)
        if len(self._fill_prices.get(coin, {})) >= 2:
            self._states[coin] = QuoteState.CONVERGED
        else:
            self._states[coin] = QuoteState.FILLED

        # Cancel remaining quotes
        result = QuoteActions()
        opp = "NO" if side == "YES" else "YES"
        result.actions.extend(self._cancel_side(coin, opp))
        # Also cancel same side
        result.actions.extend(self._cancel_side(coin, side))

        # Emit close order
        tp_dist = self._rb.get_coin_param(coin, "tp_distance", 0.05)
        if side == "YES":
            close_price = price + tp_dist
        else:
            close_price = price - tp_dist
        close_price = max(0.0, min(1.0, close_price))

        result.actions.append(QuoteAction(
            action="close_order", coin=coin, side=side,
            price=close_price, size=size,
        ))
        return result

    def on_close_fill(self, coin: str) -> None:
        self._fill_prices.pop(coin, None)
        self._capital_used.pop(coin, None)
        self._states[coin] = QuoteState.IDLE
        self._current_orders.pop(coin, None)

    # -- internal helpers --

    def _manage_filled(self, coin: str) -> List[QuoteAction]:
        """In FILLED/CONVERGED: no new quotes, just maintain close orders."""
        return []

    def _cancel_all(self, coin: str) -> List[QuoteAction]:
        actions: List[QuoteAction] = []
        orders = self._current_orders.get(coin, {})
        for side, info in orders.items():
            if info.get("order_id"):
                actions.append(QuoteAction(
                    action="cancel", coin=coin, side=side,
                    order_id=info["order_id"],
                ))
        self._current_orders.pop(coin, None)
        if self._states.get(coin) not in (QuoteState.FILLED, QuoteState.CONVERGED):
            self._states[coin] = QuoteState.IDLE
        return actions

    def _cancel_side(self, coin: str, side: str) -> List[QuoteAction]:
        orders = self._current_orders.get(coin, {})
        info = orders.get(side)
        if info and info.get("order_id"):
            orders.pop(side, None)
            return [QuoteAction(action="cancel", coin=coin, side=side, order_id=info["order_id"])]
        return []

    def _sync_side(self, coin: str, side: str, price: float, size: float) -> List[QuoteAction]:
        """Compare desired price with current order; emit place/update/nothing."""
        orders = self._current_orders.setdefault(coin, {})
        existing = orders.get(side)

        if existing and existing.get("order_id"):
            # Check reprice threshold
            if abs(existing["price"] - price) < self._cfg.reprice_threshold:
                return []
            # Update
            orders[side] = {"price": price, "size": size, "order_id": existing["order_id"]}
            return [QuoteAction(
                action="update", coin=coin, side=side,
                price=price, size=size, order_id=existing["order_id"],
            )]
        else:
            # Place new
            orders[side] = {"price": price, "size": size, "order_id": None}
            return [QuoteAction(
                action="place", coin=coin, side=side, price=price, size=size,
            )]
