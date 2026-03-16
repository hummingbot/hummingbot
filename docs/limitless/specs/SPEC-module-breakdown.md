# SPEC: Module Breakdown — BinaryOptionsController

Complete module-by-module build guide. Each module is independently buildable.
Sub-agents: read the referenced system-map sections, V2-REFERENCE.md, and this spec for your module.

## File Structure

```
controllers/generic/binary_options/
├── __init__.py
├── controller.py            # Thin orchestrator
├── config.py                # All config + runtime.json bridge
├── fair_value.py            # B-S model + mispricing profiles (straight port)
├── signal_engine.py         # EMA layers, type classification, scoring, gates
├── market_manager.py        # Discovery, ATM selection, expiry, roster
├── action_router.py         # Decision tree → 14 execution paths
├── exit_manager.py          # 7-priority exit cascade
├── position_tracker.py      # Multi-coin state, cooldowns, circuit breaker
├── pyth_feed.py             # Spot price source via connector
├── order_types.py           # EXISTS — already built
└── tests/
    ├── test_fair_value.py
    ├── test_signal_engine.py
    ├── test_action_router.py
    ├── test_exit_manager.py
    └── test_market_manager.py
```

---

## Module 1: fair_value.py

**Source:** `system-map/04-data-layer.md` § 2 (Fair Value Model)
**Port type:** Near-direct copy from `limitless-recon/scripts/fair_value.py`

### Contains
- `compute_model_prob(spot, strike, hours_to_expiry, hourly_vol) → float` — B-S binary option: Φ(d2)
- `compute_edge(model_prob, market_yes) → float` — model_prob - market_yes
- `compute_hourly_volatility(deltas, interval_secs) → float` — sample std × √(ticks/hour)
- `halflife_to_alpha(halflife_secs, interval_secs) → float` — α = 1 - exp(-ln(2) × interval/halflife)
- `secs_to_ticks(secs, interval_secs) → int`
- `class MispricingProfile` — per-coin spot mispricing tracker (EMA + Welford variance + z-score + z-velocity)
- `class BtcImpliedProfile` — per-coin BTC-implied mispricing tracker (beta × btc_return - coin_return)

### Changes from original
- None. This is pure math, no dependencies on limitless-recon infrastructure.
- Remove `import time` usage — controller provides timestamps.

### Tests
- `compute_model_prob`: known B-S values, edge cases (vol=0, spot=strike, near-expiry)
- `MispricingProfile.should_trade`: gate hierarchy (min_history, min_vol_obs, std threshold, z threshold)
- `BtcImpliedProfile.feed`: residual computation, implied spot calculation
- `halflife_to_alpha`: verify clamping [0.0001, 0.5]

---

## Module 2: config.py

**Source:** `system-map/01-divergence-tracker.md` § 1 (Constants & Configuration), § 3 (RuntimeConfig, CoinRoster)
**Source:** `SPEC-binary-options-controller.md` § 1 (Config)

### Contains

#### BinaryOptionsControllerConfig (extends ControllerConfigBase)
```python
class BinaryOptionsControllerConfig(ControllerConfigBase):
    controller_type: str = "generic"
    controller_name: str = "binary_options"
    connector_name: str = "limitless"
    runtime_json_path: str
    config_json_path: str
    poll_interval_ms: int = 1500
    vol_warmup_ticks: int = 20
    routing: ActionRoutingConfig
```

#### ActionRoutingConfig (Pydantic BaseModel)
All decision tree toggles — see SPEC-binary-options-controller.md § 1.
Entry mode, mint config, delta neutral, signal agreement, exit routing, position sizing.

#### RuntimeBridge
Hot-reloadable runtime.json reader. Replaces `RuntimeConfig` from divergence_tracker.

```python
class RuntimeBridge:
    def __init__(self, path: str, check_interval: float = 30.0)
    def check(self) → bool                    # stat() file, reload on mtime change
    def get_coin_param(self, coin, key, default) → value  # per-coin resolution
    def get_alphas(self, coin, interval_secs) → (baseline_α, current_α, mispricing_α)
    def should_trade(self) → bool             # trading_enabled AND NOT paused
    @property overrides → dict                # all non-coin, non-meta keys
```

Resolution order for `get_coin_param(coin, key, default)`:
1. `coins[COIN][key]` in runtime.json
2. Top-level `key` in runtime.json
3. `default`

#### CoinRoster
Tier management: MAIN / PROBATION / REHAB / BANNED.

```python
class CoinRoster:
    def __init__(self, runtime_bridge: RuntimeBridge)
    def tier(self, coin) → str
    def size_multiplier(self, coin) → float   # 1.0 or 0.0 (banned)
    def ensure_listed(self, coin)
```

Reads tier from `runtime.json["coins"][COIN]["tier"]`. Does NOT write (controller is read-only for runtime.json; evaluator writes).

#### Static config loader
Reads `config.json["divergence"]` for DEFAULT_CFG overlay.
All ~80 keys from `DEFAULT_CFG` (see system-map/01 § 1) become attributes.

---

## Module 3: signal_engine.py

**Source:** `system-map/01-divergence-tracker.md` § 2 (Data Structures), § 3 (DynamicThresholds), § 4 (Signal Generation — ALL subsections)

### Contains

#### Data structures (from 01 § 2)
- `TypeStats` — per-event-type stats (count, magnitudes, correction_rate)
- `OpenSignal` — pending signal awaiting resolution
- `EMALayer` — one tier of 3-layer EMA (lag_rate, follow_rate, magnitude, beta, etc.)
- `CoinProfile` — full behavioral profile (type1/2/3 stats, 3 EMA layers, mispricing/btc_implied refs)

#### DynamicThresholds (from 01 § 3)
- Rolling std × 1.5 for BTC and per-coin move detection
- Floor at 30% of static config values
- `feed(btc_delta, coin_deltas)` / `_recompute()`

#### EMA feed functions (from 01 § 4)
- `_ema()`, `_ema_var()` — base EMA + Welford variance update
- `_feed_lag()`, `_feed_follow()`, `_feed_lag_secs()`, `_feed_directional()`, `_feed_inverse()`, `_feed_magnitude()`, `_feed_beta()` — per-event-type EMA updates on baseline + current layers simultaneously

#### Scoring functions (from 01 § 4)
- `merged_lag_rate(prof, weights, min_events_curr)` — weighted 3-layer merge with graceful degradation
- `merged_inverse_rate(prof, weights, min_events_curr)`
- `lag_z_score(prof, ...)` — logit-space z-score: `logit(recent) - logit(baseline)`
- `inverse_z_score(prof, ...)`
- `beta_anomaly_signal(prof, cfg)`, `inverse_beta_signal(prof, cfg)`
- `compute_confidence(prof, tolerance, min_events_curr)` — "HIGH" if layer spread ≤ tolerance

#### Event classification (from 01 § 4)
- Type 1/2/3 classification per tick based on BTC + coin deltas vs dynamic thresholds
- Signal resolution (T1: followed/inversed/timeout, T3: correction or unresolved)

#### Dual-score entry system (from 01 § 4)
- 3 independent paths: SPOT, BTC, COMBINED
- SPOT: `mispricing_profile.should_trade()` → edge_direction
- BTC: `btc_implied.should_trade()` → btc_direction (with follow_rate floor gate)
- COMBINED: both agree, z-scores additive
- Priority order configurable, first accepted wins
- Conflict detection (spot_dir ≠ btc_dir)

#### Hour boundary handling (from 01 § 6)
- `_check_hour_boundary()` — rotate current → last_hour, reset current EMALayer

#### Main interface
```python
class SignalEngine:
    def __init__(self, config, runtime_bridge, fair_value_module)
    def tick(self, spots: dict, markets: dict, btc_spot: float) → dict
        # Returns per-coin signal data:
        # {coin: {spot_signal, btc_signal, direction, edge, z_score, ...}}
    def get_profiles(self) → dict[str, CoinProfile]
```

The `tick()` method is the entire Pyth fair-value block from the main loop (01 § 6, step 8):
1. Compute deltas, classify events
2. Feed EMA layers
3. Compute vol, B-S model_prob
4. Feed MispricingProfile + BtcImpliedProfile
5. Run dual-score entry system
6. Return signal dict

### Changes from original
- No CSV writing (controller handles reporting)
- No TickerDisplay (use controller's `to_format_status()`)
- No direct trader calls — returns signal data, controller routes
- Takes timestamps from controller, not `time.monotonic()`

---

## Module 4: market_manager.py

**Source:** `system-map/01-divergence-tracker.md` § 3 (MarketSelector), § 5 (Market Selection — ALL 3 layers)
**Source:** `system-map/04-data-layer.md` § 1 (LimitlessClient — fetch_hourly_crypto, ATM selection)

### Contains

#### MarketManager
Wraps the 3-layer MarketSelector logic.

```python
class MarketManager:
    def __init__(self, connector, config, roster, runtime_bridge)

    def discover(self, spots, force=False) → dict
        # Layer 1: fetch active markets, ATM selection per coin
        # Triggers: startup, hourly, force flag, pending ban confirmation
        # Uses connector.get_active_markets() instead of LimitlessClient

    def evaluate(self, force=False) → dict
        # Layer 2: WS-based scoring (depth + ATM proximity)
        # Hysteresis: only switch if new > current × 1.1
        # Interval: msel_eval_interval_s (default 60s)

    def build_market_data(self, prev_data=None) → dict
        # Layer 3: per-tick price fetch
        # WS cache → HTTP fallback → prev_data recycling

    def check_expiry(self, active_positions) → set
        # Expiry/rollover detection
        # Drain mode for coins with positions near expiry

    @property locked_markets → dict  # {coin: market_dict}
```

**ATM selection:** From 04 § 1 — `|spot - strike| / spot` if spot known, else `|yes_price - 0.50|`. Tie-break: earlier expiry.

**Market dict structure:** Same as 04 § 1 — coin, yes_price, no_price, strike, slug, expiry, pyth_address, max_spread, volume.

### Changes from original
- Uses Hummingbot connector for API calls instead of LimitlessClient
- Connector's WS layer replaces OrderbookCache for real-time data
- No PID locking / process management
- Roster integration via CoinRoster from config.py (read-only)
- Pending ban logic simplified (controller doesn't write runtime.json)

---

## Module 5: action_router.py

**Source:** `SPEC-binary-options-controller.md` § 3 (Decision Tree)
**Source:** `SPEC-execution-paths.md` (all 14 paths + incentive programs)

### Contains

This is entirely NEW logic. No direct port from limitless-recon.

```python
class ActionRouter:
    def __init__(self, routing_config: ActionRoutingConfig, position_tracker)

    def route(self, signals: dict, market_data: dict, active_executors: list) → list[CreateExecutorAction]
        # For each coin with signal:
        # 1. Check signal agreement (conflict_mode)
        # 2. Check position limits
        # 3. Walk decision tree → select path
        # 4. Compute position size
        # 5. Build executor config
        # Returns list of CreateExecutorAction

    def _select_path(self, signal, market, routing) → ExecutionPath
        # Decision tree:
        # delta_neutral check → mint check → taker check → default limit

    def _compute_size(self, coin, signal, routing) → float
        # fixed / edge_scaled / kelly

    def _build_executor_config(self, path, coin, signal, market, size) → PositionExecutorConfig | OrderExecutorConfig
        # Maps execution path to V2 executor config
        # Sets triple_barrier_config (stop loss, trailing, time limit)
```

#### ExecutionPath enum
```python
class ExecutionPath(str, Enum):
    BUY_YES_MARKET = "buy_yes_market"       # Path 1
    BUY_YES_LIMIT = "buy_yes_limit"         # Path 2
    MINT_SELL_NO_MARKET = "mint_sell_no_mkt" # Path 3
    MINT_SELL_NO_LIMIT = "mint_sell_no_lmt"  # Path 4
    SELL_NO_LIMIT = "sell_no_limit"          # Path 5
    BUY_NO_MARKET = "buy_no_market"         # Path 6
    BUY_NO_LIMIT = "buy_no_limit"           # Path 7
    MINT_SELL_YES_MARKET = "mint_sell_yes_mkt"  # Path 8
    MINT_SELL_YES_LIMIT = "mint_sell_yes_lmt"   # Path 9
    SELL_YES_LIMIT = "sell_yes_limit"        # Path 10
    MINT_SELL_BOTH = "mint_sell_both"        # Path 11
    BUY_BOTH = "buy_both"                   # Path 12
```

### Decision tree (from SPEC-binary-options-controller.md § 3)
```
Signal fires (direction = YES or NO)
├─ conflict_mode check
├─ position limits check
├─ delta_neutral_enabled AND small edge AND spread > min? → Path 11
├─ mint_enabled AND mint_prefer_over_buy? → Path 4/9
├─ entry_mode=market OR edge > taker_threshold OR time < taker_time? → Path 1/6
└─ DEFAULT → Path 2/7
```

All thresholds from ActionRoutingConfig. Phase 1: only paths 2, 7 active (limit buy).

---

## Module 6: exit_manager.py

**Source:** `system-map/02-orchestration-execution.md` § 2.5 (check_positions — complete exit logic)

### Contains

7-priority exit cascade, evaluated in order for each active position:

```python
class ExitManager:
    def __init__(self, config, runtime_bridge)

    def check_all(self, active_executors: list, market_data: dict, profiles: dict) → list[StopExecutorAction]
        # For each active executor:
        # Run priority cascade, first trigger wins

    def _check_exit(self, executor_info, coin_data, profile) → Optional[StopExecutorAction]
```

#### Priority 1: Market Expiry
- `hours_left <= 0` or within `close_secs` of expiry
- If winning (favorable price): hold for settlement ($1 payout) if `prob > settlement_hold_threshold`
- If losing or uncertain: emergency market exit

#### Priority 2: BTC Reversal
- Track cumulative BTC spot delta since entry: `net_btc_delta = btc_spot - pos.btc_entry_spot_price`
- Trigger: `|net_btc_delta| >= btc_reversal_multiplier` AND direction opposes position
- Source: 02 § 2.5, BTC reversal subsection
- **This is the main reason we need a custom executor later** — standard PositionExecutor doesn't have cross-asset exit triggers

#### Priority 3: Confirmed Stop Loss
- `uPnL% < -stop_loss_pct` (per-coin from runtime.json)
- Confirmation: must breach for `stop_loss_confirm_required` consecutive ticks (default 2) AND `stop_loss_confirm_secs` elapsed
- Grace period: `stop_loss_grace_secs` after entry (no stop in first N seconds)

#### Priority 4: Trailing Stop Arm
- When `uPnL% > trailing_trigger_pct`: activate trailing, record peak PnL
- Per-coin params from runtime.json

#### Priority 5: Take Profit Squeeze
- Threshold from `compute_magnitude_threshold()` (Type 2 magnitudes)
- Time decay: `threshold × (1 - (elapsed/timeout)^decay_exp) × tp_squeeze_factor`
- Squeezes TP target toward zero as time passes

#### Priority 6: Trailing Stop Fire
- If trailing active AND `peak_pnl - current_pnl > trailing_distance_pct × peak_pnl`
- Fires the trail

#### Priority 7: Adaptive Timeout
- Base timeout from `compute_stop_timeout()` (fallback_pct × market_duration)
- Extensions: if trending favorably, extend by `timeout_extension_factor` (up to `max_timeout_extensions`)
- Hard ceiling: `max_timeout_multiplier × base_timeout`
- "Trending" = price moved further in favorable direction since entry

#### Exit routing
- Same decision tree as entry but simpler: `exit_mode` config
- "limit" → StopExecutorAction (executor closes via limit)
- "market" → StopExecutorAction with force flag
- "auto" → market if `minutes_left < exit_taker_urgency_min`, else limit

### Changes from original
- No walk-the-book simulation — real fills from executor
- Phase 1: BTC reversal implemented in controller (StopExecutorAction). Phase 3: moves to custom executor.
- Settlement/redeem: controller detects expiry, holds position (no action = hold), or stops executor for early exit

---

## Module 7: position_tracker.py

**Source:** `system-map/02-orchestration-execution.md` § 2.4 (on_signal — pre-entry gates), § 2.5 (check_positions — streak tracking, circuit breaker)

### Contains

```python
class PositionTracker:
    def __init__(self, config, runtime_bridge)

    # Pre-entry gates
    def can_open(self, coin, direction) → (bool, str)
        # Checks: max_positions_per_coin, max_total_positions, cooldown,
        # streak pause, circuit breaker, exposure limit

    def record_open(self, coin, executor_id, direction, size)
    def record_close(self, coin, executor_id, pnl)

    @property total_exposure → float
    @property open_count → int
    def positions_for_coin(self, coin) → int
```

#### Pre-entry gates (from 02 § 2.4, on_signal)
1. `max_open_positions` — total across all coins
2. `max_total_exposure_pct` — total $ exposure / capital
3. Per-coin cooldown — `_coin_last_exit_time[coin]` + cooldown seconds
4. Streak tracking — N consecutive losses on a coin → pause for M seconds
   - Config: `streak_cooldown` per-coin in runtime.json `{threshold: int, pause_secs: float}`
5. Circuit breaker — N main-tier losses in window → halt all main entries
   - Config: `cb_max_losses`, `cb_window_secs`
6. `min_position_size` — reject if computed size too small
7. `max_edge_entry_price` / `min_edge_entry_price` — YES price range gate

#### Cooldown
- Per-coin from runtime.json: `{COIN}_cooldown` (seconds since last exit)
- Resolution via `runtime_bridge.get_coin_param()`

### Changes from original
- No Position dataclass (V2 executors manage their own state)
- Tracks by executor_id, not internal Position objects
- Reads PnL from executor_info on close

---

## Module 8: pyth_feed.py

**Source:** `system-map/04-data-layer.md` § 3 (PythClient, PythFetcher)

### Contains

```python
class PythFeed:
    def __init__(self, connector)

    def update_addresses(self, markets: dict)
        # Extract pyth_address from market dicts
        # Pass to connector for Pyth queries

    def get_prices(self) → dict[str, float]
        # Returns {ticker: spot_price_usd}
        # Calls connector.get_spot_prices() or internal PythFetcher

    def get_btc_price(self) → float
```

### Implementation options
1. **Connector method** (recommended): Add `get_spot_prices(pyth_addresses)` to Limitless connector. Connector calls Pyth Hermes API. Background fetch thread lives in connector.
2. **Standalone**: Port PythFetcher directly into this module. Works immediately but bypasses connector pattern.
3. **Hummingbot candles**: Use `market_data_provider.get_candles_df()`. Different data source, potential oracle discrepancy.

### Phase 1: Option 2 (standalone port), Phase 2: migrate to Option 1

---

## Module 9: controller.py

**Source:** `V2-REFERENCE.md` § 3 (ControllerBase API)

### Contains

Thin orchestrator wiring all modules together.

```python
class BinaryOptionsController(ControllerBase):
    def __init__(self, config: BinaryOptionsControllerConfig, market_data_provider, actions_queue):
        super().__init__(config, market_data_provider, actions_queue)
        self.runtime_bridge = RuntimeBridge(config.runtime_json_path)
        self.roster = CoinRoster(self.runtime_bridge)
        self.pyth_feed = PythFeed(self)
        self.signal_engine = SignalEngine(config, self.runtime_bridge, fair_value)
        self.market_manager = MarketManager(self, config, self.roster, self.runtime_bridge)
        self.exit_manager = ExitManager(config, self.runtime_bridge)
        self.position_tracker = PositionTracker(config, self.runtime_bridge)
        self.action_router = ActionRouter(config.routing, self.position_tracker)

    async def update_processed_data(self):
        self.runtime_bridge.check()
        spots = self.pyth_feed.get_prices()
        markets = self.market_manager.discover(spots)
        self.market_manager.build_market_data()
        signals = self.signal_engine.tick(spots, markets, spots.get("BTC", 0))
        self.processed_data.update({"coins": signals, "btc_spot": spots.get("BTC", 0)})

    def determine_executor_actions(self) -> list:
        actions = []
        expired = self.market_manager.check_expiry(self.executors_info)
        actions += self.exit_manager.check_all(self.executors_info, self.processed_data, self.signal_engine.get_profiles())
        actions += self.action_router.route(self.processed_data["coins"], self.processed_data, self.executors_info)
        return actions

    def to_format_status(self) -> list[str]:
        # Dashboard display — coin grid, signal states, position summary
        # Replaces TickerDisplay from divergence_tracker
```

### Key V2 contracts
- `update_processed_data()` called every tick by control loop
- `determine_executor_actions()` returns `List[CreateExecutorAction | StopExecutorAction]`
- Never touch executors directly — actions go through queue
- `self.executors_info` updated by orchestrator (read-only from controller side)

---

## Build Order

Modules with zero cross-dependencies first:

1. **fair_value.py** — zero deps, pure math, straight port
2. **config.py** — needs only Pydantic
3. **signal_engine.py** — needs fair_value + config
4. **market_manager.py** — needs connector + config
5. **position_tracker.py** — needs config
6. **exit_manager.py** — needs config + position_tracker
7. **action_router.py** — needs config + position_tracker + order_types
8. **pyth_feed.py** — needs connector
9. **controller.py** — wires everything, build last

Each can be built + tested independently. Sub-agents get: this spec (their module section) + relevant system-map file + V2-REFERENCE.md.

---

## Reference Paths

| Doc | Path | Relevant modules |
|-----|------|-----------------|
| System Map 01 | `docs/limitless/system-map/01-divergence-tracker.md` | signal_engine, market_manager, config |
| System Map 02 | `docs/limitless/system-map/02-orchestration-execution.md` | exit_manager, position_tracker |
| System Map 04 | `docs/limitless/system-map/04-data-layer.md` | fair_value, pyth_feed |
| V2 Reference | `docs/limitless/V2-REFERENCE.md` | controller, action_router, exit_manager |
| Execution Paths | `docs/limitless/specs/SPEC-execution-paths.md` | action_router |
| Order Types | `docs/limitless/specs/SPEC-order-types.md` | action_router |
| Controller Spec | `docs/limitless/specs/SPEC-binary-options-controller.md` | controller, config |
| Original fair_value.py | `skills/limitless-recon/scripts/fair_value.py` | fair_value (direct port) |
