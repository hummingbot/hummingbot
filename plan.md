# Plan: Port BTC Divergence Signal Engine to Hyperliquid Perps

## Context

The Limitless binary options system is retired. The hummingbot execution pipeline for Hyperliquid perps is proven working. The signal engine was ported wrong — the `controllers/directional_trading/hyperliquid_signal_engine.py` only has Type 1/2/3 classification with lag_z, missing the actual entry signal (`BtcImpliedProfile`) and all behavioral gating.

**However**, the COMPLETE, correct port already exists at `controllers/generic/hyperliquid/signal_engine.py` (821 lines). It has:
- Type 1/2/3 event classification + resolution tracking
- Three-layer EMA system (baseline/current/last_hour, hour boundary handling)
- BtcImpliedProfile (residual → implied spot → z-score entry signal)
- MispricingProfile (spot vs market_yes mispricing)
- Dual-score entry paths (COMBINED > SPOT > BTC priority)
- Follow rate gating (BTC-only entries require ≥30% follow rate)
- Dynamic thresholds (adaptive noise floors from rolling price data)
- Confidence scoring (layer agreement)
- Beta tracking + anomaly detection
- TypeStats (correction_rate, avg_lag_secs, avg_magnitude)

**Problem:** This generic engine still uses binary-options-specific inputs (YES price, strike, hours_left, Black-Scholes) and has integration bugs (controller calls wrong tick() signature, RuntimeBridge missing `get_alphas()`).

**Goal:** Adapt this complete engine for perps — strip binary options mechanics, use spot price directly, keep ALL behavioral tracking. Build with observation mode (`trading_enabled: false`).

---

## What the Original System Actually Does (Beyond Simple "BTC Moved → Trade")

The original system doesn't just detect divergence — it tracks WHETHER the coin even follows BTC, HOW LONG it takes, and adjusts confidence accordingly:

1. **Type 1 events** (BTC moved, coin flat) open signals that are **resolved** when:
   - Coin follows (same direction) → `follow_rate += 1.0`, record `correction_time`
   - Coin inverses (opposite) → `inverse_rate += 1.0`
   - Timeout → `unresolved_count += 1`

2. **follow_rate** = EMA of how often coin actually follows BTC. BTC-only entries require ≥30%. This prevents trading coins that historically don't track BTC.

3. **avg_lag_secs** = EMA of how long catch-up takes. Used to set `stop_timeout = avg_lag_secs × 1.5`. Without this you'd hold forever or close too early.

4. **Three-layer merge** = weighted [0.5, 0.3, 0.2] across baseline (24h memory), last_hour, current. Detects when behavior changes (e.g. coin was following BTC all day but stopped this hour).

5. **Confidence** = "HIGH" if all 3 layers agree on follow_rate (within 25pp), else "LOW".

6. **Dynamic thresholds** = rolling std × 1.5 for noise floors. What counts as "BTC moved" adapts to current volatility.

ALL of this applies to perps unchanged. Only the B-S probability layer is binary-options-specific.

---

## Adaptation: Binary Options → Perps

### Strip (binary-options-specific):
- `compute_model_prob()` / Black-Scholes / `_norm_cdf()` — no strike, no expiry
- `MispricingProfile` — compares spot vs market YES price (doesn't exist for perps)
- `market_yes`, `strike`, `hours_left` params from `BtcImpliedProfile.feed()`
- `btc_fair_prob` field (probability-space output)
- Market slug management and slug-based profile reset
- SPOT entry path (requires MispricingProfile) — keep BTC and simplified COMBINED
- "YES"/"NO" direction → "LONG"/"SHORT"

### Keep unchanged:
- Type 1/2/3 classification + resolution tracking
- Three-layer EMA (EMALayer, baseline/current/last_hour)
- All `_feed_*` functions (lag, follow, inverse, magnitude, directional, beta, lag_secs)
- `merged_lag_rate()`, `merged_inverse_rate()`
- `lag_z_score()`, `inverse_z_score()`, `beta_anomaly_signal()`, `inverse_beta_signal()`
- `compute_confidence()`
- `DynamicThresholds` class
- `_check_hour_boundary()`
- `OpenSignal` + `_resolve_signals()`
- `TypeStats` (correction_rate, avg_magnitude, avg_correction_time)
- `CoinProfile` (type1/2/3 stats, ratios, open_signals, three EMA layers)
- `halflife_to_alpha()`

### Adapt:
- **`BtcImpliedProfile.feed()`** — remove strike/hours_left/vol/market_yes params. Instead of computing `btc_fair_prob - market_yes`, track the **residual directly** as the "mispricing" signal
- **`BtcImpliedProfile.should_trade()`** — same gate hierarchy, z-score on residual instead of probability-space mispricing
- **`BtcImpliedProfile.btc_direction()`** — return "LONG"/"SHORT" instead of "YES"/"NO"
- **Type 1/2/3 deltas** — use **spot price log returns** instead of YES price deltas. `coin_delta = ln(coin_spot / prev_coin_spot)` instead of `yes_price - prev_yes`
- **`SignalEngine.tick()` signature** — simplify to `tick(coin_spots: Dict[str, float], btc_spot: float, now_ts: float)`. No `markets` dict with binary options metadata
- **RuntimeBridge** — use the full version from `binary_options/config.py` (has `get_alphas()`, `get_coin_param()`, `should_trade()`)
- **Entry path selection** — drop "SPOT" path. Keep "BTC" (primary) and a simplified "COMBINED" that checks behavioral + divergence agreement

---

## Files to Modify

### Replace (rewrite from generic/hyperliquid/signal_engine.py):
1. **`controllers/directional_trading/hyperliquid_signal_engine.py`**
   - Source: `controllers/generic/hyperliquid/signal_engine.py` (821 lines)
   - Adaptations: strip B-S/MispricingProfile, use spot deltas, adapt BtcImpliedProfile
   - Include: RuntimeBridge (full version), adapted fair_value classes, all behavioral tracking
   - Expected size: ~650-700 lines (removing ~120 lines of B-S/MispricingProfile)

### Update:
2. **`controllers/directional_trading/hyperliquid_stat_arb.py`**
   - Update controller to use new engine's tick() signature
   - Wire RuntimeBridge hot-reload
   - Add observation mode (force signal=0 when `trading_enabled: false`)
   - Rich status display (z_score, residual, follow_rate, confidence, beta, Type stats)

3. **`conf/controllers/conf_hyperliquid_stat_arb_1.yml`**
   - Add `runtime_json_path`

### Create:
4. **`conf/runtime_hyperliquid.json`**
   - All tunable params with `trading_enabled: false` (observation mode)

---

## Detailed Implementation

### Signal Engine (`hyperliquid_signal_engine.py`)

**Structure** — single file containing everything (no separate fair_value.py):

```
# Utilities
halflife_to_alpha()

# Adapted BtcImpliedProfile (stripped of B-S)
class BtcDivergenceProfile:
    - residual tracking (beta * btc_return_ema - coin_return_ema)
    - Welford EMA+variance on residual → z-score
    - feed(btc_spot, coin_spot, beta, return_alpha, mispricing_alpha)
    - should_trade(min_history, z_threshold) → (bool, residual, z_score)
    - direction() → "LONG" / "SHORT"

# Behavioral tracking (kept as-is from generic engine)
TypeStats, OpenSignal, EMALayer, CoinProfile
DynamicThresholds
_feed_lag, _feed_follow, _feed_inverse, _feed_magnitude, _feed_beta, _feed_directional, _feed_lag_secs
merged_lag_rate, merged_inverse_rate
lag_z_score, inverse_z_score
beta_anomaly_signal, inverse_beta_signal
compute_confidence
_check_hour_boundary

# RuntimeBridge (full version from binary_options/config.py)
class RuntimeBridge:
    - check() / _reload() / get_coin_param() / get_alphas() / should_trade()

# Main engine
class SignalEngine:
    - __init__(config, runtime_bridge)
    - tick(coin_spots, btc_spot, now_ts) → Dict[str, dict]
    - _resolve_signals()
    - _empty_signal()
```

**Key change in tick():**
```python
# OLD (binary options): uses YES price deltas for Type 1/2/3
coin_deltas[coin] = markets[coin]["yes_price"] - prev_yes[coin]

# NEW (perps): uses spot log return deltas for Type 1/2/3
if prev_spots[coin] > 0 and coin_spot > 0:
    coin_deltas[coin] = math.log(coin_spot / prev_spots[coin])

# OLD: btc_delta = btc_spot - prev_btc (dollar delta)
# NEW: btc_delta = math.log(btc_spot / prev_btc) (log return, consistent with coin)
```

**Key change in BtcDivergenceProfile.feed():**
```python
# OLD: computes btc_fair_prob via B-S, tracks btc_fair_prob - market_yes
btc_fair_prob = compute_model_prob(implied_spot, strike, hours_left, vol)
btc_mispricing = btc_fair_prob - market_yes

# NEW: tracks residual directly (no probability conversion)
# The residual IS the divergence signal in log-return space
divergence = self.residual  # = beta * btc_return_ema - coin_return_ema
# Z-score on divergence using same Welford EMA+variance
```

**Entry path selection (simplified for perps):**
```python
# No SPOT path (requires MispricingProfile / market_yes)
# BTC path: divergence z-score > threshold, follow_rate >= floor
# Direction: residual > 0 → LONG (coin undervalued), residual < 0 → SHORT
```

### Controller (`hyperliquid_stat_arb.py`)

```python
async def update_processed_data(self):
    # 1. Hot-reload check
    self._rb.check()

    # 2. Get prices
    spot_price = get_price(trading_pair)
    btc_price = get_price(btc_trading_pair)

    # 3. Tick engine (now takes simple coin_spots dict)
    signals = self._engine.tick(
        coin_spots={self._coin: spot_price},
        btc_spot=btc_price,
        now_ts=time.time()
    )

    # 4. Extract signal for this coin
    coin_signal = signals.get(self._coin, {})

    # 5. Observation mode gate
    if not self._rb.should_trade():
        signal = 0  # observation only
    else:
        entry_path = coin_signal.get("entry_path")
        direction = coin_signal.get("direction")
        if entry_path and direction:
            signal = 1 if direction == "LONG" else -1
        else:
            signal = 0

    # 6. Log rich status every tick
    logger.info("[%s] %s | btc=%.2f spot=%.4f impl=%.4f div=%+.4f%% "
                "beta=%.3f z=%.2f follow=%.0f%% conf=%s T1=%d/%d signal=%d%s",
                self.config.controller_name, self._coin,
                btc_price, spot_price,
                coin_signal.get("implied_spot", 0),
                coin_signal.get("divergence_pct", 0) * 100,
                coin_signal.get("beta", 0),
                coin_signal.get("z_score", 0),
                coin_signal.get("follow_rate", 0) * 100,
                coin_signal.get("confidence", "?"),
                coin_signal.get("type1_corrections", 0),
                coin_signal.get("type1_total", 0),
                signal,
                "(obs)" if not self._rb.should_trade() else "")

    self.processed_data = {"signal": signal, "features": coin_signal}
```

### Runtime Config (`conf/runtime_hyperliquid.json`)

```json
{
    "trading_enabled": false,
    "paused": false,
    "baseline_halflife_secs": 35.0,
    "current_halflife_secs": 12.0,
    "mispricing_halflife_secs": 23.0,
    "z_threshold": 2.0,
    "min_history": 10,
    "btc_score_follow_rate_floor": 0.3,
    "confidence_tolerance": 0.25,
    "min_btc_delta": 0.001,
    "min_coin_delta": 0.0005,
    "btc_reversal_z": 1.75,
    "coins": {
        "ETH": {},
        "SOL": {}
    }
}
```

`trading_enabled: false` → observation mode. Phil sets thresholds after reviewing signal data.

---

## Observation Mode Logging

Every tick logs rich signal data:
```
[hyperliquid_stat_arb] ETH | btc=87234.50 spot=3412.80 impl=3415.20 div=+0.07%
  beta=0.82 z=1.34 follow=68% conf=HIGH T1=23/34 signal=0(obs)
```

Fields: BTC price, coin spot, BTC-implied spot, divergence %, beta coefficient, z-score, follow rate, confidence, Type 1 resolution ratio, signal (0 in observation mode).

---

## Verification

1. **Import check:** `python -c "from controllers.directional_trading.hyperliquid_signal_engine import SignalEngine, RuntimeBridge"`
2. **Controller load:** `start --v2 conf_v2_hyperliquid_1.yml` — confirms clean init
3. **Price feed:** `status` shows BTC and coin prices updating
4. **Signal computation:** Watch logs — z-score changes as prices move
5. **Behavioral tracking:** Type 1 events accumulate, follow_rate updates, confidence computed
6. **Observation mode:** `trading_enabled: false` → no executors created, signal=0(obs) in logs
7. **Hot-reload:** Edit `runtime_hyperliquid.json` → new values take effect within 5s
8. **Sanity:** BTC goes up, ETH doesn't follow → positive residual → would-be LONG. BTC goes down, ETH doesn't follow → negative residual → would-be SHORT
