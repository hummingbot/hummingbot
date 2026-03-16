"""Position tracking with pre-entry gates, cooldowns, and circuit breaker."""

import logging
import time as _time

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks open positions, enforces pre-entry gates, manages cooldowns and circuit breaker."""

    def __init__(self, config, runtime_bridge):
        self._config = config
        self._rb = runtime_bridge
        self._open_positions: dict = {}   # {executor_id: {coin, direction, size, open_ts}}
        self._coin_last_exit_ts: dict = {}  # {coin: timestamp}
        self._coin_loss_streaks: dict = {}  # {coin: consecutive_loss_count}
        self._recent_losses: list = []      # [(timestamp, coin)]
        self._coin_trade_count: dict = {}   # {coin: total_trades}

    # -- Properties ----------------------------------------------------------

    @property
    def total_exposure(self) -> float:
        return sum(p["size"] for p in self._open_positions.values())

    @property
    def open_count(self) -> int:
        return len(self._open_positions)

    def positions_for_coin(self, coin: str) -> int:
        return sum(1 for p in self._open_positions.values() if p["coin"] == coin)

    # -- Pre-entry gates -----------------------------------------------------

    def can_open(self, coin: str, direction: str, size: float, now_ts: float = None,
                 yes_price: float = None) -> tuple:
        """Returns (allowed: bool, reason: str). All gates must pass."""
        if now_ts is None:
            now_ts = _time.time()
        routing = self._config.routing

        # 1. Max total positions
        if self.open_count >= routing.max_total_positions:
            return False, f"max_total_positions ({routing.max_total_positions}) reached"

        # 2. Max positions per coin
        if self.positions_for_coin(coin) >= routing.max_positions_per_coin:
            return False, f"max_positions_per_coin ({routing.max_positions_per_coin}) for {coin}"

        # 3. Per-coin cooldown
        cooldown_secs = float(self._rb.get_coin_param(coin, "cooldown", 10.0))
        last_exit = self._coin_last_exit_ts.get(coin)
        if last_exit is not None and (now_ts - last_exit) < cooldown_secs:
            remaining = cooldown_secs - (now_ts - last_exit)
            return False, f"cooldown for {coin} ({remaining:.1f}s remaining)"

        # 4. Streak pause
        streak_threshold = int(self._rb.get_coin_param(coin, "streak_threshold", 5))
        streak_pause_secs = float(self._rb.get_coin_param(coin, "streak_pause_secs", 300))
        streak = self._coin_loss_streaks.get(coin, 0)
        if streak >= streak_threshold:
            # Check if pause has elapsed since last exit
            if last_exit is not None and (now_ts - last_exit) < streak_pause_secs:
                return False, f"streak pause for {coin} ({streak} consecutive losses)"
            # If pause elapsed, allow (streak resets on win)

        # 5. Circuit breaker
        cb_max_losses = int(self._rb.get_coin_param(coin, "cb_max_losses", 10))
        cb_window_secs = float(self._rb.get_coin_param(coin, "cb_window_secs", 3600))
        cutoff = now_ts - cb_window_secs
        recent_count = sum(1 for ts, _ in self._recent_losses if ts >= cutoff)
        if recent_count >= cb_max_losses:
            return False, f"circuit breaker ({recent_count} losses in {cb_window_secs}s window)"

        # 6. Min position size
        min_size = float(self._rb.get_coin_param(coin, "min_position_size", 1.0))
        if size < min_size:
            return False, f"size {size} below min_position_size ({min_size})"

        # 7. YES price range
        if yes_price is not None:
            min_price = float(self._rb.get_coin_param(coin, "min_edge_entry_price", 0.15))
            max_price = float(self._rb.get_coin_param(coin, "max_edge_entry_price", 0.99))
            if yes_price < min_price or yes_price > max_price:
                return False, f"yes_price {yes_price} outside [{min_price}, {max_price}]"

        return True, ""

    # -- State mutations ------------------------------------------------------

    def record_open(self, coin: str, executor_id: str, direction: str,
                    size: float, now_ts: float = None):
        if now_ts is None:
            now_ts = _time.time()
        self._open_positions[executor_id] = {
            "coin": coin,
            "direction": direction,
            "size": size,
            "open_ts": now_ts,
        }
        self._coin_trade_count[coin] = self._coin_trade_count.get(coin, 0) + 1

    def record_close(self, coin: str, executor_id: str, pnl: float,
                     now_ts: float = None):
        if now_ts is None:
            now_ts = _time.time()
        self._open_positions.pop(executor_id, None)
        self._coin_last_exit_ts[coin] = now_ts

        cb_window_secs = float(self._rb.get_coin_param(coin, "cb_window_secs", 3600))

        if pnl < 0:
            self._coin_loss_streaks[coin] = self._coin_loss_streaks.get(coin, 0) + 1
            self._recent_losses.append((now_ts, coin))
        else:
            self._coin_loss_streaks[coin] = 0

        # Prune old losses
        cutoff = now_ts - cb_window_secs
        self._recent_losses = [(ts, c) for ts, c in self._recent_losses if ts >= cutoff]
