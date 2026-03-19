"""Signal engine for BinaryOptionsController — divergence tracking + dual-score entry.

Ports the behavioral classification (Type 1/2/3), three-layer EMA system,
dynamic thresholds, and unified dual-score entry system from the original
divergence_tracker.py into a stateless-per-tick module that returns signal
dicts instead of calling a trader directly.

Only stdlib + .fair_value + .config imports.
"""
from __future__ import annotations

import copy
import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from .config import RuntimeBridge
from .fair_value import (
    BtcImpliedProfile,
    MispricingProfile,
    compute_edge,
    compute_hourly_volatility,
    compute_model_prob,
    halflife_to_alpha,
)

_LN2 = math.log(2)

# ---------------------------------------------------------------------------
# Default config values (subset relevant to signal engine)
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, Any] = {
    "min_btc_delta": 10.0,
    "min_coin_delta": 0.005,
    "poll_interval_ms": 500,
    "baseline_halflife_secs": 35,
    "current_halflife_secs": 12,
    "mispricing_halflife_secs": 23,
    "ema_weights": [0.5, 0.3, 0.2],
    "min_events_current_hour": 3,
    "confidence_tolerance": 0.25,
    "lag_z_min_var_obs": 10,
    "btc_z_threshold": 1.75,
    "btc_score_follow_rate_floor": 0.3,
    "independent_entry_paths_enabled": True,
    "entry_path_priority": ["COMBINED", "SPOT", "BTC"],
    "edge_z_threshold": 1.5,
    "edge_min_history_secs": 50,
    "edge_min_vol_obs_secs": 100,
    "min_events_for_score": 3,
    "dyn_thresh_min_samples": 10,
    "dyn_thresh_floor_pct": 0.3,
    "type1_timeout_seconds": 0,
    "type3_timeout_seconds": 0,
    "market_duration_seconds": 3600,
    "stop_fallback_pct": 0.05,
    "beta_anomaly_threshold": 0.3,
    "inverse_beta_threshold": 0.0,
    "vol_ema_halflife_secs": 350,
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
    """Per-event-type statistics for a single coin."""
    count: int = 0
    magnitudes: list = field(default_factory=list)
    correction_count: int = 0
    unresolved_count: int = 0
    correction_times: list = field(default_factory=list)

    @property
    def correction_rate(self) -> float:
        total = self.correction_count + self.unresolved_count
        return self.correction_count / total if total > 0 else 0.0

    @property
    def avg_magnitude(self) -> float:
        return statistics.mean(self.magnitudes) if self.magnitudes else 0.0

    @property
    def avg_correction_time(self) -> float:
        return statistics.mean(self.correction_times) if self.correction_times else 0.0


@dataclass
class OpenSignal:
    """Pending Type 1 or Type 3 signal awaiting resolution."""
    event_type: int
    event_id: int
    timestamp: float       # monotonic ts at creation
    coin_delta: float
    btc_delta: float


@dataclass
class EMALayer:
    """One tier of the three-layer EMA system."""
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
class CoinProfile:
    """Full behavioral profile for a single coin."""
    type1: TypeStats = field(default_factory=TypeStats)
    type2: TypeStats = field(default_factory=TypeStats)
    type3: TypeStats = field(default_factory=TypeStats)

    ratios: list = field(default_factory=list)
    open_signals: list = field(default_factory=list)
    ticks_idle: int = 0

    baseline: EMALayer = field(default_factory=EMALayer)
    last_hour: EMALayer = field(default_factory=EMALayer)
    current: EMALayer = field(default_factory=EMALayer)
    hour_started: int = -1

    mispricing: Optional[MispricingProfile] = None
    btc_implied: Optional[BtcImpliedProfile] = None
    last_slug: str = ""  # track market slug for reset on switch

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
# DynamicThresholds
# ---------------------------------------------------------------------------

class DynamicThresholds:
    """Adaptive noise floors from rolling price data."""

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


# ---------------------------------------------------------------------------
# EMA feed functions — update baseline + current layers
# ---------------------------------------------------------------------------

def _feed_lag(prof: CoinProfile, value: float, b_alpha: float, c_alpha: float) -> None:
    """Feed lag_rate (1.0 for T1, 0.0 for T2). Updates var before rate (Welford)."""
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
        n = layer.t1_resolved_seen  # use resolved count as proxy
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
# Scoring functions
# ---------------------------------------------------------------------------

def merged_lag_rate(prof: CoinProfile, weights: List[float],
                    min_events_curr: int) -> float:
    w_base, w_last, w_curr = weights
    has_last = prof.last_hour.btc_move_seen > 0
    has_curr = prof.current.btc_move_seen >= min_events_curr

    if not has_curr and not has_last:
        return prof.baseline.lag_rate

    if not has_curr:
        total = w_base + w_last
        if total <= 0:
            return prof.baseline.lag_rate
        return (prof.baseline.lag_rate * w_base + prof.last_hour.lag_rate * w_last) / total

    if not has_last:
        total = w_base + w_curr
        if total <= 0:
            return prof.baseline.lag_rate
        return (prof.baseline.lag_rate * w_base + prof.current.lag_rate * w_curr) / total

    return (prof.baseline.lag_rate * w_base +
            prof.last_hour.lag_rate * w_last +
            prof.current.lag_rate * w_curr)


def merged_inverse_rate(prof: CoinProfile, weights: List[float],
                        min_events_curr: int) -> float:
    w_base, w_last, w_curr = weights
    has_last = prof.last_hour.btc_move_seen > 0
    has_curr = prof.current.btc_move_seen >= min_events_curr

    if not has_curr and not has_last:
        return prof.baseline.inverse_rate

    if not has_curr:
        total = w_base + w_last
        if total <= 0:
            return prof.baseline.inverse_rate
        return (prof.baseline.inverse_rate * w_base + prof.last_hour.inverse_rate * w_last) / total

    if not has_last:
        total = w_base + w_curr
        if total <= 0:
            return prof.baseline.inverse_rate
        return (prof.baseline.inverse_rate * w_base + prof.current.inverse_rate * w_curr) / total

    return (prof.baseline.inverse_rate * w_base +
            prof.last_hour.inverse_rate * w_last +
            prof.current.inverse_rate * w_curr)


def _logit(x: float) -> float:
    x = max(0.005, min(0.995, x))
    return math.log(x / (1.0 - x))


def lag_z_score(prof: CoinProfile, weights: List[float],
                min_events_curr: int, min_var_obs: int = 10) -> float:
    if prof.baseline.btc_move_seen < min_var_obs:
        return 0.0
    # Pick best recent layer
    if prof.current.btc_move_seen >= min_events_curr:
        recent = prof.current.lag_rate
    elif prof.last_hour.btc_move_seen > 0:
        recent = prof.last_hour.lag_rate
    else:
        return 0.0
    return _logit(recent) - _logit(prof.baseline.lag_rate)


def inverse_z_score(prof: CoinProfile, weights: List[float],
                    min_events_curr: int, min_var_obs: int = 10) -> float:
    if prof.baseline.t1_resolved_seen < min_var_obs:
        return 0.0
    if prof.current.btc_move_seen >= min_events_curr:
        recent = prof.current.inverse_rate
    elif prof.last_hour.btc_move_seen > 0:
        recent = prof.last_hour.inverse_rate
    else:
        return 0.0
    return _logit(recent) - _logit(prof.baseline.inverse_rate)


def beta_anomaly_signal(prof: CoinProfile, cfg: dict) -> Tuple[float, bool]:
    threshold = cfg.get("beta_anomaly_threshold", 0.3)
    bb = prof.baseline_beta
    rb = prof.recent_beta
    if bb is None or rb is None or prof.baseline.beta_count < 20 or rb <= 0:
        return 0.0, False
    score = max(0.0, 1.0 - rb / bb)
    return score, score >= threshold


def inverse_beta_signal(prof: CoinProfile, cfg: dict) -> Tuple[float, bool]:
    threshold = cfg.get("inverse_beta_threshold", 0.0)
    bb = prof.baseline_beta
    rb = prof.recent_beta
    if bb is None or rb is None or bb < 0.3:
        return 0.0, False
    return rb, rb < threshold


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


# ---------------------------------------------------------------------------
# Hour boundary
# ---------------------------------------------------------------------------

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
    """Per-tick signal pipeline: classify events, feed EMAs, score entries."""

    def __init__(self, config: dict, runtime_bridge: RuntimeBridge,
                 fair_value_module=None):
        self._config = config
        self._rb = runtime_bridge
        self._fv = fair_value_module  # unused placeholder for future DI

        self._profiles: Dict[str, CoinProfile] = {}
        self._prev_spots: Dict[str, float] = {}
        self._prev_btc: float = 0.0
        self._prev_yes: Dict[str, float] = {}
        self._event_id: int = 0

        static_btc = _cfg(config, "min_btc_delta")
        static_coin = _cfg(config, "min_coin_delta")
        self._dyn_thresh = DynamicThresholds(
            static_btc, static_coin,
            min_samples=_cfg(config, "dyn_thresh_min_samples"),
            floor_pct=_cfg(config, "dyn_thresh_floor_pct"),
        )
        self._tick_count: int = 0

    def get_profiles(self) -> Dict[str, CoinProfile]:
        return self._profiles

    def _get_interval_secs(self) -> float:
        return _cfg(self._config, "poll_interval_ms") / 1000.0

    def _get_timeout(self, event_type: int) -> float:
        key = f"type{event_type}_timeout_seconds"
        val = _cfg(self._config, key)
        if val and val > 0:
            return val
        # Auto: fallback_pct * market_duration
        dur = _cfg(self._config, "market_duration_seconds")
        pct = _cfg(self._config, "stop_fallback_pct")
        return dur * pct

    def tick(self, spots: Dict[str, float], markets: Dict[str, dict],
             btc_spot: float, now_ts: float) -> Dict[str, dict]:
        """Run the full per-tick signal pipeline.

        Args:
            spots: {coin: spot_price} from Pyth oracle
            markets: {coin: {yes_price, strike, hours_left, max_spread, ...}}
            btc_spot: current BTC spot price
            now_ts: monotonic timestamp in seconds

        Returns:
            {coin: {spot_signal, btc_signal, direction, edge, z_score, ...}}
        """
        self._tick_count += 1
        interval = self._get_interval_secs()
        current_hour = int((now_ts / 3600)) % 24

        # Ensure profiles exist
        for coin in markets:
            if coin not in self._profiles:
                self._profiles[coin] = CoinProfile()

        # Hour boundary
        _check_hour_boundary(self._profiles, current_hour)

        # --- 1. Compute spot deltas (log returns) ---
        btc_delta = btc_spot - self._prev_btc if self._prev_btc > 0 else 0.0
        coin_deltas: Dict[str, float] = {}
        for coin in markets:
            if coin in self._prev_yes:
                coin_deltas[coin] = markets[coin].get("yes_price", 0) - self._prev_yes.get(coin, 0)
            else:
                coin_deltas[coin] = 0.0

        # Update prev
        self._prev_btc = btc_spot
        for coin in markets:
            self._prev_yes[coin] = markets[coin].get("yes_price", 0)
            if coin in spots:
                self._prev_spots[coin] = spots[coin]

        # First tick: seed and skip
        if self._tick_count <= 1:
            return {coin: self._empty_signal() for coin in markets}

        # --- 2. Feed DynamicThresholds ---
        self._dyn_thresh.feed(btc_delta, coin_deltas)

        btc_moved = abs(btc_delta) >= self._dyn_thresh.btc_threshold
        any_moved = btc_moved

        # --- 3. Classify events (Type 1/2/3) ---
        coin_types: Dict[str, int] = {}
        for coin, delta in coin_deltas.items():
            thresh = self._dyn_thresh.get_coin_threshold(coin)
            coin_moved = abs(delta) >= thresh
            if not btc_moved and not coin_moved:
                coin_types[coin] = 0
                continue
            any_moved = True
            if btc_moved and not coin_moved:
                coin_types[coin] = 1
            elif btc_moved and coin_moved:
                coin_types[coin] = 2
            else:
                coin_types[coin] = 3

        # --- 4. Feed EMA layers + record events ---
        if any_moved:
            self._event_id += 1
            for coin, etype in coin_types.items():
                if etype == 0:
                    continue
                prof = self._profiles[coin]
                b_alpha, c_alpha, _ = self._rb.get_alphas(coin, interval)

                if etype == 1:
                    prof.type1.count += 1
                    prof.type1.magnitudes.append(abs(btc_delta))
                    self._trim_list(prof.type1.magnitudes)
                    _feed_lag(prof, 1.0, b_alpha, c_alpha)
                    _feed_beta(prof, btc_delta, coin_deltas[coin], b_alpha, c_alpha)
                    # Open signal for resolution
                    prof.open_signals.append(OpenSignal(
                        event_type=1, event_id=self._event_id,
                        timestamp=now_ts, coin_delta=coin_deltas[coin],
                        btc_delta=btc_delta))

                elif etype == 2:
                    prof.type2.count += 1
                    if abs(btc_delta) > 0.001:
                        ratio = coin_deltas[coin] / btc_delta
                        prof.ratios.append(ratio)
                        self._trim_list(prof.ratios, _cfg(self._config, "max_history_ratios"))
                    prof.type2.magnitudes.append(abs(coin_deltas[coin]))
                    self._trim_list(prof.type2.magnitudes)
                    _feed_lag(prof, 0.0, b_alpha, c_alpha)
                    _feed_magnitude(prof, abs(coin_deltas[coin]), b_alpha, c_alpha)
                    _feed_beta(prof, btc_delta, coin_deltas[coin], b_alpha, c_alpha)

                elif etype == 3:
                    prof.type3.count += 1
                    prof.type3.magnitudes.append(abs(coin_deltas[coin]))
                    self._trim_list(prof.type3.magnitudes)
                    prof.open_signals.append(OpenSignal(
                        event_type=3, event_id=self._event_id,
                        timestamp=now_ts, coin_delta=coin_deltas[coin],
                        btc_delta=0.0))

        # --- 5. Resolve pending signals ---
        for coin in markets:
            prof = self._profiles[coin]
            self._resolve_signals(prof, coin, coin_deltas.get(coin, 0), btc_delta, now_ts)

        # --- 6-9. Fair value + dual-score entry ---
        results: Dict[str, dict] = {}
        weights = _cfg(self._config, "ema_weights")
        min_ev_curr = _cfg(self._config, "min_events_current_hour")

        btc_log_return = None
        if "BTC" in spots and "BTC" in self._prev_spots and self._prev_spots["BTC"] > 0 and spots["BTC"] > 0:
            btc_log_return = math.log(btc_spot / self._prev_spots.get("_btc_prev_raw", btc_spot)) if self._prev_spots.get("_btc_prev_raw", 0) > 0 else 0.0
        # Store raw btc for next tick log return
        self._prev_spots["_btc_prev_raw"] = btc_spot

        for coin, mdata in markets.items():
            prof = self._profiles[coin]
            spot = spots.get(coin)
            yes_price = mdata.get("yes_price", 0.5)
            strike = mdata.get("strike", 0)
            hours_left = mdata.get("hours_left", 1.0)

            sig = self._empty_signal()
            sig["event_type"] = coin_types.get(coin, 0)

            # Lazy-init fair value profiles
            if prof.mispricing is None:
                prof.mispricing = MispricingProfile()
            if prof.btc_implied is None and coin != "BTC":
                prof.btc_implied = BtcImpliedProfile()

            # Reset mispricing profile on market switch (different strike = different distribution)
            current_slug = mdata.get("slug", "")
            if current_slug and prof.last_slug and current_slug != prof.last_slug:
                logger.info("Market switch %s: %s -> %s — resetting mispricing profile",
                            coin, prof.last_slug[:30], current_slug[:30])
                old_vol_tick = prof.mispricing.vol_tick_count if prof.mispricing else 0
                old_delta_ema = prof.mispricing.delta_ema if prof.mispricing else 0.0
                old_delta_var = prof.mispricing.delta_var_ema if prof.mispricing else 0.0
                prof.mispricing = MispricingProfile()
                # Carry over spot volatility stats (market-independent)
                if old_vol_tick > 0:
                    prof.mispricing.vol_tick_count = old_vol_tick
                    prof.mispricing.delta_ema = old_delta_ema
                    prof.mispricing.delta_var_ema = old_delta_var
            prof.last_slug = current_slug

            # Vol computation
            mp = prof.mispricing
            vol = mp.ema_hourly_volatility(interval) if mp.vol_tick_count >= 2 else 0.0

            # Feed spot delta into vol tracker
            if spot and spot > 0:
                b_alpha, c_alpha, mp_alpha = self._rb.get_alphas(coin, interval)
                vol_hl = self._rb.get_coin_param(coin, "vol_ema_halflife_secs",
                                                  _cfg(self._config, "vol_ema_halflife_secs"))
                vol_alpha = halflife_to_alpha(vol_hl, interval)

                # B-S model prob
                model_prob = compute_model_prob(spot, strike, hours_left, vol) if vol > 0 else 0.5

                # Feed mispricing
                mp.feed(model_prob, yes_price, spot, alpha=mp_alpha,
                        vol_ema_alpha=vol_alpha)
                vol = mp.ema_hourly_volatility(interval)

                # Recompute with updated vol
                if vol > 0:
                    model_prob = compute_model_prob(spot, strike, hours_left, vol)

                sig["model_prob"] = model_prob
                sig["vol"] = vol
                sig["mispricing"] = model_prob - yes_price

                # Feed BtcImpliedProfile
                if prof.btc_implied is not None and btc_spot > 0:
                    beta = prof.baseline_beta if prof.baseline_beta is not None else 1.0
                    prof.btc_implied.feed(
                        btc_spot, spot, beta, strike, hours_left, vol,
                        yes_price, return_alpha=c_alpha,
                        mispricing_alpha=mp_alpha,
                        spot_model_prob=model_prob,
                        btc_log_return=btc_log_return)

                # --- Dual-score entry ---
                spot_signal, spot_misp, spot_z = mp.should_trade(
                    min_history=int(_cfg(self._config, "edge_min_history_secs") / interval),
                    z_threshold=0,
                    min_vol_obs=int(_cfg(self._config, "edge_min_vol_obs_secs") / interval))
                edge_dir = mp.edge_direction()

                btc_signal = False
                btc_misp = 0.0
                btc_z = 0.0
                btc_dir = None
                if prof.btc_implied is not None:
                    btc_signal, btc_misp, btc_z = prof.btc_implied.should_trade(
                        min_history=int(_cfg(self._config, "edge_min_history_secs") / interval),
                        z_threshold=0)
                    btc_dir = prof.btc_implied.btc_direction()
                    # Follow rate floor gate
                    mr = merged_lag_rate(prof, weights, min_ev_curr)
                    follow_floor = _cfg(self._config, "btc_score_follow_rate_floor")
                    follow_r = 1.0 - mr  # follow_rate = 1 - lag_rate approximately
                    # Use actual follow_rate from layers
                    if prof.current.btc_move_seen >= min_ev_curr:
                        follow_r = prof.current.follow_rate
                    elif prof.last_hour.t1_resolved_seen > 0:
                        follow_r = prof.last_hour.follow_rate
                    else:
                        follow_r = prof.baseline.follow_rate
                    if follow_r < follow_floor:
                        btc_signal = False

                combined_z = 0.0
                if edge_dir is not None and btc_dir is not None and edge_dir == btc_dir:
                    spot_weight = self._rb.get_coin_param(coin, "spot_weight", self._config.get("spot_weight", 1.0))
                    btc_weight = self._rb.get_coin_param(coin, "btc_weight", self._config.get("btc_weight", 1.0))
                    direction_sign = 1.0 if edge_dir == "YES" else -1.0
                    combined_z = direction_sign * ((spot_z * spot_weight) + (btc_z * btc_weight))

                sig["spot_signal"] = spot_signal
                sig["btc_signal"] = btc_signal
                sig["z_score"] = spot_z
                sig["btc_z_score"] = btc_z
                sig["combined_z"] = combined_z
                sig["btc_mispricing"] = btc_misp

                # Behavioral z-scores
                sig["lag_z"] = lag_z_score(prof, weights, min_ev_curr,
                                           _cfg(self._config, "lag_z_min_var_obs"))
                sig["inverse_z"] = inverse_z_score(prof, weights, min_ev_curr,
                                                    _cfg(self._config, "lag_z_min_var_obs"))
                sig["confidence"] = compute_confidence(prof, _cfg(self._config, "confidence_tolerance"),
                                                        min_ev_curr)

                # Entry path selection
                paths = _cfg(self._config, "entry_path_priority")
                entry_path = None
                direction = None
                edge = 0.0

                for path in paths:
                    if path == "COMBINED" and spot_signal and btc_signal:
                        if edge_dir == btc_dir:
                            entry_path = "COMBINED"
                            direction = edge_dir
                            edge = spot_z + btc_z
                            sig["confidence"] = "HIGH"
                            break
                    elif path == "SPOT" and spot_signal:
                        entry_path = "SPOT"
                        direction = edge_dir
                        edge = spot_z
                        break
                    elif path == "BTC" and btc_signal:
                        entry_path = "BTC"
                        direction = btc_dir
                        edge = btc_z
                        break

                sig["entry_path"] = entry_path
                sig["direction"] = direction
                sig["edge"] = edge

            results[coin] = sig

        return results

    def _resolve_signals(self, prof: CoinProfile, coin: str,
                          coin_delta: float, btc_delta: float,
                          now_ts: float) -> None:
        remaining = []
        interval = self._get_interval_secs()
        b_alpha, c_alpha, _ = self._rb.get_alphas(coin, interval)

        for sig in prof.open_signals:
            elapsed = now_ts - sig.timestamp

            if sig.event_type == 1:
                timeout = self._get_timeout(1)
                thresh = self._dyn_thresh.get_coin_threshold(coin)
                if abs(coin_delta) >= thresh:
                    # Coin moved — check if followed or inversed
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
                    continue  # resolved
                elif elapsed >= timeout:
                    prof.type1.unresolved_count += 1
                    _feed_follow(prof, 0.0, b_alpha, c_alpha)
                    _feed_inverse(prof, 0.0, b_alpha, c_alpha)
                    continue  # timed out
                remaining.append(sig)

            elif sig.event_type == 3:
                timeout = self._get_timeout(3)
                thresh = self._dyn_thresh.get_coin_threshold(coin)
                # Correction = moved opposite to original delta
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
            "spot_signal": False,
            "btc_signal": False,
            "direction": None,
            "edge": 0.0,
            "z_score": 0.0,
            "btc_z_score": 0.0,
            "combined_z": 0.0,
            "entry_path": None,
            "confidence": "LOW",
            "event_type": 0,
            "model_prob": 0.5,
            "vol": 0.0,
            "mispricing": 0.0,
            "btc_mispricing": 0.0,
            "lag_z": 0.0,
            "inverse_z": 0.0,
        }
