"""Fair value model for binary options — Hummingbot BinaryOptionsController.

Uses Black-Scholes formula for binary options:
    P(S_T > K) = Φ(d2)  where  d2 = (ln(S/K) - (σ²/2)τ) / (σ√τ)

Where:
    S = current spot price (from Pyth oracle)
    K = strike price (from market metadata)
    τ = time to expiry in hours
    σ = hourly volatility (from observed price deltas)
    Φ = standard normal CDF

No external dependencies — uses math.erf for normal CDF.
"""
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

_LN2 = math.log(2)


def halflife_to_alpha(halflife_secs: float, interval_secs: float) -> float:
    """Convert a half-life (in seconds) to a per-tick EMA alpha.

    EMA half-life is the wall-clock time for past observations to decay to 50%.
    This decouples the smoothing parameter from the polling interval, so changing
    poll_interval_ms doesn't silently change vol estimation behavior.

    Formula: alpha = 1 - exp(-ln(2) * interval / halflife)
    For small alpha (halflife >> interval), this approximates ln(2) * interval / halflife.
    """
    if halflife_secs <= 0 or interval_secs <= 0:
        return 0.01  # safe fallback
    alpha = 1.0 - math.exp(-_LN2 * interval_secs / halflife_secs)
    return max(0.0001, min(0.5, alpha))  # clamp to sane range


def secs_to_ticks(secs: float, interval_secs: float) -> int:
    """Convert a time duration (seconds) to tick count for the current interval."""
    if interval_secs <= 0:
        return 1
    return max(1, round(secs / interval_secs))


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf. No scipy needed."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def compute_model_prob(spot: float, strike: float,
                       hours_to_expiry: float, hourly_vol: float) -> float:
    """Compute fair probability that spot > strike at expiry.

    Binary option Black-Scholes: P(S_T > K) = Φ(d2)
    where d2 = (ln(S/K) - (σ²/2)τ) / (σ√τ)

    Returns probability in [0, 1]. Clamps edge cases.
    """
    if spot <= 0 or strike <= 0 or hours_to_expiry <= 0:
        return 0.5  # can't compute — return neutral
    if hourly_vol <= 0:
        # Zero vol: binary outcome based on spot vs strike
        return 1.0 if spot > strike else 0.0

    tau = hours_to_expiry
    log_ratio = math.log(spot / strike)
    d2 = (log_ratio - (hourly_vol ** 2 / 2.0) * tau) / (hourly_vol * math.sqrt(tau))

    prob = _norm_cdf(d2)
    return max(0.001, min(0.999, prob))  # clamp to avoid 0/1 extremes


def compute_edge(model_prob: float, market_yes: float) -> float:
    """Compute edge: positive = YES underpriced, negative = YES overpriced.

    edge > 0 → BUY YES (market < fair)
    edge < 0 → BUY NO  (market > fair)
    """
    return model_prob - market_yes


def compute_hourly_volatility(deltas: list, interval_secs: float) -> float:
    """Compute hourly volatility from observed log returns.

    Args:
        deltas: list of signed log returns (ln(spot/prev))
        interval_secs: seconds between observations

    Returns:
        Hourly volatility (std of per-tick log returns * sqrt(ticks_per_hour))
    """
    if len(deltas) < 5 or interval_secs <= 0:
        return 0.0

    n = len(deltas)
    mean = sum(deltas) / n
    variance = sum((d - mean) ** 2 for d in deltas) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0

    # Scale to hourly: std * sqrt(ticks_per_hour)
    ticks_per_hour = 3600.0 / interval_secs
    return std * math.sqrt(ticks_per_hour)


@dataclass
class MispricingProfile:
    """Per-coin mispricing statistics, EMA-smoothed.

    Tracks the distribution of (model_prob - market_yes) over time for each coin.
    Triggers EDGE signals when current mispricing exceeds the coin's own EMA + std.
    """
    mispricing_ema: float = 0.0       # EMA of (fair_value - market_yes)
    mispricing_var_ema: float = 0.0   # EMA of (mispricing - ema)^2 for std
    mispricing_history: list = field(default_factory=list)  # last N raw mispricings
    spot_price: float = 0.0           # last known Pyth spot
    model_prob: float = 0.0           # last computed fair value
    volatility: float = 0.0           # rolling hourly vol from observed deltas
    delta_history: list = field(default_factory=list)  # last N spot price deltas (for min_vol_obs gate)
    last_spot: float = 0.0            # previous spot for delta computation
    total_ticks: int = 0              # how many ticks we've observed
    # EMA-smoothed volatility (Welford online variance of spot log returns)
    delta_ema: float = 0.0            # EMA of spot log returns
    delta_var_ema: float = 0.0        # EMA of (delta - delta_ema)^2
    vol_tick_count: int = 0           # how many deltas fed into EMA vol
    # Z-score velocity tracking — ring buffer of (timestamp, z_score) for dz/dt
    _z_history: deque = field(default_factory=lambda: deque(maxlen=30))

    @property
    def mispricing_std(self) -> float:
        """Current std of mispricing from EMA variance."""
        return math.sqrt(max(0.0, self.mispricing_var_ema))

    def feed(self, model_prob: float, market_yes: float, spot: float,
             alpha: float = 0.15, max_history: int = 100,
             vol_ema_alpha: float = 0.01):
        """Update mispricing stats with new observation.

        Args:
            model_prob: Black-Scholes fair probability
            market_yes: current YES price from market
            spot: current Pyth spot price
            alpha: EMA smoothing factor for mispricing
            max_history: max raw mispricing history to keep
            vol_ema_alpha: EMA smoothing factor for volatility (lower = longer memory)
        """
        self.model_prob = model_prob
        self.spot_price = spot
        self.total_ticks += 1

        mispricing = model_prob - market_yes

        # Track spot log returns — EMA vol + short history for min_vol_obs gate
        if self.last_spot > 0 and spot > 0:
            spot_delta = math.log(spot / self.last_spot)  # signed log return
            # Keep short history for the min_vol_obs gate only
            self.delta_history.append(spot_delta)
            if len(self.delta_history) > max_history:
                self.delta_history = self.delta_history[-max_history:]
            # EMA-smoothed variance of spot deltas (Welford online)
            self.vol_tick_count += 1
            if self.vol_tick_count <= 1:
                self.delta_ema = spot_delta
                self.delta_var_ema = 0.0
            else:
                d_diff = spot_delta - self.delta_ema
                self.delta_ema += vol_ema_alpha * d_diff
                self.delta_var_ema = (1.0 - vol_ema_alpha) * (
                    self.delta_var_ema + vol_ema_alpha * d_diff * d_diff)
        self.last_spot = spot

        # Raw history (for evaluator analysis)
        self.mispricing_history.append(mispricing)
        if len(self.mispricing_history) > max_history:
            self.mispricing_history = self.mispricing_history[-max_history:]

        # EMA update
        if self.total_ticks <= 1:
            self.mispricing_ema = mispricing
            self.mispricing_var_ema = 0.0
        else:
            diff = mispricing - self.mispricing_ema
            self.mispricing_ema += alpha * diff
            self.mispricing_var_ema = (1.0 - alpha) * (self.mispricing_var_ema + alpha * diff * diff)

    def feed_delta(self, spot: float, vol_ema_alpha: float = 0.01):
        """Feed a spot price delta without model computation (warmup phase).

        Used when vol is not yet reliable enough for Black-Scholes.
        Only updates delta EMA/variance and delta_history.
        """
        if self.last_spot > 0 and spot > 0:
            spot_delta = math.log(spot / self.last_spot)
            self.delta_history.append(spot_delta)
            if len(self.delta_history) > 100:
                self.delta_history = self.delta_history[-100:]
            self.vol_tick_count += 1
            if self.vol_tick_count <= 1:
                self.delta_ema = spot_delta
                self.delta_var_ema = 0.0
            else:
                d_diff = spot_delta - self.delta_ema
                self.delta_ema += vol_ema_alpha * d_diff
                self.delta_var_ema = (1.0 - vol_ema_alpha) * (
                    self.delta_var_ema + vol_ema_alpha * d_diff * d_diff)
        self.last_spot = spot
        self.total_ticks += 1

    def ema_hourly_volatility(self, interval_secs: float) -> float:
        """Compute hourly volatility from EMA-smoothed variance.

        Uses per-asset realized vol only. Each asset's own spot price
        log returns feed the EMA — no cross-asset blending.

        Args:
            interval_secs: seconds between observations (for scaling to hourly)

        Returns:
            Hourly volatility (per-tick EMA std × √ticks_per_hour).
        """
        if self.vol_tick_count < 2 or interval_secs <= 0:
            return 0.0

        per_tick_std = math.sqrt(max(0.0, self.delta_var_ema))
        ticks_per_hour = 3600.0 / interval_secs
        return per_tick_std * math.sqrt(ticks_per_hour)

    def should_trade(self, min_history: int = 10, z_threshold: float = 1.0,
                     min_mispricing: float = 0.0, min_vol_obs: int = 20) -> tuple:
        """Check if current mispricing is anomalous AND large enough to trade.

        Gate hierarchy (ALL must pass):
        1. Enough total ticks observed (min_history)
        2. Enough volatility observations for reliable vol estimate (min_vol_obs)
        3. Mispricing std is meaningful (> 0.001)
        4. Absolute mispricing exceeds min_mispricing (caller computes from spread)
        5. Z-score exceeds z_threshold (deviation from coin's own mean)

        Args:
            min_history: minimum ticks before signals fire
            z_threshold: z-score threshold (default 1.0, other gates filter noise)
            min_mispricing: minimum abs(mispricing) — typically spread * pct
            min_vol_obs: minimum delta observations for reliable volatility

        Returns:
            (should_trade: bool, current_mispricing: float, z_score: float)
        """
        if self.total_ticks < min_history:
            return False, 0.0, 0.0

        if not self.mispricing_history:
            return False, 0.0, 0.0

        # Gate: need enough spot deltas for a reliable volatility estimate
        # Uses vol_tick_count (uncapped counter) — NOT len(delta_history) which
        # is capped at max_history=100 and would permanently block at fast
        # polling intervals (e.g. 250ms → 280 ticks needed but buffer max 100).
        if self.vol_tick_count < min_vol_obs:
            return False, 0.0, 0.0

        current = self.mispricing_history[-1]
        std = self.mispricing_std

        if std <= 0.001:  # too little variance to judge
            return False, current, 0.0

        # Gate: absolute mispricing must be large enough to be tradeable
        if abs(current) < min_mispricing:
            return False, current, 0.0

        z_score = abs(current - self.mispricing_ema) / std
        if z_score > z_threshold:
            return True, current, z_score

        return False, current, z_score

    def edge_direction(self) -> Optional[str]:
        """Get trade direction from mispricing sign.

        Returns "YES" if underpriced, "NO" if overpriced, None if no data.
        """
        if not self.mispricing_history:
            return None
        current = self.mispricing_history[-1]
        if current > 0:
            return "YES"   # market < fair → buy YES
        elif current < 0:
            return "NO"    # market > fair → buy NO
        return None

    def record_z(self, z_score: float, ts: float = 0.0):
        """Record a z-score observation for velocity tracking.

        Args:
            ts: timestamp in seconds (caller must provide)
        """
        if ts <= 0.0:
            raise ValueError("ts must be a positive timestamp")
        self._z_history.append((ts, z_score))

    def z_velocity(self, window_secs: float = 5.0) -> float:
        """Compute z-score velocity (dz/dt) over the given window.

        Returns the rate of z-score change per second. Positive = divergence
        growing, negative = divergence shrinking.

        Uses simple finite difference: (z_now - z_at_window_ago) / elapsed.
        Returns 0.0 if insufficient history.
        """
        if len(self._z_history) < 2:
            return 0.0
        now_ts, now_z = self._z_history[-1]
        target_ts = now_ts - window_secs
        # Find the tick closest to target_ts
        best_z = None
        best_gap = float("inf")
        for ts, z in self._z_history:
            gap = abs(ts - target_ts)
            if gap < best_gap:
                best_gap = gap
                best_z = z
        # Need at least 2s of history to compute meaningful velocity
        if best_z is None or best_gap > window_secs * 0.8:
            return 0.0
        elapsed = window_secs
        if elapsed <= 0:
            return 0.0
        return (now_z - best_z) / elapsed

    def conflicts_with(self, divergence_direction: str) -> bool:
        """Check if edge direction conflicts with a divergence signal.

        Returns True if edge says opposite direction (veto condition).
        """
        edge_dir = self.edge_direction()
        if edge_dir is None:
            return False  # no data → no conflict
        return edge_dir != divergence_direction

    def agrees_with(self, divergence_direction: str) -> bool:
        """Check if edge direction agrees with a divergence signal (boost condition)."""
        edge_dir = self.edge_direction()
        if edge_dir is None:
            return False
        return edge_dir == divergence_direction


@dataclass
class BtcImpliedProfile:
    """BTC-implied mispricing: where the coin SHOULD be based on BTC movement.

    Computes residual = beta * btc_spot_return - coin_spot_return.
    Positive residual → coin undervalued (BTC moved, coin didn't follow) — old T1.
    Negative residual → coin overvalued (coin spiked without BTC) — old T3_FADE.
    Inverse detection is automatic (opposite move → larger residual).

    Uses existing halflifes from the three-layer EMA system:
      - current_halflife_secs (12s) → return EMAs (divergence window)
      - mispricing_halflife_secs (23s) → mispricing EMA/variance (z-score)
    """
    # Per-tick return EMA (alpha from current_halflife_secs)
    btc_return_ema: float = 0.0
    coin_return_ema: float = 0.0
    last_btc_spot: float = 0.0
    last_coin_spot: float = 0.0

    # BTC-implied mispricing tracking (alpha from mispricing_halflife_secs)
    btc_mispricing_ema: float = 0.0
    btc_mispricing_var_ema: float = 0.0
    btc_mispricing_history: list = field(default_factory=list)
    total_ticks: int = 0
    implied_spot: float = 0.0
    residual: float = 0.0
    btc_fair_prob: float = 0.0

    @property
    def btc_mispricing_std(self) -> float:
        return math.sqrt(max(0.0, self.btc_mispricing_var_ema))

    def feed(self, btc_spot: float, coin_spot: float, beta: float,
             strike: float, hours_left: float, vol: float,
             market_yes: float, return_alpha: float,
             mispricing_alpha: float, max_history: int = 100,
             spot_model_prob: float = 0.0, btc_log_return: float = None):
        """Update each tick with new spot data.

        Args:
            btc_spot: BTC Pyth spot price
            coin_spot: Coin Pyth spot price
            beta: baseline_beta from EMA layers (YES-price-level)
            strike: market strike price
            hours_left: hours to market expiry
            vol: hourly volatility (shared with Spot Score)
            market_yes: current YES price
            return_alpha: from current_halflife_secs (per-coin tuned)
            mispricing_alpha: from mispricing_halflife_secs (per-coin tuned)
            max_history: max raw mispricing history to keep
            spot_model_prob: if >0, reuse Spot Score's B-S when residual ≈ 0
            btc_log_return: precomputed BTC log return (skips per-coin recomputation)
        """
        self.total_ticks += 1

        # Compute spot log returns (BTC return can be precomputed once per tick)
        if btc_log_return is not None:
            btc_ret = btc_log_return
        elif self.last_btc_spot > 0 and btc_spot > 0:
            btc_ret = math.log(btc_spot / self.last_btc_spot)
        else:
            btc_ret = 0.0
        coin_return = 0.0
        if self.last_coin_spot > 0 and coin_spot > 0:
            coin_return = math.log(coin_spot / self.last_coin_spot)
        self.last_btc_spot = btc_spot
        self.last_coin_spot = coin_spot

        # First tick: seed only
        if self.total_ticks <= 1:
            return

        # Update return EMAs
        if self.total_ticks == 2:
            self.btc_return_ema = btc_ret
            self.coin_return_ema = coin_return
        else:
            self.btc_return_ema += return_alpha * (btc_ret - self.btc_return_ema)
            self.coin_return_ema += return_alpha * (coin_return - self.coin_return_ema)

        # Residual: how much coin deviates from BTC-implied movement
        self.residual = beta * self.btc_return_ema - self.coin_return_ema

        # Implied spot: where coin should be if it tracked BTC perfectly
        if abs(self.residual) < 1e-6:
            self.implied_spot = coin_spot
        else:
            self.implied_spot = coin_spot * math.exp(self.residual)

        # B-S fair prob from implied spot — skip when residual ≈ 0 (reuse Spot Score)
        if abs(self.residual) < 1e-6 and spot_model_prob > 0:
            self.btc_fair_prob = spot_model_prob
        else:
            self.btc_fair_prob = compute_model_prob(
                self.implied_spot, strike, hours_left, vol)

        # BTC mispricing: how far market is from BTC-implied fair value
        btc_mispricing = self.btc_fair_prob - market_yes

        # Track mispricing history
        self.btc_mispricing_history.append(btc_mispricing)
        if len(self.btc_mispricing_history) > max_history:
            self.btc_mispricing_history = self.btc_mispricing_history[-max_history:]

        # EMA update (same Welford pattern as MispricingProfile)
        if self.total_ticks <= 2:
            self.btc_mispricing_ema = btc_mispricing
            self.btc_mispricing_var_ema = 0.0
        else:
            diff = btc_mispricing - self.btc_mispricing_ema
            self.btc_mispricing_ema += mispricing_alpha * diff
            self.btc_mispricing_var_ema = (1.0 - mispricing_alpha) * (
                self.btc_mispricing_var_ema + mispricing_alpha * diff * diff)

    def should_trade(self, min_history: int = 10, z_threshold: float = 0.0,
                     min_mispricing: float = 0.0) -> tuple:
        """Check if BTC-implied mispricing is anomalous enough to trade.

        Same gate hierarchy as MispricingProfile.should_trade():
        1. Enough ticks (min_history)
        2. std > 0.001
        3. abs(mispricing) > min_mispricing
        4. z-score > z_threshold

        Returns: (should_trade, btc_mispricing, z_score)
        """
        if self.total_ticks < min_history:
            return False, 0.0, 0.0
        if not self.btc_mispricing_history:
            return False, 0.0, 0.0

        current = self.btc_mispricing_history[-1]
        std = self.btc_mispricing_std

        if std <= 0.001:
            return False, current, 0.0
        if abs(current) < min_mispricing:
            return False, current, 0.0

        z_score = abs(current - self.btc_mispricing_ema) / std
        if z_score > z_threshold:
            return True, current, z_score
        return False, current, z_score

    def btc_direction(self) -> Optional[str]:
        """Trade direction from BTC-implied mispricing.

        Positive mispricing → YES underpriced (coin should be higher) → buy YES
        Negative mispricing → NO underpriced (coin should be lower) → buy NO
        """
        if not self.btc_mispricing_history:
            return None
        current = self.btc_mispricing_history[-1]
        if current > 0:
            return "YES"
        elif current < 0:
            return "NO"
        return None
