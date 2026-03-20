# 03 — Parameter Tuning Layer (Backtester + Evaluator)

Full code extraction from `backtester.py` (2554 lines) and `evaluator.py` (2805 lines).
Meta-eval skipped (not needed for controller build).

---

## Architecture Overview

```
Cold Eval (every 30min, full depth):
  evaluator.py --cold
    → Backtester.optimize_all()           # per-coin trade-based Optuna
    → Backtester.optimize_from_snapshots() # per-coin snapshot replay Optuna
    → Backtester.optimize_unified()       # V2: hybrid trade+snapshot objective
    → Recommender._eval_roster_full()     # tier promotions/demotions
    → apply_runtime_changes()             # write to runtime.json

Hot Eval (every 10min, quick depth):
  evaluator.py --apply --all --eval-depth quick
    → Recommender._rehab_pre_pass()       # REHAB cleanup
    → Recommender._eval_alphas()          # REHAB-only score-driven drift ("wobble")
    → _hot_eval_v2_stage2()              # V2: cold-anchor convergence
    → apply_runtime_changes()
```

---

## 1. Backtester Class

### Constructor
```python
class Backtester:
    def __init__(self, data_dir: str|Path, lookback_hours: int = 2, n_trials: int = None):
        self.data_dir = Path(data_dir)
        self.lookback_hours = lookback_hours
        self.n_trials = n_trials or config.json["optuna"]["n_trials"]
        self.trades = self._load_recent_trades()
```

### Data Loading

#### `_load_recent_trades() -> list[dict]`
- Scans `trades_*.csv` in `data/` + `data/archive/`
- Files filtered by filename date `_YYYY-MM-DD_HHMMSS.` regex
- **Data-relative cutoff**: anchor to latest trade timestamp, NOT wall clock
- Numeric fields parsed: `pnl, size, entry_price, exit_price, hold_secs, stop_timeout, entry_z_score, entry_vol, entry_spread, entry_mispricing, entry_mispricing_std, entry_decay_exp, exit_btc_delta, peak_pnl, best_entry_price, best_exit_price, entry_btc_z_score, entry_btc_mispricing, entry_spot_z_score, entry_exec_cost, entry_edge_raw, entry_edge_ratio`
- String fields: `exit_reason, signal_type, direction, coin, entry_path`

#### `_load_snapshots(coin, lookback_hours=None) -> list[dict]`
- Scans `tick_snapshots_*.csv` in `data/` + `data/archive/`
- Filters to specific coin (case-insensitive)
- Lookback from `runtime.json["snapshot_lookback_hours"]` (default 2)
- Numeric fields: `spot, yes_price, no_price, mispricing, mispricing_std, z_score, vol, model_prob, strike, hours_left, max_spread, btc_spot, btc_delta, coin_delta, lag_z, inv_z, lag_rate, btc_mispricing, btc_mispricing_std, btc_z_score, implied_spot, residual, entry_size_usd, entry_price_ref, depth_yes_usd, depth_no_usd, depth_relevant_usd, min_book_depth_req_usd, buy_slip_est, sell_slip_est, total_exec_cost_est, edge_raw_est, edge_after_cost_est, edge_slip_ratio_est`
- Pre-parses `_ts_epoch` for fast per-trial datetime avoidance

#### `_glob_with_archive(data_dir, pattern, max_age_hours) -> list[Path]`
- Glob in data_dir + archive subdir
- Include file if filename date OR mtime falls within lookback window
- Handles files written to continuously past their creation timestamp

### Scoring

#### `_score(trades) -> float`
- `len(trades) < 5` → `-inf` (hard floor)
- Otherwise: `sum(t["pnl"] for t in trades)` — pure PnL

### Search Space

#### `_build_search_space_info() -> dict`
Returns:
```python
{
    "coins": sorted(set of coins),
    "signals": sorted(set of signal_types),
    "vol_pct": fraction of trades with entry_vol != 0,
    "spread_pct": fraction with entry_spread != 0,
    "mispricing_pct": fraction with entry_mispricing != 0,
    "has_z_data": bool,
}
```

### Parameter Space

All bounds come from `runtime.json["param_space"]`. Each entry has `low`, `high`, optional `sensitivity`, `loosen`, `step`, `data_cap`.

**Per-coin Optuna dimensions** (prefixed with coin name in trial):
| Trial Key | Runtime Key | Type |
|-----------|-------------|------|
| `z_{coin}` | `{COIN}_edge_z_threshold` | float |
| `cd_{coin}` | `{COIN}_scale_in_cooldown_seconds` | int (with step) |
| `tm_{coin}` | `{COIN}_max_timeout_multiplier` | float |
| `de_{coin}` | `{COIN}_edge_decay_exponent` | float |
| `tt_{coin}` | `{COIN}_trailing_stop_trigger_pct` | float |
| `td_{coin}` | `{COIN}_trailing_stop_distance_pct` | float |
| `btc_rev_{coin}` | `{COIN}_btc_reversal_multiplier` | float |
| `esq_{coin}` | `{COIN}_tp_squeeze_factor` | float |
| `roi_{coin}` | `{COIN}_tp_min_roi` | float |
| `sl_{coin}` | `{COIN}_edge_stop_loss_pct` | float |
| `btc_z_{coin}` | `{COIN}_btc_z_threshold` | float |
| `cz_{coin}` | `{COIN}_combined_z_threshold` | float |
| `zmax_{coin}` | `{COIN}_edge_z_max` | float |
| `btc_zmax_{coin}` | `{COIN}_btc_z_max` | float |
| `czmax_{coin}` | `{COIN}_combined_z_max` | float |
| `meas_{coin}` | `{COIN}_min_edge_profit_ratio` | float (with step) |
| `ers_{coin}` | `{COIN}_edge_reject_sigma` | float |
| `vl_{coin}` | `{COIN}_entry_vol_range[0]` | float (if vol data >30%) |
| `vh_{coin}` | `{COIN}_entry_vol_range[1]` | float (if vol data >30%) |

**Not Optuna-tuned (global runtime values passed through):**
- `min_edge_entry_price` (default 0.15)
- `max_edge_mispricing` (default 0.99)
- `min_mispricing` (default 0.005)
- `max_edge_entry_price` (default 0.93 — fixed)

### Optimization Methods

#### `optimize_all(current_runtime=None, snapshot_seed=None) -> dict`
- **Trade-based Optuna** — runs per-coin in parallel via ProcessPoolExecutor
- Flattens `runtime.json["coins"]` block to `{COIN}_{key}` format
- Each coin gets independent study with TPE sampler (multivariate=True)
- Pruner disabled (too aggressive with low trade counts)
- First trial seeded with current runtime values (enqueue_trial)
- Optional snapshot_seed for cross-seeding

**Per-coin study flow** (`_run_single_coin_study`):
1. Build study with TPE sampler, 20 startup trials
2. Enqueue baseline (current params) + optional snapshot seed
3. Run n_trials
4. Extract best params, compute improvement %, param importance

**Objective function** (`_make_objective` closure):

**Phase 1 — Filter trades by candidate params:**
- Per-path z-score gating:
  - COMBINED: `spot_z + btc_z >= combined_z_threshold`
  - BTC: `btc_z >= btc_z_threshold`
  - SPOT: `spot_z >= z_threshold`
- Z-score max gates (upper tunnel): reject if z exceeds per-coin max
  - COMBINED checks: spot_z vs z_max, btc_z vs btc_z_max, sum vs combined_z_max
- Entry vol range (EDGE only, if vol data >30%)
- Min mispricing gate (global, EDGE only)
- Entry price floor (min_edge_entry_price) and ceiling (0.93)
- Edge/profit ratio: `edge / max_profit >= min_edge_profit_ratio`
  - `edge = |entry_mispricing|`, `max_profit = 1.0 - fill_price`
- Stop-room/survivability: `execution_cost_proxy < stop_room` AND `stop_room / execution_cost_proxy >= min_stop_room_ratio`
- Mispricing-std reject: `|mispricing| > min(sigma * std, max_edge_mispricing)` → reject

**Phase 1b — Scale-in cooldown:**
- Per-coin EDGE trades must be `cd` seconds apart
- Cooldown measured from previous EDGE entry for same coin

**Phase 1c — Streak cooldown:**
- Fixed: 3 consecutive losses → 15 min pause per coin
- Not Optuna-tuned (optimizer always picks max/no-pause)

**Phase 2 — Behavioral proxy adjustments (modify PnL of surviving trades):**

*Decay exponent proxy* (timeout exits with pnl < 0):
```
orig_squeeze = (hold / stop_timeout) ^ 2.0
new_squeeze = (hold / stop_timeout) ^ coin_decay_exp
reduction = 1.0 - |new_squeeze - orig_squeeze|
adjusted_pnl = pnl * max(0, min(1, reduction))
```

*Timeout multiplier proxy* (timeout exits with pnl < 0):
```
scale = min(coin_timeout_mult / default_timeout_mult, 1.0)
adjusted_pnl *= scale
```

*BTC reversal proxy* (btc_reversal exits with pnl < 0):
```
scale = min(coin_btc_rev_mult / 2.0, 2.0)
adjusted_pnl = pnl * scale
```

*Take-profit proxy* (take_profit exits with pnl > 0):
```
age = min(hold / stop_timeout, 1.0)
orig_squeeze_factor = max(1 - age^2 * default_esq, 0)
new_squeeze_factor = max(1 - age^2 * coin_esq, 0)
orig_min_profit = size * default_roi * orig_squeeze_factor
new_min_profit = size * coin_roi * new_squeeze_factor
scaled_pnl = pnl * (new_min_profit / orig_min_profit)
capped at peak_pnl
```

*Trailing stop proxy* (any exit with peak_pnl > 0):
```
captured = peak_pnl * (1 - coin_trailing_distance)
if peak_pnl >= size * coin_trailing_trigger AND captured > current_pnl:
    adjusted_pnl = captured
```

**Phase 3 — Score:**
- `_score(adjusted_trades)` → sum(pnl) with <5 trade floor

#### `optimize_from_snapshots(coin, snapshot_seed=None, current_runtime=None) -> dict`
- **Snapshot replay Optuna** — simulates trades from tick-by-tick snapshot data
- Used when trade data is insufficient
- Two-stage flow: trade baseline → snapshot refinement seeded from trade

**Snapshot objective** (`_make_snapshot_objective` closure):

Simulates full position lifecycle tick-by-tick:

**Entry logic (per tick):**
1. Check `edge_count < max_scale_in` (from config)
2. Check cooldown from last EDGE entry
3. Check vol range, spread, hours_left > freeze
4. Build candidates: SPOT, BTC, COMBINED (independent or priority-based)
5. Per-path z-score gating (same as trade-based)
6. Entry price floor/ceiling check
7. Max payout ceiling check (`1 - entry_price >= min_payout_ceiling`)
8. Execution context realism gates (path/direction match from snapshot)
9. Depth check (`depth_relevant_usd >= min_book_depth_req_usd`)
10. Execution cost proxy: real orderbook > spread-based > 2x spread fallback
11. Edge/cost ratio gate
12. Stop-room/survivability gate
13. Place entry: `entry_size = base_size * scale_in_decay^edge_count`

**Exit priority (checked per tick per open position):**
1. **Market expiry**: `hours_left < market_close_minutes/60`
2. **BTC reversal**: `|btc_spot - btc_entry| > min_btc_delta * btc_rev_mult` (after grace period, direction-aware)
3. **Stop loss**: `unrealized_pnl < -(base_size * stop_loss_pct)` with confirmation (tick count AND/OR time-based)
4. **Take profit**: `unrealized_pnl >= base_size * tp_min_roi * squeeze_factor` where `squeeze_factor = max(1 - age^decay_exp * tp_squeeze, 0)`
5. **Trailing stop**: arm at `unrealized_pnl >= base_size * trailing_trigger`, fire when `peak_pnl - unrealized_pnl >= peak_pnl * trailing_distance`
6. **Adaptive timeout**: extend if profitable (`extensions < max_timeout_extensions`, `new_timeout = timeout * timeout_ext_factor`, capped at `2 * max_timeout`)

**Force-close** remaining positions at last tick as timeout.

#### `optimize_unified(coin, real_weight=2.0, sim_weight=1.0, current_runtime=None) -> dict`
- **Cold Eval V2** — single Optuna study with hybrid objective
- Joins real trades to snapshot ticks by timestamp (two-pointer O(n+m), max 5s gap)
- Score = `real_avg_pnl * real_weight + sim_avg_pnl * sim_weight`
- `real_weight` default 2.0, `sim_weight` default 1.0 (real trades count double)
- Sim component reuses snapshot replay logic
- Real component filters actual trades by candidate params, uses real PnL as ground truth

### Optimization Output Format
```python
{
    "optimal_params": {"{COIN}_{param}": value, ...},  # delta-only: changes from current
    "best_params": {"z_{coin}": ..., ...},              # raw trial keys for seeding
    "study_stats": {
        "n_trials": int,
        "best_score": float,
        "best_pnl": float,
        "baseline_score": float,
        "improvement_pct": float,
        "best_edge_reject_sigma": float,
        # V2 extras:
        "real_trade_count": int, "real_pnl": float,
        "sim_trade_count": int, "sim_pnl": float,
        "join_rate": "matched/total",
    },
    "param_importance": {"param": importance_score, ...},  # top 10
    "trade_count": int,
    "test_trade_count": int,
    "filter_kills": {"z": n, "btc_z": n, "vol": n, ...},
    "source": "trades" | "snapshots" | "unified_v2",
}
```

---

## 2. Evaluator

### Trade Loading

#### `load_trades(csv_path, since=None) -> list[dict]`
- Single CSV reader with timestamp filter
- Numeric fields: pnl, size, entry_price, exit_price, hold_secs, stop_timeout, entry_z_score, entry_vol, entry_spread, entry_decay_exp, entry_correction_rate, entry_lag_rate, entry_lag_z_score, entry_btc_z_score, entry_btc_mispricing, entry_exec_cost, entry_edge_raw, entry_edge_ratio
- String fields: entry_path, signal_type, direction

#### `find_trade_csvs(lookback_hours=None) -> list[Path]`
- Uses `_glob_with_archive` (wall-clock + mtime fallback)
- Sorted by mtime descending

### TradeAnalysis Class
```python
class TradeAnalysis:
    def __init__(self, trades):
        self.trades = trades
        self.by_coin = defaultdict(list)
        self.by_signal = defaultdict(list)
        self.by_exit = defaultdict(list)
        self.by_coin_signal = defaultdict(list)  # (coin, signal_type) -> trades
        self.by_coin_tier = defaultdict(list)    # (coin, tier) -> trades

    def _stats(trades) -> dict:
        # count, wins, losses, total_pnl, win_rate, avg_pnl, avg_hold, profit_factor

    def overall() -> dict
    def per_coin() -> dict
    def per_signal() -> dict
    def per_exit() -> dict
    def per_coin_signal() -> dict
```

### Recommender Class

```python
class Recommender:
    def __init__(self, analysis, min_trades=3, trade_mode="paper"):
        self.recommendations = []
        self.runtime_changes = {}       # global auto-apply
        self.coin_changes = {}          # per-coin nested changes
        self.coin_optuna_stats = {}     # per-coin Optuna results
        self.coin_cold_anchor_params = {}  # Stage 1 cold anchors
        self.config_proposals = {}      # requires confirmation
        self._cutoff_ts = 24h ago       # heuristic tuning window
        self._cutoff_1h_ts = 1h ago
        self.coin_baselines = self._compute_coin_baselines()
```

### Roster System (3 Tiers)

```
MAIN     → real trades, Optuna-tuned params, untouched between cold evals
PROBATION → real trades, Optuna params, proving ground (time-limited)
REHAB    → paper trades, params loosened by hot eval wobble, collecting data
BANNED   → excluded from all trading and evaluation
```

**Tier transitions:**

| From | To | Condition |
|------|----|-----------|
| REHAB → PROBATION | Optuna `best_pnl > rehab_promote_min_pnl` (default 30) |
| PROBATION → MAIN | `trades >= probation_min_trades` AND `total_pnl >= probation_promote_min_pnl` (default 5) |
| PROBATION → REHAB | `trades >= probation_min_trades` AND `total_pnl <= 0` |
| PROBATION → REHAB | `probation_hours >= 1h` AND `hourly_trades < probation_min_hourly_trades` |
| MAIN → REHAB | `trades >= demote_min_trades` AND `total_pnl <= 0` (over `demotion_lookback_h`, default 24) |

Roster config loaded from `config.json["divergence"]["roster"]` with runtime.json overrides.

### Cold Eval (`_eval_roster_full`)

**Pipeline per coin (non-banned):**

**V1 (default — `cold_eval_version: "v1"`):**
1. Trade-based Optuna: `Backtester.optimize_all()` (24h lookback)
2. Snapshot Optuna: `Backtester.optimize_from_snapshots()` (2h lookback), seeded with trade baseline
3. Validation: `snap_pnl_extrapolated >= trade_pnl * snap_validation_ratio` (default 0.80)
4. Source selection (`optuna_stage_selection`):
   - `"stage2"` (default): prefer snapshots, fallback trades
   - `"stage1"`: prefer trades, fallback snapshots
   - `"higher_profit"`: whichever has higher best_pnl
5. Cross-pollination: snapshot gets trade's `min_edge_profit_ratio`, trades get snapshot's `tp_min_roi`

**V2 (`cold_eval_version: "v2"`):**
1. Single unified Optuna: `Backtester.optimize_unified()` with hybrid trade+snapshot objective
2. No validation step needed (single study handles both)

**After Optuna — tier promotion/demotion logic runs.**

### Hot Eval (`_eval_alphas`) — REHAB Only

**MAIN and PROBATION coins are NOT touched by hot eval** — they're Optuna-only (cold eval). Hot eval drift on those tiers created a moving-target that prevented Optuna convergence.

**REHAB "wobble" cycle:**

For each param in `param_space`:
```python
loosen_target = floor if loosen=="down" else ceiling
tighten_target = ceiling if loosen=="down" else floor
elapsed = min(elapsed_hours_since_last_eval, 1.0)

if score > 0:    # winning: hold
    new_val = old_val
elif score < 0:  # losing: tighten
    progress = min(1.0, rehab_drift * sensitivity * |score| * elapsed)
    new_val = old_val + (tighten_target - old_val) * progress
else:             # no data: loosen
    progress = min(1.0, rehab_drift * sensitivity * elapsed)
    new_val = old_val + (loosen_target - old_val) * progress
```

**Score = `_coin_performance_score(coin_trades_1h)`:**
```python
# Composite [-1, +1], weighted:
score = (0.35 * wr_score +      # win_rate: (wr - 0.5) * 2
         0.25 * pnl_score +     # normalized per-trade PnL
         0.20 * rev_score +     # BTC reversal rate (15% = neutral)
         0.10 * to_score +      # timeout rate (20% = neutral)
         0.10 * edge_score)     # EDGE-specific win rate
```

**Additional REHAB interventions:**
- **Low-trade** (<5 trades/1h): `rehab_default_pull_mult` (default 2x) pull toward defaults
- **Near-bounds** (within 5% of floor/ceiling): 25%/h pull toward default
- **V2 anchored coins**: skip wobble entirely if v2 live mode + fresh cold anchor with positive expected gain

**REHAB pre-pass** (`_rehab_pre_pass`):
- Delete legacy keys: `tp_squeeze_factor, sl_squeeze_factor, btc_rev_squeeze_factor, trailing_squeeze_factor`
- Zero gate params: `min_entry_vol`
- Optional emergency reset (disabled by default): if any param hits 85% toward restrictive end, snap ALL to defaults

### Hot Eval V2 Stage System

**Stage 0** (observability only):
- Tier counts, 1h/6h window metrics per tier
- Compact log line for monitoring

**Stage 1** (`_maybe_export_hot_eval_v2_stage1`):
- Cold eval exports anchor state to `hot_eval_v2_state.json`
- Per-coin: target params, confidence, expected gain, timestamp
- Merges with existing state (parallel cold eval processes)
- Confidence formula: `min(1, trade_count/20) + 0.2 if profitable + 0.15 if trades source`

**Stage 2** (`_hot_eval_v2_stage2`):
- Hot eval converges toward cold anchors incrementally
- Per-eval cap: `1/N` of remaining distance (N = cold_interval / hot_interval)
- Step = `base_step * confidence * gain_gap`
- `gain_gap = max(0, cold_expected_gain - hot_actual_gain)`
- Modes: `shadow` (log only) or `live` (apply writes)

### Cold Eval Modes
- `"apply"` (default): cold eval writes params directly to runtime.json
- `"anchor_only"`: cold eval exports anchors for v2 stage2, does NOT write params directly

### Gate Loosening

When ≤2 trades fire, automatically loosen entry gates:

| Key | Delta | Floor |
|-----|-------|-------|
| `edge_z_threshold` | -0.15 | 0.5 |
| `edge_min_vol_obs_secs` | -15 | 5 |
| `edge_min_history_secs` | -10 | 5 |
| `btc_z_threshold` | -0.15 | 0.3 |
| `min_events_current_hour` | -1 | 1 |
| `confidence_tolerance` | +0.05 | 0.5 |
| `alert_std_threshold` | -0.2 | 1.0 |

### Pinned Keys

`runtime.json["_pinned"]` = list of keys that evaluator/backtester NEVER overwrite.
Checked at both global and per-coin level (`{COIN}_{key}`).

### Report-only Analysis (no param writes)

- `_eval_coins()` — per-coin win rate, PnL (MAIN tier only)
- `_eval_signals()` — per signal type performance
- `_eval_direction()` — YES vs NO bias detection
- `_eval_per_coin_signals()` — coin+signal combo failures
- `_eval_exits()` — exit reason effectiveness
- `_eval_sizing()` — max single loss % of capital
- `_eval_timeouts()` — timeout hold time vs average
- `_eval_hold_time()` — winner vs loser hold time comparison
- `_eval_edge()` — EDGE signal performance logging

### Applying Changes

#### `apply_runtime_changes(changes, trade_mode, coin_changes)`
- Writes to `runtime.json` via temp file + rename
- Respects `_pinned` keys
- Handles `__DELETE__` sentinel for key removal
- Per-coin changes go into nested `coins` block
- Paper mode blocks `paused` and `trading_enabled` changes

#### `apply_config_changes(changes)`
- Writes to `config.json["divergence"]` section
- Respects `_pinned` keys in config

### Evaluation Functions (report-only)

These produce recommendations but NO param writes:

#### `_eval_coins()` — MAIN tier trades only
- Win rate < 25% + 5+ trades → WARN "severely underperforming"
- Win rate < 35% → WARN
- Win rate ≥ 60% + PF ≥ 1.5 → OK "strong performer"
- REHAB coins: data coverage report (trades, distinct hours, signal types)

#### `_baseline_threshold(coin, metric, fallback, direction, sensitivity=0.6)`
- Adaptive thresholds based on coin's historical baseline
- `direction="below"`: threshold = `baseline * (1 - sensitivity)`, floored at `fallback * 0.5`
- `direction="above"`: threshold = `baseline + sensitivity * (100 - baseline)`, capped at `fallback * 1.5`

### Alerts

```python
from alerts import send_status, send_eval_status
```
- `send_status(text)` — Telegram notification
- `send_eval_status(eval_type, analysis, recommender)` — formatted eval summary

---

## 3. Config Keys Reference

### config.json["divergence"]
- `capital` — base capital for sizing (default 1000)
- `risk_per_trade` — fraction per position (default 0.02)
- `market_duration_seconds` — market duration (default 3600)
- `stop_fallback_pct` — base timeout fraction (default 0.05 → 180s)
- `max_spread` — max spread for entry (default 0.15)
- `min_payout_ceiling` — min payout room (default 0.02)
- `market_close_minutes` — close before expiry (default 2)
- `market_freeze_minutes` — no entries before expiry (default 5)
- `min_btc_delta` — min BTC move for reversal exit
- `stop_loss_grace_secs` — grace before stop loss active (default 20)
- `max_scale_in_entries` — max concurrent EDGE positions per coin (default 3)
- `scale_in_size_decay` — size multiplier per scale-in (default 0.7)
- `stop_loss_confirm_required` — ticks needed (default 2)
- `stop_loss_confirm_secs` — seconds needed (default 0)
- `max_timeout_extensions` — max timeout extensions (default 2)
- `timeout_extension_factor` — extension multiplier (default 1.5)

### config.json["divergence"]["roster"]
- `promote_min_trades` — min trades for REHAB→PROBATION Optuna (default 10)
- `probation_min_trades` — min trades for PROBATION→MAIN (default 10)
- `probation_min_hourly_trades` — min per hour in probation (default 2)
- `probation_zero_trade_timeout_h` — timeout to demote if no trades (default 1)
- `demote_min_trades` — min trades for MAIN→REHAB demotion (default 10)
- `demotion_lookback_h` — lookback for demotion (default 24)
- `rehab_promote_min_pnl` — Optuna PnL threshold for REHAB→PROBATION (default 30)
- `probation_promote_min_pnl` — actual PnL threshold for PROBATION→MAIN (default 5)

### config.json["optuna"]
- `n_trials` — trials per Optuna study (required, no hardcoded fallback)

### runtime.json top-level
- `snapshot_lookback_hours` — snapshot replay window (default 2)
- `trade_lookback_hours` — trade data window (default 24)
- `cold_eval_interval_minutes` — cold eval frequency (default 30)
- `cold_eval_version` — "v1" (two-stage) or "v2" (unified)
- `cold_eval_mode` — "apply" (write params) or "anchor_only" (v2 anchors only)
- `optuna_stage_selection` — "stage2" | "stage1" | "higher_profit"
- `snap_validation_ratio` — minimum snap/trade PnL ratio (default 0.80)
- `v2_real_weight` — unified objective real trade weight (default 2.0)
- `v2_sim_weight` — unified objective sim weight (default 1.0)
- `independent_entry_paths_enabled` — allow SPOT/BTC/COMBINED independently (default true)
- `entry_path_priority` — ordered list ["COMBINED", "SPOT", "BTC"]
- `emergency_reset_enabled` — REHAB emergency reset (default false)
- `_pinned` — list of keys never overwritten by evaluator

### runtime.json["hot_eval"]
- `hot_eval_interval_minutes` — hot eval frequency (default 10)
- `rehab_drift_per_hour` — base wobble rate (default 0.20)
- `rehab_low_trade_threshold` — trades/1h below which extra intervention (default 5)
- `rehab_default_pull_mult` — pull strength toward defaults (default 2.0)
- `rehab_near_bound_buffer` — fraction of range near bounds (default 0.05)
- `rehab_near_bound_pull_rate` — pull rate when near bounds (default 0.25)
- `hot_eval_v2_enabled` — enable v2 stage system
- `hot_eval_v2_mode` — "shadow" (log only) or "live" (apply)
- `hot_eval_v2_log_decisions` — log detailed delta info
- `hot_eval_v2_live_mode` — legacy flag (→ mode="live")
- `hot_eval_v2_shadow_mode` — legacy flag (→ mode="shadow")

---

## 4. V2 Hummingbot Mapping

| Limitless Component | V2 Component | Notes |
|---|---|---|
| Backtester + Evaluator | **External tooling** | NOT part of live controller. Runs as separate process (cron/systemd). |
| `param_space` bounds | Controller config | Could become `ControllerConfigBase` fields with validation |
| Optuna optimal params | Controller config hot-reload | Controller reads runtime.json, updates `processed_data` |
| Roster tiers | Controller market selection | `update_processed_data()` filters coins by tier |
| Hot eval wobble | External (keep as-is) | No V2 equivalent for online param drift |
| Cold eval anchor export | External (keep as-is) | `hot_eval_v2_state.json` is external state |
| Gate loosening | Controller config update | Could be controller method or external |

**Key insight**: The entire param tuning layer stays OUTSIDE Hummingbot. It reads/writes `runtime.json` which the controller reads on each tick. No refactoring needed — just ensure the controller loads `runtime.json` in `update_processed_data()`.
