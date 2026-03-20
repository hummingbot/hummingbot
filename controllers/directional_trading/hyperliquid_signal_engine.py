"""Signal engine for Hyperliquid directional stat-arb.

Tracks BTC-ALT divergence using a three-layer EMA system (baseline / last_hour / current).
Classifies price events as Type 1 (BTC moved, ALT didn't), Type 2 (both moved),
or Type 3 (ALT moved independently). Produces z-scores for entry signals.

Stripped version of the binary_options signal engine — no Black-Scholes, no strikes,
no yes_price. Pure spot-vs-spot divergence tracking.
"""
from __future__ import annotations

import copy
import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LN2 = math.log(2)


def halflife_to_alpha(halflife_secs: float, interval_secs: float) -> float:
    if halflife_secs <= 0 or interval_secs <= 0:
        return 0.01
    alpha = 1.0 - math.exp(-_LN2 * interval_secs / halflife_secs)
    return max(0.0001, min(0.5, alpha))


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, Any] = {
    "min_btc_delta": 10.0,
    "min_coin_delta": 0.005,
    "poll_interval_ms": 1000,
    "baseline_halflife_secs": 35,
    "current_halflife_secs": 12,
    "ema_weights": [0.5, 0.3, 0.2],
    "min_events_current_hour": 3,
    "confidence_tolerance": 0.25,
    "lag_z_min_var_obs": 10,
    "btc_z_threshold": 1.75,
    "btc_score_follow_rate_floor": 0.3,
    "edge_z_threshold": 1.5,
    "min_events_for_score": 3,
    "dyn_thresh_min_samples": 10,
    "dyn_thresh_floor_pct": 0.3,
    "max_history_ratios": 100,
    "max_history_stats": 50,
}


def _cfg(config: dict, key: str):
    return config.get(key, _DEFAULTS.get(key))


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class TypeStats:
    count: int = 0
    magnitudes: list = field(default_factory=list)
    correction_count: int = 0
    unresolved_count: int = 0
    correction_times: list = field(default_factory=list)

    @property
    def correction_rate(self) -> float:
        total = self.correction_count + self.unresolved_count
        return self.correction_count / total if total > 0 else 0.0


@dataclass
class EMALayer:
    lag_rate: float = 0.0
    follow_rate: float = 0.0
    avg_lag_secs: float = 0.0
    magnitude: float = 0.0
    up_follow_rate: float = 0.0
    down_follow_rate: float = 0.0
    inverse_rate: float = 0.0
    lag_rate_var: float = 0.0
    inverse_rate_var: float = 0.0
    btc_move_seen: int = 0
    t1_resolved_seen: int = 0
    beta_sum: float = 0.0
    beta_count: int = 0


@dataclass
class OpenSignal:
    event_type: int
    event_id: int
    timestamp: float
    coin_delta: float
    btc_delta: float


@dataclass
class CoinProfile:
    type1: TypeStats = field(default_factory=TypeStats)
    type2: TypeStats = field(default_factory=TypeStats)
    type3: TypeStats = field(default_factory=TypeStats)

    ratios: list = field(default_factory=list)
    open_signals: list = field(default_factory=list)

    baseline: EMALayer = field(default_factory=EMALayer)
    last_hour: EMALayer = field(default_factory=EMALayer)
    current: EMALayer = field(default_factory=EMALayer)
    hour_started: int = -1

    # Price tracking for log returns
    prev_price: float = 0.0

    @property
    def total_events(self) -> int:
        return self.type1.count + self.type2.count + self.type3.count

    @property
    def baseline_beta(self) -> Optional[float]:
        if self.baseline.beta_count >= 5:
            return self.baseline.beta_sum / self.baseline.beta_count
        return None

    @property
    def recent_beta(self) -> Optional[float]:
        cnt = self.current.beta_count + self.last_hour.beta_count
        if cnt >= 3:
            return (self.current.beta_sum + self.last_hour.beta_sum) / cnt
        return None


# ---------------------------------------------------------------------------
# Dynamic Thresholds
# ---------------------------------------------------------------------------

class DynamicThresholds:
    def __init__(self, static_btc_delta: float, static_coin_delta: float,
                 window: int = 60, multiplier: float = 1.5,
                 min_samples: int = 10, floor_pct: float = 0.3):
        self._static_btc = static_btc_delta
        self._static_coin = static_coin_delta
        self._window = window
        self._multiplier = multiplier
        self._min_samples = min_samples
        self._floor_pct = floor_pct
        self._btc_deltas: List[float] = []
        self._coin_deltas: Dict[str, List[float]] = {}
        self.btc_threshold: float = static_btc_delta
        self.coin_thresholds: Dict[str, float] = {}

    def feed(self, btc_delta: float, coin_deltas: Dict[str, float]) -> None:
        self._btc_deltas.append(abs(btc_delta))
        if len(self._btc_deltas) > self._window:
            self._btc_deltas = self._btc_deltas[-self._window:]
        for coin, delta in coin_deltas.items():
            lst = self._coin_deltas.setdefault(coin, [])
            lst.append(abs(delta))
            if len(lst) > self._window:
                self._coin_deltas[coin] = lst[-self._window:]
        self._recompute()

    def _recompute(self) -> None:
        if len(self._btc_deltas) >= self._min_samples:
            std = statistics.stdev(self._btc_deltas) if len(self._btc_deltas) > 1 else 0.0
            self.btc_threshold = max(std * self._multiplier, self._static_btc * self._floor_pct)
        for coin, lst in self._coin_deltas.items():
            if len(lst) >= self._min_samples:
                std = statistics.stdev(lst) if len(lst) > 1 else 0.0
                self.coin_thresholds[coin] = max(
                    std * self._multiplier, self._static_coin * self._floor_pct)

    def get_coin_threshold(self, coin: str) -> float:
        return self.coin_thresholds.get(coin, self._static_coin)


# ---------------------------------------------------------------------------
# EMA math
# ---------------------------------------------------------------------------

def _ema(old: float, new: float, alpha: float, n: int) -> float:
    if n == 0:
        return new
    return alpha * new + (1.0 - alpha) * old


def _ema_var(old_var: float, diff: float, alpha: float) -> float:
    return (1.0 - alpha) * (old_var + alpha * diff * diff)


def _feed_lag(prof: CoinProfile, value: float, b_alpha: float, c_alpha: float) -> None:
    for layer, alpha in ((prof.baseline, b_alpha), (prof.current, c_alpha)):
        diff = value - layer.lag_rate
        layer.lag_rate_var = _ema_var(layer.lag_rate_var, diff, alpha)
        layer.lag_rate = _ema(layer.lag_rate, value, alpha, layer.btc_move_seen)
        layer.btc_move_seen += 1


def _feed_follow(prof: CoinProfile, value: float, b_alpha: float, c_alpha: float) -> None:
    for layer, alpha in ((prof.baseline, b_alpha), (prof.current, c_alpha)):
        layer.follow_rate = _ema(layer.follow_rate, value, alpha, layer.t1_resolved_seen)
        layer.t1_resolved_seen += 1


def _feed_lag_secs(prof: CoinProfile, secs: float, b_alpha: float, c_alpha: float) -> None:
    for layer, alpha in ((prof.baseline, b_alpha), (prof.current, c_alpha)):
        n = layer.t1_resolved_seen
        layer.avg_lag_secs = _ema(layer.avg_lag_secs, secs, alpha, max(0, n - 1))


def _feed_directional(prof: CoinProfile, btc_delta: float, value: float,
                       b_alpha: float, c_alpha: float) -> None:
    for layer, alpha in ((prof.baseline, b_alpha), (prof.current, c_alpha)):
        n = layer.t1_resolved_seen
        if btc_delta > 0:
            layer.up_follow_rate = _ema(layer.up_follow_rate, value, alpha, max(0, n - 1))
        elif btc_delta < 0:
            layer.down_follow_rate = _ema(layer.down_follow_rate, value, alpha, max(0, n - 1))


def _feed_inverse(prof: CoinProfile, value: float, b_alpha: float, c_alpha: float) -> None:
    for layer, alpha in ((prof.baseline, b_alpha), (prof.current, c_alpha)):
        diff = value - layer.inverse_rate
        layer.inverse_rate_var = _ema_var(layer.inverse_rate_var, diff, alpha)
        layer.inverse_rate = _ema(layer.inverse_rate, value, alpha, layer.t1_resolved_seen)


def _feed_magnitude(prof: CoinProfile, ratio: float, b_alpha: float, c_alpha: float) -> None:
    for layer, alpha in ((prof.baseline, b_alpha), (prof.current, c_alpha)):
        n = layer.btc_move_seen
        layer.magnitude = _ema(layer.magnitude, ratio, alpha, max(0, n - 1))


def _feed_beta(prof: CoinProfile, btc_delta: float, coin_delta: float,
               b_alpha: float, c_alpha: float) -> None:
    if abs(btc_delta) < 0.001:
        return
    beta = coin_delta / btc_delta
    if abs(beta) > 10:
        return
    for layer in (prof.baseline, prof.current, prof.last_hour):
        layer.beta_sum += beta
        layer.beta_count += 1


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _logit(x: float) -> float:
    x = max(0.005, min(0.995, x))
    return math.log(x / (1.0 - x))


def lag_z_score(prof: CoinProfile, weights: List[float],
                min_events_curr: int, min_var_obs: int = 10) -> float:
    if prof.baseline.btc_move_seen < min_var_obs:
        return 0.0
    if prof.current.btc_move_seen >= min_events_curr:
        recent = prof.current.lag_rate
    elif prof.last_hour.btc_move_seen > 0:
        recent = prof.last_hour.lag_rate
    else:
        return 0.0
    return _logit(recent) - _logit(prof.baseline.lag_rate)


def compute_confidence(prof: CoinProfile, tolerance: float,
                       min_events_curr: int) -> str:
    layers = [prof.baseline.lag_rate]
    if prof.last_hour.btc_move_seen > 0:
        layers.append(prof.last_hour.lag_rate)
    if prof.current.btc_move_seen >= min_events_curr:
        layers.append(prof.current.lag_rate)
    if len(layers) < 2:
        return "LOW"
    spread = max(layers) - min(layers)
    return "HIGH" if spread <= tolerance else "LOW"


def _check_hour_boundary(profiles: Dict[str, CoinProfile], current_hour: int) -> None:
    for coin, prof in profiles.items():
        if prof.hour_started != current_hour:
            if prof.current.btc_move_seen > 0:
                prof.last_hour = copy.copy(prof.current)
            prof.current = EMALayer()
            prof.hour_started = current_hour


# ---------------------------------------------------------------------------
# SignalEngine
# ---------------------------------------------------------------------------

class SignalEngine:
    """Per-tick divergence tracker for perpetual trading.

    Call tick() each update cycle with current ALT and BTC prices.
    Returns dict with z_score, btc_z_score, direction, signal, etc.
    """

    def __init__(self, config: dict):
        self._config = config
        self._profiles: Dict[str, CoinProfile] = {}
        self._prev_btc: float = 0.0
        self._event_id: int = 0
        self._tick_count: int = 0

        static_btc = _cfg(config, "min_btc_delta")
        static_coin = _cfg(config, "min_coin_delta")
        self._dyn_thresh = DynamicThresholds(
            static_btc, static_coin,
            min_samples=_cfg(config, "dyn_thresh_min_samples"),
            floor_pct=_cfg(config, "dyn_thresh_floor_pct"),
        )

    def _get_interval_secs(self) -> float:
        return _cfg(self._config, "poll_interval_ms") / 1000.0

    def _get_alphas(self, interval: float) -> Tuple[float, float]:
        b_alpha = halflife_to_alpha(_cfg(self._config, "baseline_halflife_secs"), interval)
        c_alpha = halflife_to_alpha(_cfg(self._config, "current_halflife_secs"), interval)
        return b_alpha, c_alpha

    def tick(self, coin: str, spot_price: float, btc_price: float,
             now_ts: float) -> dict:
        """Run one tick of divergence tracking.

        Args:
            coin: Asset symbol (e.g. "SOL")
            spot_price: Current ALT price
            btc_price: Current BTC price
            now_ts: Timestamp in seconds (monotonic or wall clock)

        Returns:
            Dict with z_score, btc_z_score, signal (-1/0/1), direction, confidence, etc.
        """
        self._tick_count += 1
        interval = self._get_interval_secs()
        current_hour = int((now_ts / 3600)) % 24

        # Ensure profile exists
        if coin not in self._profiles:
            self._profiles[coin] = CoinProfile()
        prof = self._profiles[coin]

        # Hour boundary
        _check_hour_boundary(self._profiles, current_hour)

        # Compute price deltas
        btc_delta = btc_price - self._prev_btc if self._prev_btc > 0 else 0.0
        coin_delta = spot_price - prof.prev_price if prof.prev_price > 0 else 0.0

        # Update prev prices
        self._prev_btc = btc_price
        prof.prev_price = spot_price

        # First tick: seed and skip
        if self._tick_count <= 1:
            return self._empty_signal()

        # Feed dynamic thresholds
        self._dyn_thresh.feed(btc_delta, {coin: coin_delta})

        btc_moved = abs(btc_delta) >= self._dyn_thresh.btc_threshold
        coin_thresh = self._dyn_thresh.get_coin_threshold(coin)
        coin_moved = abs(coin_delta) >= coin_thresh

        # Classify event
        if not btc_moved and not coin_moved:
            event_type = 0
        elif btc_moved and not coin_moved:
            event_type = 1  # BTC moved, ALT lagged
        elif btc_moved and coin_moved:
            event_type = 2  # Both moved
        else:
            event_type = 3  # ALT moved independently

        # Feed EMA layers
        b_alpha, c_alpha = self._get_alphas(interval)

        if event_type > 0:
            self._event_id += 1

            if event_type == 1:
                prof.type1.count += 1
                prof.type1.magnitudes.append(abs(btc_delta))
                self._trim_list(prof.type1.magnitudes)
                _feed_lag(prof, 1.0, b_alpha, c_alpha)
                _feed_beta(prof, btc_delta, coin_delta, b_alpha, c_alpha)
                prof.open_signals.append(OpenSignal(
                    event_type=1, event_id=self._event_id,
                    timestamp=now_ts, coin_delta=coin_delta,
                    btc_delta=btc_delta))

            elif event_type == 2:
                prof.type2.count += 1
                if abs(btc_delta) > 0.001:
                    ratio = coin_delta / btc_delta
                    prof.ratios.append(ratio)
                    self._trim_list(prof.ratios, _cfg(self._config, "max_history_ratios"))
                _feed_lag(prof, 0.0, b_alpha, c_alpha)
                _feed_magnitude(prof, abs(coin_delta), b_alpha, c_alpha)
                _feed_beta(prof, btc_delta, coin_delta, b_alpha, c_alpha)

            elif event_type == 3:
                prof.type3.count += 1
                prof.type3.magnitudes.append(abs(coin_delta))
                self._trim_list(prof.type3.magnitudes)
                prof.open_signals.append(OpenSignal(
                    event_type=3, event_id=self._event_id,
                    timestamp=now_ts, coin_delta=coin_delta,
                    btc_delta=0.0))

        # Resolve pending signals
        self._resolve_signals(prof, coin, coin_delta, btc_delta, now_ts)

        # Compute z-scores
        weights = _cfg(self._config, "ema_weights")
        min_ev_curr = _cfg(self._config, "min_events_current_hour")

        z_score = lag_z_score(prof, weights, min_ev_curr,
                              _cfg(self._config, "lag_z_min_var_obs"))

        # BTC z-score: how much is BTC diverging from its baseline behavior with this ALT
        # Use the beta deviation as BTC signal
        btc_z = 0.0
        if prof.baseline_beta is not None and prof.recent_beta is not None:
            if prof.baseline.beta_count >= 20 and prof.recent_beta > 0:
                btc_z = (prof.recent_beta - prof.baseline_beta) / max(0.01, prof.baseline_beta)

        confidence = compute_confidence(prof, _cfg(self._config, "confidence_tolerance"),
                                         min_ev_curr)

        # Determine direction from z-score
        edge_threshold = _cfg(self._config, "edge_z_threshold")
        btc_threshold = _cfg(self._config, "btc_z_threshold")

        if abs(z_score) >= edge_threshold:
            # Negative z = ALT lagging BTC = expect catch-up = long
            # Positive z = ALT leading BTC = expect reversion = short
            signal = -1 if z_score > 0 else 1
            direction = "SHORT" if z_score > 0 else "LONG"
        else:
            signal = 0
            direction = None

        return {
            "signal": signal,
            "direction": direction,
            "z_score": z_score,
            "btc_z_score": btc_z,
            "confidence": confidence,
            "event_type": event_type,
            "spot_price": spot_price,
            "btc_price": btc_price,
            "beta_baseline": prof.baseline_beta,
            "beta_recent": prof.recent_beta,
            "total_events": prof.total_events,
            "type1_count": prof.type1.count,
            "type2_count": prof.type2.count,
            "type3_count": prof.type3.count,
        }

    def _resolve_signals(self, prof: CoinProfile, coin: str,
                          coin_delta: float, btc_delta: float,
                          now_ts: float) -> None:
        remaining = []
        interval = self._get_interval_secs()
        b_alpha, c_alpha = self._get_alphas(interval)
        # Timeout: 60 seconds for perps (no expiry)
        timeout = 60.0

        for sig in prof.open_signals:
            elapsed = now_ts - sig.timestamp

            if sig.event_type == 1:
                thresh = self._dyn_thresh.get_coin_threshold(coin)
                if abs(coin_delta) >= thresh:
                    same_dir = (coin_delta > 0) == (sig.btc_delta > 0)
                    if same_dir:
                        prof.type1.correction_count += 1
                        prof.type1.correction_times.append(elapsed)
                        self._trim_list(prof.type1.correction_times)
                        _feed_follow(prof, 1.0, b_alpha, c_alpha)
                        _feed_directional(prof, sig.btc_delta, 1.0, b_alpha, c_alpha)
                        _feed_inverse(prof, 0.0, b_alpha, c_alpha)
                        _feed_lag_secs(prof, elapsed, b_alpha, c_alpha)
                    else:
                        _feed_follow(prof, 0.0, b_alpha, c_alpha)
                        _feed_inverse(prof, 1.0, b_alpha, c_alpha)
                        _feed_directional(prof, sig.btc_delta, 0.0, b_alpha, c_alpha)
                    continue
                elif elapsed >= timeout:
                    prof.type1.unresolved_count += 1
                    _feed_follow(prof, 0.0, b_alpha, c_alpha)
                    _feed_inverse(prof, 0.0, b_alpha, c_alpha)
                    continue
                remaining.append(sig)

            elif sig.event_type == 3:
                thresh = self._dyn_thresh.get_coin_threshold(coin)
                if abs(coin_delta) >= thresh and (coin_delta > 0) != (sig.coin_delta > 0):
                    prof.type3.correction_count += 1
                    prof.type3.correction_times.append(elapsed)
                    self._trim_list(prof.type3.correction_times)
                    continue
                elif elapsed >= timeout:
                    prof.type3.unresolved_count += 1
                    continue
                remaining.append(sig)

        prof.open_signals = remaining

    def _trim_list(self, lst: list, max_len: int = None) -> None:
        if max_len is None:
            max_len = _cfg(self._config, "max_history_stats")
        while len(lst) > max_len:
            lst.pop(0)

    @staticmethod
    def _empty_signal() -> dict:
        return {
            "signal": 0,
            "direction": None,
            "z_score": 0.0,
            "btc_z_score": 0.0,
            "confidence": "LOW",
            "event_type": 0,
            "spot_price": 0.0,
            "btc_price": 0.0,
            "beta_baseline": None,
            "beta_recent": None,
            "total_events": 0,
            "type1_count": 0,
            "type2_count": 0,
            "type3_count": 0,
        }
