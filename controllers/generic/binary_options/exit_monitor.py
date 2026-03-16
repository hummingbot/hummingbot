"""Exit monitor for BinaryOptionsController — Phase 1.

Handles two exit conditions that PositionExecutor's TripleBarrierConfig cannot:
1. BTC spot reversal (cross-asset trigger)
2. Settlement detection (near-expiry hold-or-exit decision)

Phase 2 replaces this with BinaryOptionsExecutor which handles all exits internally.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ExitMonitor:
    """Monitors active executors for BTC reversal and settlement exits."""

    def __init__(self, config, runtime_bridge):
        self._config = config
        self._rb = runtime_bridge
        self._btc_entry_prices: dict = {}    # {executor_id: btc_spot_at_entry}
        self._executor_directions: dict = {}  # {executor_id: "YES" or "NO"}
        self._executor_coins: dict = {}       # {executor_id: coin}

    def register_entry(self, executor_id: str, coin: str, direction: str, btc_spot: float):
        """Called when a new executor is created. Records BTC spot at entry."""
        self._btc_entry_prices[executor_id] = btc_spot
        self._executor_directions[executor_id] = direction
        self._executor_coins[executor_id] = coin

    def unregister(self, executor_id: str):
        """Called when executor closes. Cleans up tracking state."""
        self._btc_entry_prices.pop(executor_id, None)
        self._executor_directions.pop(executor_id, None)
        self._executor_coins.pop(executor_id, None)

    def check_all(self, active_executors: list, btc_spot: float,
                  market_data: dict, now_ts: float) -> list:
        """Check all active executors for BTC reversal and settlement exits.

        Returns list of dicts: [{"executor_id": str, "reason": str}, ...]
        The controller converts these to actual StopExecutorAction objects.
        """
        actions = []
        for executor_info in active_executors:
            eid = executor_info.id if hasattr(executor_info, 'id') else executor_info.get('id', '')

            # Check 1: BTC reversal (higher priority)
            action = self._check_btc_reversal(eid, btc_spot)
            if action:
                actions.append(action)
                continue

            # Check 2: Settlement detection
            coin = self._executor_coins.get(eid)
            if coin and coin in market_data:
                action = self._check_settlement(eid, coin, market_data[coin], now_ts)
                if action:
                    actions.append(action)

        return actions

    def _check_btc_reversal(self, executor_id: str, btc_spot_now: float) -> Optional[dict]:
        """Cross-asset exit trigger.

        If BTC spot moved against our position by >= btc_reversal_multiplier, exit.
        - YES (bullish): BTC dropping is bad → btc_entry - btc_now >= threshold
        - NO  (bearish): BTC rising is bad  → btc_now - btc_entry >= threshold
        """
        entry_price = self._btc_entry_prices.get(executor_id)
        direction = self._executor_directions.get(executor_id)
        coin = self._executor_coins.get(executor_id)
        if entry_price is None or direction is None:
            return None

        threshold = self._rb.get_coin_param(
            coin or "", "btc_reversal_multiplier", 5.24
        )

        if direction == "YES":
            adverse_move = entry_price - btc_spot_now
        else:  # NO
            adverse_move = btc_spot_now - entry_price

        if adverse_move >= threshold:
            logger.info(
                "ExitMonitor: BTC reversal for %s (dir=%s, entry=%.2f, now=%.2f, move=%.2f >= %.2f)",
                executor_id, direction, entry_price, btc_spot_now, adverse_move, threshold,
            )
            return {"executor_id": executor_id, "reason": "btc_reversal"}

        return None

    def _check_settlement(self, executor_id: str, coin: str,
                          market: dict, now_ts: float) -> Optional[dict]:
        """Near-expiry decision: hold for settlement or exit early.

        If market expires within close_secs:
        - Winning AND probability > settlement_hold_threshold → hold (no action)
        - Losing → exit before worthless
        """
        close_secs = self._rb.get_coin_param(coin, "close_secs", 120.0)
        end_time = market.get("end_time")
        if end_time is None:
            return None

        time_to_expiry = end_time - now_ts
        if time_to_expiry > close_secs:
            return None

        # Near expiry — decide hold or exit
        direction = self._executor_directions.get(executor_id)
        yes_price = market.get("yes_price", 0.5)

        if direction == "YES":
            winning = yes_price > 0.50
        else:
            winning = yes_price < 0.50

        if winning:
            threshold = getattr(self._config.routing, "settlement_hold_threshold", 0.70)
            # Probability of our outcome winning
            prob = yes_price if direction == "YES" else (1.0 - yes_price)
            if prob >= threshold:
                return None  # Hold for $1.00 settlement

        logger.info(
            "ExitMonitor: settlement exit for %s (coin=%s, dir=%s, yes_price=%.3f, "
            "time_to_expiry=%.1fs)",
            executor_id, coin, direction, yes_price, time_to_expiry,
        )
        return {"executor_id": executor_id, "reason": "settlement_exit"}
