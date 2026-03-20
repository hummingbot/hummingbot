# 01 — divergence_tracker.py — Full Code Extraction

**File:** `skills/limitless-recon/scripts/divergence_tracker.py` (3471 lines)
**Purpose:** Real-time divergence tracker for Limitless hourly binary options markets. Polls market prices, classifies BTC/alt movements into behavioral types, computes fair-value mispricing via Black-Scholes + Pyth oracles, generates entry signals, and feeds them to a trader module.

---

## Table of Contents

1. [Constants & Configuration](#1-constants--configuration)
2. [Data Structures](#2-data-structures)
3. [Classes](#3-classes)
4. [Signal Generation](#4-signal-generation)
5. [Market Selection](#5-market-selection)
6. [Main Loop](#6-main-loop)
7. [Data Flow](#7-data-flow)
8. [V2 Mapping](#8-v2-mapping)

---

## 1. Constants & Configuration

### File Paths

```python
SKILL_DIR = Path(__file__).resolve().parent.parent  # limitless-recon/
CONFIG_PATH = SKILL_DIR / "config.json"
RUNTIME_PATH = SKILL_DIR / "data" / "runtime.json"
EMA_STATE_PATH = SKILL_DIR / "data" / "ema_state.json"
EMA_SAVE_INTERVAL = 600  # seconds, overridden at runtime
RUNTIME_CHECK_INTERVAL = 30  # seconds between runtime.json stat() checks
ENV_PATH = SKILL_DIR / ".env"
```

### CSV Field Schemas

**Event CSV (`CSV_FIELDS`):**
```
timestamp, event_id, coin, event_type, subtype, confidence,
btc_delta, coin_delta, ratio, btc_price, coin_price,
coin_strike, alert
```

**Tick Snapshot CSV (`SNAP_FIELDS`):**
```
timestamp, coin, spot, yes_price, no_price,
mispricing, mispricing_std, z_score, vol, model_prob,
strike, hours_left, max_spread,
btc_spot, btc_delta, coin_delta,
event_type, lag_z, inv_z, lag_rate,
beta_anomaly, inverse_beta, beta_baseline, beta_recent,
btc_mispricing, btc_mispricing_std, btc_z_score,
implied_spot, residual,
z_velocity,
tick_ms,
entry_candidate, entry_path, entry_direction,
entry_size_usd, entry_price_ref,
depth_yes_usd, depth_no_usd, depth_relevant_usd,
min_book_depth_req_usd,
buy_slip_est, sell_slip_est, total_exec_cost_est,
edge_raw_est, edge_after_cost_est, edge_slip_ratio_est,
pre_gate_pass, pre_gate_reason, exec_gate_evaluated,
exec_gate_pass, exec_reject_reason
```

### COIN_ORDER
```python
COIN_ORDER = ["BTC", "ETH", "SOL"]  # display sort priority
```

### DEFAULT_CFG (complete)

All keys with their defaults:

| Key | Default | Description |
|-----|---------|-------------|
| `poll_interval_ms` | 500 | Tick loop interval |
| `min_btc_delta` | 10.0 | BTC move threshold in dollars |
| `min_coin_delta` | 0.005 | Coin move threshold (yes_price delta) |
| `alert_std_threshold` | 2.0 | Alert when ratio > N std from baseline |
| `type3_timeout_seconds` | 0 (auto) | T3 signal resolution timeout |
| `type1_timeout_seconds` | 0 (auto) | T1 signal resolution timeout |
| `min_events_for_score` | 3 | Min T2 events for baseline |
| `min_signals_reliable` | 3 | Min signals before "tradeable" |
| `reliable_correction_pct` | 60 | Correction % for tradeable |
| `btc_z_threshold` | 1.75 | Z-score gate for BTC-only entries |
| `btc_score_follow_rate_floor` | 0.3 | Min follow_rate for BTC-only entries |
| `independent_entry_paths_enabled` | True | SPOT/BTC/COMBINED independent candidate loop |
| `lag_z_min_var_obs` | 10 | Min obs for lag_z computation |
| `t3_correction_rate_threshold` | 0.4 | T3 FADE vs FOLLOW classification |
| `market_duration_seconds` | 3600 | Hourly markets |
| `market_max_expiry_minutes` | 360 | Discovery window (6h = daily markets) |
| `stop_fallback_pct` | 0.05 | Fallback stop = 5% of market duration |
| `stop_ema_multiplier` | 1.5 | Stop = avg_lag_secs × this |
| `capital` | 1000 | Total capital |
| `risk_per_trade` | 0.02 | Fraction per trade |
| `max_open_positions` | 5 | Max simultaneous positions |
| `max_total_exposure_pct` | 0.30 | Max total exposure fraction |
| `max_spread` | 0.15 | Reject entry if spread > this |
| `min_events_base` | 3 | Dynamic min_events floor |
| `min_events_max` | 10 | Dynamic min_events ceiling |
| `min_correction_rate` | 0.5 | Min correction rate for T3 entry |
| `min_observations_full_size` | 5 | Obs needed before full size |
| `btc_reversal_multiplier` | 5.2405 | Net BTC delta for reversal |
| `trailing_stop_trigger_pct` | 0.3 | Arm trailing stop at this % of magnitude |
| `trailing_stop_distance_pct` | 0.225 | Close when profit drops this % from peak |
| `timeout_extension_factor` | 1.5 | Default timeout extension when trending |
| `max_timeout_multiplier` | 2.905 | Hard ceiling = fallback × this |
| `t1_lag_weight` | 0.4 | T1 reliability weight for lag_rate |
| `t1_follow_weight` | 0.6 | T1 reliability weight for follow_rate |
| `magnitude_threshold_std_factor` | 1.0 | TP threshold = mean - std × this |
| `tp_fallback_baseline_pct` | 0.5 | TP fallback: baseline.magnitude × this |
| `tp_fallback_vol_pct` | 0.5 | TP fallback: mispricing.vol × this |
| `tp_fallback_floor` | 0.01 | TP fallback: absolute minimum |
| `ema_save_interval_seconds` | 600 | Crash recovery save interval |
| `max_history_ratios` | 100 | Keep last N ratios per coin |
| `max_history_stats` | 50 | Keep last N magnitudes/correction_times |
| `max_scale_in_entries` | 3 | Max entries per coin+signal |
| `scale_in_cooldown_seconds` | 30 | Min seconds between scale-ins |
| `scale_in_size_decay` | 0.7 | Each additional entry × decay^n |
| `baseline_halflife_secs` | 35 | 24h personality — slow EMA |
| `current_halflife_secs` | 12 | Current hour — fast EMA |
| `mispricing_halflife_secs` | 23 | Mispricing EMA smoothing |
| `ema_weights` | [0.5, 0.3, 0.2] | [baseline, last_hour, current] |
| `min_events_current_hour` | 3 | Min BTC-move events to trust current layer |
| `confidence_tolerance` | 0.25 | Max layer divergence for HIGH confidence |
| `pyth_enabled` | True | Fetch Pyth spot prices |
| `edge_min_history_secs` | 50 | Min seconds before EDGE fires |
| `edge_max_size_multiplier` | 2.0 | Max sizing boost from z-score |
| `mispricing_ema_alpha` | 0.15 | Legacy fallback |
| `edge_z_threshold` | 1.5 | Z-score threshold for EDGE |
| `edge_min_vol_obs_secs` | 100 | Min seconds of vol observations |
| `edge_base_size_multiplier` | 1.5 | EDGE base size = base × this |
| `edge_max_concurrent` | 3 | Max simultaneous EDGE positions |
| `edge_decay_exponent` | 2.15 | Time decay exponent |
| `edge_stop_loss_pct` | 0.29 | Hard stop: exit if uPnL < -29% |
| `stop_loss_grace_secs` | 20 | Grace period before stop activates |
| `vol_ema_halflife_secs` | 350 | EMA half-life for realized vol |
| `dyn_thresh_min_samples` | 10 | Samples before dynamic thresholds activate |
| `dyn_thresh_floor_pct` | 0.3 | Floor = static × 30% |
| `startup_no_trade_seconds` | 120 | Grace period at startup — no trades |

### Config Loading

`load_config()` → Reads `config.json`, overlays `divergence` section onto `DEFAULT_CFG`. Any key in `DEFAULT_CFG` that also exists in `config.json.divergence` gets overridden.

`load_telegram_config()` → Reads `telegram` section from `config.json`.

---

## 2. Data Structures

### TypeStats (dataclass)

Per-event-type statistics for a single coin.

```python
@dataclass
class TypeStats:
    count: int = 0
    magnitudes: list = []          # abs(coin_delta) or abs(btc_delta)
    correction_count: int = 0
    unresolved_count: int = 0
    correction_times: list = []    # seconds to correct

    # Properties:
    correction_rate = correction_count / (correction_count + unresolved_count)
    avg_magnitude = mean(magnitudes)
    avg_correction_time = mean(correction_times)
```

### OpenSignal (dataclass)

A pending Type 1 or Type 3 signal waiting for resolution.

```python
@dataclass
class OpenSignal:
    event_type: int          # 1 or 3
    event_id: int
    timestamp: str           # ISO UTC
    coin_delta: float        # how much coin moved (T3) or 0 (T1)
    btc_delta: float         # how much BTC moved (T1) or 0 (T3)
    created_mono: float = 0  # time.monotonic() at creation
```

### EMALayer (dataclass)

One layer of the three-tier EMA system. Three instances per coin: `baseline`, `last_hour`, `current`.

```python
@dataclass
class EMALayer:
    lag_rate: float = 0.0          # How often coin lags BTC (Type 1 frequency)
    follow_rate: float = 0.0       # How often coin eventually follows BTC
    avg_lag_secs: float = 0.0      # Average seconds to follow
    magnitude: float = 0.0         # EMA of co-movement ratio
    up_follow_rate: float = 0.0    # Follow rate when BTC goes up
    down_follow_rate: float = 0.0  # Follow rate when BTC goes down
    inverse_rate: float = 0.0      # How often coin moves OPPOSITE to BTC
    lag_rate_var: float = 0.0      # Variance of lag_rate (for z-score)
    inverse_rate_var: float = 0.0  # Variance of inverse_rate
    btc_move_seen: int = 0         # Total BTC move events observed
    t1_resolved_seen: int = 0      # Total T1 signals resolved
    beta_sum: float = 0.0          # Sum of valid betas
    beta_count: int = 0            # Number of beta observations
```

**Layer cadences:**
- `baseline`: alpha from halflife=35s, never resets (24h personality)
- `last_hour`: snapshot of previous hour's `current` layer
- `current`: alpha from halflife=12s, resets each hour boundary

### CoinProfile (dataclass)

Complete behavioral profile for a single coin.

```python
@dataclass
class CoinProfile:
    type1: TypeStats       # BTC moved, coin flat
    type2: TypeStats       # Both moved (co-movement)
    type3: TypeStats       # BTC flat, coin moved

    ratios: list           # Type 2 co-movement ratios (coin_delta / btc_delta)
    open_signals: list     # List of OpenSignal awaiting resolution
    ticks_idle: int = 0    # Ticks since last movement

    # Three-layer EMA system
    baseline: EMALayer     # 24h slow personality
    last_hour: EMALayer    # Previous hour snapshot
    current: EMALayer      # Current hour, fast
    hour_started: int = -1 # UTC hour (0-23) when current layer last reset

    # Fair value (lazy-init)
    mispricing: object = None      # MispricingProfile (from fair_value module)
    btc_implied: object = None     # BtcImpliedProfile (from fair_value module)
```

**Key properties:**

```
total_events = type1.count + type2.count + type3.count
abs_correlation = |mean(ratios)|
sign_stability = max(pos_count, neg_count) / total_ratios
magnitude_consistency = 1 / (1 + std(ratios))
baseline_ratio = mean(ratios)
ratio_std = sample_std(ratios)

type3_score = count × correction_rate × (1/max(1, avg_correction_time))
type1_score = count × correction_rate × (1/max(1, avg_correction_time))

baseline_beta = baseline.beta_sum / baseline.beta_count  (if count >= 5)
recent_beta = (current.beta_sum + last_hour.beta_sum) / (current.beta_count + last_hour.beta_count)  (if count >= 3)
beta_anomaly_score = max(0, 1 - recent_beta/baseline_beta)
inverse_beta_score = recent_beta  (negative = opposite movement)
```

---

## 3. Classes

### DynamicThresholds

Adaptive noise floors from rolling price data. Replaces fixed `min_btc_delta` / `min_coin_delta`.

```python
class DynamicThresholds:
    __init__(static_btc_delta, static_coin_delta,
             window=60, multiplier=1.5, min_samples=10, floor_pct=0.3)

    # State:
    _btc_deltas: list        # Recent abs(btc_delta), capped at window
    _coin_deltas: dict       # coin → list of abs(coin_delta)
    btc_threshold: float     # Current effective BTC threshold
    coin_thresholds: dict    # coin → current effective threshold
```

**Algorithm:**
- `feed(btc_delta, coin_deltas)` → Appends abs values, trims to window, recomputes.
- `_recompute()`:
  - If `len(btc_deltas) >= min_samples`: `btc_threshold = max(std(btc_deltas) × multiplier, static_btc × floor_pct)`
  - Same per-coin for `coin_thresholds`.
- Falls back to static config values until enough data.

### RuntimeConfig

Hot-reloadable runtime parameters from `data/runtime.json`.

```python
class RuntimeConfig:
    HALFLIFE_KEYS = ("baseline_halflife_secs", "current_halflife_secs", "mispricing_halflife_secs")
    ALPHA_KEYS = ("baseline_alpha", "current_alpha", "mispricing_alpha")  # legacy

    __init__(path=RUNTIME_PATH)
    # State:
    trading_enabled: bool = True
    paused: bool = False
    overrides: dict          # key → value (ALL keys except trading_enabled, paused, coins)
    coin_alphas: dict        # COIN → {halflife_key: value}
    _alpha_cache: dict       # per-tick cache, cleared on reload
```

**Loading logic:**
- `_load()`: stat() file, compare mtime. On change: read JSON.
  - `_SKIP_KEYS = {"trading_enabled", "paused", "coins"}`
  - All other top-level keys → `overrides` dict.
  - `coins` block: per-coin params become `overrides[f"{COIN}_{key}"]` (numeric) or structured values (dicts/lists like `streak_cooldown`, `entry_vol_range`).
  - Halflife/alpha keys in coin block → `coin_alphas[COIN]`.
  - `_META_KEYS = {"tier", "probation_started_at"}` — skipped.
- `check()`: Called every tick. Only stats file every 30s (RUNTIME_CHECK_INTERVAL).
- `should_trade()`: `trading_enabled and not paused`

**`get_alphas(coin, default_b_hl, default_c_hl, default_mp_hl=23, interval_secs=5.0)` → (baseline_α, current_α, mispricing_α)**:
- Checks `coin_alphas[COIN]` for halflife_secs keys first, then legacy alpha keys.
- Converts halflife → per-tick alpha via `fair_value.halflife_to_alpha(halflife, interval)`.
- Formula: `α = 1 - exp(-ln(2) × interval / halflife)` (from fair_value module).
- Results cached per tick.

### CoinRoster

Three-tier coin management: MAIN / PROBATION / REHAB / BANNED.

```python
class CoinRoster:
    __init__(path=RUNTIME_PATH)
    # State:
    main: set       # Full-size real trades (proven performers)
    probation: set  # Paper trades with MAIN params, validating
    rehab: set      # Paper-trade only, exploratory params
    banned: set     # No trades at all
```

- **Loading:** Reads `coins` block from runtime.json. Each coin's `tier` field determines set membership. Unknown coins default to `rehab`.
- **`ensure_listed(coin)`:** If coin not in any tier → add to REHAB, persist.
- **`tier(coin)`:** Returns tier string. Unknown = "rehab".
- **`size_multiplier(coin)`:** Returns 1.0 for all non-banned, 0.0 for banned.
- **`save(coin, new_tier)`:** Atomic write to runtime.json (write tmp, rename).

### TickerDisplay

ANSI terminal ticker — static coin grid at bottom, signal scrollback above.

```python
class TickerDisplay:
    MAX_SCROLLBACK = 20

    __init__(is_tty=None)
    # State:
    _scrollback: list    # Recent signal/trade lines
    _grid_lines: list    # Current coin grid
    _grid_height: int
    _state_path: Path    # data/ticker_display (plain text for remote viewing)
```

- **`signal_line(text)`:** Add to scrollback, redraw.
- **`event_compact(eid, ts, btc_d, coin_events)`:** One-line event summary.
- **`update_grid(coins_data, net_stats=None)`:** Full grid redraw.
  - Columns: COIN, PRICE, Z, Mσ, BZ, TIER, EXP, SESSION
  - Network stats bar: avg tick_ms, tpm, total_ticks, ws_mode, rate_waits, pyth stats.
- **`_write_state_file()`:** Writes plain text frame to `data/ticker_display` for remote viewing.
- **`_redraw()`:** ANSI escape codes (clear screen, reposition).

### MarketSelector

Three-layer market selection: Discovery → Evaluation → Trading.

```python
class MarketSelector:
    __init__(client, ws_cache, runtime, roster, pyth_fetcher, pyth_client, cfg)

    # Layer 1 state:
    all_coin_markets: dict     # {coin: [market_dicts]}
    locked_markets: dict       # {coin: full_market_dict}
    _last_discovery_slot: int  # hour*4 + quarter (0-95)
    _discovery_done: bool

    # Layer 2 state:
    _last_selection_at: float  # monotonic

    # Drain + ban state:
    draining_coins: set
    pending_ban: dict          # coin → (first_seen_mono, miss_count)

    # Staleness tracking:
    _stale_counts: dict        # coin → consecutive stale tick count
    _stale_since: dict         # coin → monotonic first stale timestamp
    _http_fallback_count: int
    _http_fb_last: dict        # coin → last HTTP call monotonic
    _http_fb_data: dict        # coin → cached HTTP result
```

Detailed in [Section 5](#5-market-selection).

---

## 4. Signal Generation

### Event Classification (Type 1/2/3)

Every tick with price movement classifies each coin:

| Type | Condition | Meaning |
|------|-----------|---------|
| 1 | BTC moved, coin flat | Delayed follow expected |
| 2 | BTC moved, coin moved | Normal co-movement (baseline) |
| 3 | BTC flat, coin moved | Pure noise — fade candidate |

**"Moved" thresholds:** Dynamic via `DynamicThresholds` (rolling std × 1.5, floor at 30% of static).

### EMA Feed Functions

All feed functions update `baseline` + `current` layers simultaneously:

**`_ema(old, new, alpha, n)`:**
- If n == 0: return new (seed)
- Else: `alpha × new + (1 - alpha) × old`

**`_ema_var(old_var, old_mean, new_val, alpha, n)`:**
- If n == 0: return 0
- `alpha × (new_val - old_mean)² + (1 - alpha) × old_var`

**`_feed_lag(prof, value, b_alpha, c_alpha)`:**
- value = 1.0 (Type 1) or 0.0 (Type 2)
- Updates `lag_rate_var` BEFORE `lag_rate` (Welford-style)
- Updates `lag_rate` EMA
- Increments `btc_move_seen`

**`_feed_follow(prof, value, b_alpha, c_alpha)`:**
- value = 1.0 (coin followed) or 0.0 (didn't follow)
- Updates `follow_rate` EMA

**`_feed_lag_secs(prof, secs, b_alpha, c_alpha)`:**
- Updates `avg_lag_secs` EMA

**`_feed_directional(prof, btc_delta, value, b_alpha, c_alpha)`:**
- If btc_delta > 0: updates `up_follow_rate`
- If btc_delta < 0: updates `down_follow_rate`

**`_feed_inverse(prof, value, b_alpha, c_alpha)`:**
- value = 1.0 (coin moved opposite) or 0.0
- Updates `inverse_rate_var` BEFORE `inverse_rate`

**`_feed_magnitude(prof, ratio, b_alpha, c_alpha, b_n, c_n)`:**
- Updates `magnitude` EMA

**`_feed_beta(prof, btc_delta, coin_delta, b_alpha, c_alpha)`:**
- Computes `beta = coin_delta / btc_delta`
- Filters: `abs(btc_delta) < 0.001` → skip; `abs(beta) > 10` → skip
- Adds to `beta_sum` and `beta_count` on baseline, current, AND last_hour layers

### Merged Scoring

**`merged_lag_rate(prof, weights, min_events_curr)` → float:**
- Weighted merge of `lag_rate` across all three layers.
- `weights = [w_base, w_last, w_curr]` (default [0.5, 0.3, 0.2])
- Graceful degradation: if current hour has < min_events_curr BTC moves → redistribute weight.
- If only baseline → return `baseline.lag_rate`.
- Formula: `Σ(layer.lag_rate × adjusted_weight)`

**`merged_inverse_rate(prof, weights, min_events_curr)` → float:**
- Same degradation logic as `merged_lag_rate` but for `inverse_rate`.

### Z-Score Computation

**`_logit(x)` → float:**
```
logit(x) = log(x / (1 - x))
```
Clamped to [0.005, 0.995] to avoid ±inf.

**`lag_z_score(prof, weights, min_events_curr, min_var_obs=10)` → float:**
- Returns 0 if `baseline.btc_move_seen < min_var_obs`.
- Picks best recent layer: `current` (if enough events) → `last_hour` → 0.
- Formula: `logit(recent_lag_rate) - logit(baseline_lag_rate)`
- Uses logit transform because Bernoulli data has var=p(1-p) fully determined by mean.

**`inverse_z_score(prof, weights, min_events_curr, min_var_obs=10)` → float:**
- Same logit-space comparison but for `inverse_rate`.
- Returns 0 if `baseline.t1_resolved_seen < min_var_obs`.

### Beta Signals (Diagnostic)

**`beta_anomaly_signal(prof, cfg)` → (score, threshold_met):**
- Returns `(beta_anomaly_score, score >= threshold)`.
- Requires `baseline.beta_count >= 20`, `recent_count >= 3`, `recent_beta > 0`.
- `threshold = cfg["beta_anomaly_threshold"]` (default 0.3).

**`inverse_beta_signal(prof, cfg)` → (score, threshold_met):**
- Returns `(recent_beta, recent_beta < threshold)`.
- Requires `baseline_beta >= 0.3`.
- `threshold = cfg["inverse_beta_threshold"]` (default 0).

### Confidence Classification

**`compute_confidence(prof, tolerance, min_events_curr)` → "HIGH" | "LOW":**
- Collects lag_rate from all available layers.
- If < 2 layers: "LOW".
- `spread = max(layers) - min(layers)`.
- "HIGH" if `spread <= tolerance`, else "LOW".

### Unified Dual-Score Entry System

Three entry paths, evaluated independently per coin per tick:

1. **SPOT** — Pure spot mispricing (Black-Scholes model vs market YES price)
   - `mp.should_trade(min_history, z_threshold=0, min_mispricing, min_vol_obs)` → (should, mispricing, z_score)
   - Direction: `mp.edge_direction()` → "YES" if mispricing > 0, "NO" if < 0.

2. **BTC** — BTC-implied mispricing via `BtcImpliedProfile`
   - `btc_implied.should_trade(min_history, z_threshold=0, min_mispricing)` → (should, mispricing, z_score)
   - Direction: `btc_implied.btc_direction()`
   - **Pre-gate:** `follow_rate >= btc_score_follow_rate_floor` (default 0.3)

3. **COMBINED** — Both SPOT and BTC fire with same direction
   - `edge_z_score = spot_z + btc_z` (additive)
   - Confidence always "HIGH"

**Entry priority order:** Configurable via `runtime.overrides["entry_path_priority"]`, default `["COMBINED", "SPOT", "BTC"]`.

**Independent paths mode** (`independent_entry_paths_enabled=True`, default):
- All three paths evaluated independently.
- Iterated in priority order: first accepted path wins.
- CONFLICT logged when spot_dir ≠ btc_dir (natural veto).

**Legacy mode** (independent_paths=False):
- COMBINED checked first (both agree).
- CONFLICT = both fire but disagree → neither trades.
- SPOT-ONLY if only spot fires.
- BTC-ONLY if only BTC fires (with follow_rate floor gate).

### Signal Flow to Trader

Each candidate calls:
```python
trader.on_signal(
    "EDGE", coin, prof, mispricing, market_data,
    confidence,                    # "HIGH" or "MED"
    btc_price=bp,
    roster_mult=r_mult,            # 0.0 for banned, 1.0 otherwise
    roster_tier=r_tier,
    edge_z_score=z,
    edge_max_size_mult=2.0,
    btc_z_score=btc_z,
    btc_mispricing=btc_misp,
    entry_path=path,               # "SPOT", "BTC", or "COMBINED"
    spot_z_score=spot_z,
    z_velocity=z_vel,
    btc_spot_price=btc_spot,
)
```

The trader applies its own z-threshold gates, cooldowns, execution cost analysis, etc.

### Snapshot Enrichment

Every tick snapshot row is enriched with:
- `entry_candidate`: "1" if any entry path was evaluated
- `entry_path`: which path was tried
- `entry_direction`: "YES" or "NO"
- Execution cost estimates (from `trader.estimate_execution_cost`)
- Pre-gate and exec-gate pass/fail reasons
- All mispricing/z-score values for backtesting

---

## 5. Market Selection

### Layer 1: Discovery

**`MarketSelector.discover(prev_spots, trader, prev_data, force=False)`**

Triggers:
- Not yet discovered
- Force flag (SIGUSR1, pending ban confirmation, widespread staleness)
- New quarter-hour slot AND past startup delay

Process:
1. Calls `client.fetch_hourly_crypto(...)` with `return_all_candidates=True`.
2. ATM selection via `LimitlessClient._atm_select_ticker()` — picks market closest to at-the-money for each coin.
3. Filters by expiry type (hourly vs sub-hourly based on `include_subhourly`).
4. Gap preservation: keeps previous `all_coin_markets` for coins no longer returned.
5. Re-pins coins with open positions to their current market.
6. Rebuilds WS subscriptions from all known slugs.
7. Updates Pyth fetcher addresses + Chainlink feed IDs.
8. **Roster reconciliation:**
   - Missing from live markets → pending ban (need 2+ misses over 60s).
   - Banned but now in live markets → auto-REHAB.
9. Runs Layer 2 immediately.

Returns `(did_discover, hourly_startup)`.

### Layer 2: Evaluation (WS scoring)

**`MarketSelector.evaluate(prev_spots, trader, force=False)`**

Runs every `msel_eval_interval_s` (default 300s).

For each coin with multiple candidate markets:
1. Score each market from WS data:
   ```
   score = msel_depth_weight × (near_depth / max_depth) + msel_atm_weight × (atm_proximity / max_atm)
   ```
   - `atm_proximity = 1 - |bid - 0.50|` (closer to 0.50 = more ATM)
   - `near_depth` from `ws_cache.get_book_quality(slug, depth_band=0.30)`
   - Fallback candidates (no WS data) get -1.0 penalty.
2. **Hysteresis:** Only switch if `new_score > current_score × (1 + msel_hysteresis_pct)`.
3. Pinned coins (open positions) and draining coins are never switched.
4. Rebuilds WS subscriptions if any coin switched.

Default weights from runtime.json:
- `msel_depth_weight` = 1 (from runtime)
- `msel_atm_weight` = 5 (from runtime)
- `msel_hysteresis_pct` = 0.1 (10%)
- `msel_eval_interval_s` = 60

### Layer 3: Build cd (every tick)

**`MarketSelector.build_cd(prev_data)` → dict or None**

For each locked market:
1. **WS first:** `ws_cache.get_best_bid(slug)` — if non-None, use it.
2. **HTTP fallback:** If WS stale, rate-limited per-coin (cooldown from `ws_http_fallback_cooldown_s`). Calls `client.fetch_orderbook(slug)`.
3. **Last resort:** `prev_data[coin]` (stale recycled).

Staleness tracking: logs after first stale tick, then every 12 ticks.

### Expiry / Rollover

**`MarketSelector.check_expiry(trader)` → set of expired coins**

Every tick:
- If market within 60s of expiry AND has open positions → drain mode.
- If no positions → remove lock, add to expired set.
- Draining coins with cleared positions → release.

**Draining coin safety valve** (in main loop):
- If draining coin's YES price < 0.02 or > 0.98 → force-close all positions.

---

## 6. Main Loop

### Initialization

1. Load config + env.
2. Parse args: `--interval`, `--coins`, `--output`, `--json`, `--trade {off,paper,live}`, `--verbose-events`.
3. Create `LimitlessClient` with private key and API key from env.
4. Start WebSocket manager if enabled (3s connection timeout).
5. Initialize `PaperTrader` if trading.
6. Initialize `PythClient` + `PythFetcher` if Pyth enabled.
7. Restore EMA state from `ema_state.json`.
8. Open event CSV and tick snapshot CSV.
9. Create `MarketSelector`.
10. Register signal handlers: SIGINT/SIGTERM → clean shutdown, SIGUSR1 → force market refresh.

### Tick Loop

```
while running and not deadline:
    tick += 1
    ts0 = time.monotonic()

    1. runtime.check() + roster.check()
    2. Apply runtime overrides to trader
    3. Hot-reload poll_interval_ms
    4. Build prev_spots from Pyth data

    5. Market Selection:
       a. Check pending ban / widespread staleness → force refresh
       b. Layer 1: discover() (hourly + startup + forced)
       c. Layer 2: evaluate() (periodic WS scoring)
       d. check_expiry() (every tick)
       e. Signal invalidation for expired coins
       f. Layer 3: build_cd() → cd dict

    6. First tick: seed prev prices, skip processing

    7. Compute deltas:
       - btc_delta = current_bp - prev_bp
       - btc_moved = |btc_delta| >= dynamic_btc_threshold
       - coin_deltas = {coin: current_yes - prev_yes}
       - any_moved = any coin or BTC exceeded threshold

    8. Pyth fair value (EVERY tick, not gated by any_moved):
       - Fetch spot prices from PythFetcher
       - For each coin with spot data:
         a. Compute hours_left from expiry
         b. Draining safety valve check
         c. Lazy-init MispricingProfile
         d. Compute vol EMA (per-coin halflife)
         e. Black-Scholes model_prob = compute_model_prob(spot, strike, hours_left, vol)
         f. Feed mispricing EMA
         g. Feed BtcImpliedProfile (for non-BTC coins)
         h. Build tick snapshot row
         i. Record z-score for z_velocity
         j. Estimate execution cost (WS-cached, ~0 cost)
         k. Unified dual-score entry decision (SPOT/BTC/COMBINED)

    9. Timing diagnostics (per-phase ms)

    10. If no movement:
        - Update idle counters
        - Timeout open signals
        - trader.check_positions(cd, btc_delta, profiles, btc_spot_price)
        - Write change-gated snapshot rows
        - Sleep

    11. If movement:
        - Feed dynamic thresholds
        - Classify each coin (Type 1/2/3)
        - Feed EMA layers per classification
        - Resolve open signals
        - Write CSV rows
        - trader.check_positions()
        - Update prev prices
        - Periodic EMA save (every ema_save_interval_seconds)
        - Update live ticker grid

    12. Sleep until next interval (or WS wake)
```

### Hour Boundary Handling

**`_check_hour_boundary(profiles, current_hour)`:**
- For each coin: if `hour_started != current_hour`:
  - If current has data: `last_hour = copy(current)`
  - Reset: `current = EMALayer()`
  - Update `hour_started = current_hour`
- Preserves last_hour from most recent traded hour (for daily markets with quiet periods).

### Signal Resolution

For each coin with open signals, every tick:

**Type 3 resolution:** If coin moved opposite to original T3 delta:
- `correction_count += 1`, record time.

**Type 1 resolution:**
- **Followed:** coin moved same direction as BTC → `correction_count += 1`, feed follow=1.0, inverse=0.0.
- **Inversed:** coin moved opposite to BTC → feed follow=0.0, inverse=1.0.
- **Timed out:** → `unresolved_count += 1`, feed follow=0.0, inverse=0.0.

### Shutdown

1. Stop PythFetcher.
2. Stop WebSocket manager.
3. Save EMA state.
4. Resolve all open signals as unresolved.
5. Call `trader.summary()`.
6. Close CSVs.
7. Print summary or JSON output.

---

## 7. Data Flow

### Inputs

| Source | Data | Frequency |
|--------|------|-----------|
| `limitless_client.fetch_hourly_crypto()` | Market list (slug, strike, expiry, pyth_address, chainlink_feed_id) | Hourly (Layer 1) |
| `limitless_client.fetch_orderbook(slug)` | HTTP bid/ask | Per-coin fallback when WS stale |
| `ws_manager → OrderbookCache` | Real-time bids via WebSocket | Sub-second |
| `PythFetcher.get_prices()` | Spot prices from Pyth oracle | Every tick (background thread) |
| `runtime.json` | Hot-reloadable config + per-coin params + tier info | stat() every 30s |
| `config.json` | Static config | Startup only |
| `ema_state.json` | Crash recovery — saved EMA profiles | Load at startup |

### Processing Pipeline

```
Spot Prices (Pyth) ──────┐
                         ├─→ Black-Scholes Model Prob ──→ Mispricing EMA ──→ SPOT Score
Market YES Price ────────┘                                                      │
                                                                                ├─→ Entry Decision
BTC Spot + Alt Spot ──→ BtcImpliedProfile ──→ BTC Mispricing EMA ──→ BTC Score ─┘
                                                                                     │
BTC/Alt Price Changes ──→ Type 1/2/3 Classification ──→ EMA Layers ──→ Behavioral Stats (z-scores, beta)
                                                                          │
                                                                          ├─→ follow_rate gate for BTC-only
                                                                          └─→ Evaluator (external) uses for tier promotion
```

### Outputs

| Output | Path | Contents |
|--------|------|----------|
| Event CSV | `data/divergence_YYYY-MM-DD_HHMMSS.csv` | Per-event: timestamp, coin, type, delta, ratio, alert |
| Tick Snapshot CSV | `data/tick_snapshots_YYYY-MM-DD_HHMMSS.csv` | Per-tick per-coin: all mispricing/z-score/execution data |
| EMA State | `data/ema_state.json` | Periodic + shutdown save of all EMA profiles |
| Ticker Display | `data/ticker_display` | Plain text grid for remote viewing |
| Runtime JSON | `data/runtime.json` | CoinRoster.save() writes tier changes |
| Trader signals | → `trader.on_signal()` | Entry candidates passed to trader module |
| Telegram | → `TelegramAlerts` | Startup reports, hourly refreshes |

### Change-Gated Snapshot Writes

Snapshot rows only written when:
1. `(spot, yes_price, no_price)` changed from previous tick, OR
2. `entry_candidate == "1"` (preserves execution verdicts even if prices didn't move)

Flushes every 10 ticks.

### Inter-Process Communication

- **Tracker → Trader:** `trader.on_signal()` (in-process call), `trader.check_positions()` (every tick).
- **Tracker → Evaluator:** Evaluator reads snapshot CSVs + runtime.json externally.
- **Runtime hotreload:** stat() on runtime.json every 30s, reload on mtime change.
- **SIGUSR1:** Forces market rediscovery.

---

## 8. V2 Mapping

### Signal Logic → `ControllerBase.update_processed_data()`

The entire Pyth fair-value block (lines ~2500-2900) maps to `update_processed_data()`:
- Fetch Pyth spot prices → `self.market_data_provider` or candles
- Black-Scholes model prob computation → remains custom logic in processed_data
- MispricingProfile.feed() / BtcImpliedProfile.feed() → build mispricing EMAs in `self.processed_data`
- z-score computation → `self.processed_data["spot_z"]`, `self.processed_data["btc_z"]`
- Z-velocity → `self.processed_data["z_velocity"]`

The Type 1/2/3 classification + EMA behavioral stats also go here:
- `self.processed_data["profiles"][coin]` — all EMALayer data
- lag_z_score, inverse_z_score, beta signals → diagnostic metrics in processed_data

### Market Filtering → Controller Config or `update_processed_data()`

`MarketSelector` maps to:
- **Layer 1 (discovery):** `ControllerConfigBase.update_markets()` — register trading pairs with strategy at startup/hourly.
- **Layer 2 (evaluation):** Custom logic in `update_processed_data()` — score markets, update `self.processed_data["locked_markets"]`.
- **Layer 3 (build_cd):** `market_data_provider.get_price()` replaces WS cache reads.
- **CoinRoster:** Controller config (static) + processed_data (dynamic tier changes).

### Trade Decisions → `ControllerBase.determine_executor_actions()`

The unified dual-score entry system maps here:
```python
def determine_executor_actions(self) -> List[ExecutorAction]:
    actions = []
    for coin in self.processed_data["coins"]:
        candidates = self._emit_path_candidates(coin)  # SPOT/BTC/COMBINED
        for cand in candidates:
            if self._passes_gates(coin, cand):
                actions.append(CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=PositionExecutorConfig(
                        trading_pair=f"{coin}-USDC",
                        side=TradeType.BUY if cand["direction"] == "YES" else TradeType.SELL,
                        amount=self._compute_size(coin, cand),
                        triple_barrier_config=TripleBarrierConfig(
                            stop_loss=Decimal(str(edge_stop_loss_pct)),
                            take_profit=self._compute_tp(coin),
                            time_limit=int(self._compute_timeout(coin)),
                            trailing_stop=TrailingStop(
                                activation_price=Decimal(str(trailing_stop_trigger_pct)),
                                trailing_delta=Decimal(str(trailing_stop_distance_pct)),
                            ),
                        ),
                    ),
                ))
                break  # First accepted path wins
    return actions
```

### Order Placement → Executor Terms

| Current (tracker/trader) | V2 Equivalent |
|--------------------------|---------------|
| `trader.on_signal()` → `_open_position()` | `CreateExecutorAction` with `PositionExecutorConfig` |
| `trader._close_position()` | `StopExecutorAction` or PositionExecutor's triple barrier auto-close |
| Stop-loss (confirmed over N ticks) | `TripleBarrierConfig.stop_loss` + time-based confirmation via custom executor |
| Trailing stop (arm + trail) | `TripleBarrierConfig.trailing_stop` (native in PositionExecutor) |
| Timeout + extensions | `TripleBarrierConfig.time_limit` + custom extension logic in controller |
| Scale-in | Multiple `CreateExecutorAction`s with decaying size |
| BTC reversal exit | Custom logic in `determine_executor_actions()` → `StopExecutorAction` |

### State That Needs Migration

| Current State | V2 Location |
|---------------|-------------|
| `CoinProfile` (all EMA layers, TypeStats) | `controller.processed_data` |
| `MispricingProfile` / `BtcImpliedProfile` | `controller.processed_data` |
| `DynamicThresholds` | `controller.processed_data` or eliminated (V2 connectors handle this differently) |
| `MarketSelector` locked_markets | `controller.processed_data` + `update_markets()` |
| `CoinRoster` | Controller config (updatable) |
| EMA state persistence | V2 has DB persistence via `MarketsRecorder` — can store custom JSON |
| Tick snapshot CSV | Eliminated — V2 uses DB-backed executor performance reports |

### External Dependencies Needed

| Module | Purpose |
|--------|---------|
| `fair_value.py` | `MispricingProfile`, `BtcImpliedProfile`, `compute_model_prob`, `halflife_to_alpha`, `secs_to_ticks`, `compute_hourly_volatility`, `compute_edge` |
| `trader.py` | `PaperTrader` — position management, execution cost estimation, exits |
| `limitless_client.py` | `LimitlessClient` — API calls, ATM selection, orderbook |
| `ws_manager.py` | `OrderbookCache`, `LimitlessWSManager` — WebSocket streaming |
| `pyth_client.py` | `PythClient`, `PythFetcher` — Pyth oracle spot prices |
| `alerts.py` | `TelegramAlerts` — notifications |

---

## Appendix: Key Formulas

### Black-Scholes Model Probability
```
model_prob = compute_model_prob(spot, strike, hours_left, vol)
```
(Defined in fair_value.py — standard BS for binary options)

### Mispricing
```
mispricing = model_prob - market_yes_price
```
Positive = market underpriced (buy YES), negative = overpriced (buy NO).

### Z-Score (per-tick)
```
z = |current_mispricing - mispricing_ema| / max(mispricing_std, 0.001)
```

### Lag Z-Score (logit-space)
```
lag_z = logit(recent_lag_rate) - logit(baseline_lag_rate)
logit(x) = log(x / (1-x))  # clamped [0.005, 0.995]
```

### EMA Alpha from Halflife
```
α = 1 - exp(-ln(2) × interval / halflife)
```

### Dynamic Threshold
```
threshold = max(rolling_std(deltas, window=60) × 1.5, static_value × 0.3)
```

### Market Selection Score
```
score = depth_weight × (near_depth / max_depth) + atm_weight × (atm_proximity / max_atm)
atm_proximity = 1 - |bid - 0.50|
```

### Beta
```
beta = coin_delta / btc_delta  (filtered: |btc_delta| >= 0.001, |beta| <= 10)
beta_anomaly = max(0, 1 - recent_beta / baseline_beta)
```

### Combined Z-Score
```
combined_z = spot_z + btc_z  (additive when both paths agree on direction)
```
