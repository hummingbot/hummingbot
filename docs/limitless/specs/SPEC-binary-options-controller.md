# SPEC: BinaryOptionsController

## Overview

Controller extending `ControllerBase` that:
1. Reads signal parameters from `runtime.json` (written by external Optuna tuner)
2. Runs fair value + mispricing engine each tick
3. Passes signals through gate cascade
4. Routes to one of 14 execution paths via configurable decision tree
5. Manages positions through executor actions

**Not a 1:1 port.** Signal math (B-S, mispricing profiles, BTC correlation) is preserved.
Action routing (the 14 paths) is NEW — configurable, backtestable.

---

## File Structure

```
controllers/
  generic/
    binary_options/
      __init__.py
      binary_options_controller.py    ← THIS SPEC
      order_types.py                  ← EXISTS (built)
      fair_value.py                   ← port from limitless-recon
      config_schema.py               ← controller config + action routing config
```

---

## 1. Config

### BinaryOptionsControllerConfig (extends ControllerConfigBase)

```python
class BinaryOptionsControllerConfig(ControllerConfigBase):
    controller_type: str = "generic"
    controller_name: str = "binary_options"

    # --- Connection ---
    connector_name: str = "limitless"
    trading_pair: str = "CRYPTO-USD"          # placeholder, actual pairs are dynamic

    # --- Runtime params (from runtime.json, per-coin) ---
    runtime_json_path: str                     # path to runtime.json
    config_json_path: str                      # path to config.json (roster, divergence settings)

    # --- Signal engine ---
    poll_interval_ms: int = 1500               # tick rate
    vol_warmup_ticks: int = 20                 # min ticks before vol is trusted (min_vol_obs)

    # --- Action routing (the decision tree) ---
    routing: ActionRoutingConfig               # see below
```

### ActionRoutingConfig

Every branch point in the decision tree = a toggle or threshold.

```python
class ActionRoutingConfig(BaseModel):
    # --- Entry method selection ---
    entry_mode: str = "limit"                  # "limit" | "market" | "auto"
    taker_edge_threshold: float = 0.15         # edge above this → market order (if entry_mode="auto")
    taker_time_threshold_min: float = 5.0      # minutes to expiry below this → allow taker

    # --- Mint paths ---
    mint_enabled: bool = False                 # enable MINT + SELL paths
    mint_min_spread: float = 0.03              # min YES+NO spread above $1.00 to make minting profitable
    mint_prefer_over_buy: bool = False         # when True, prefer MINT+SELL_OPP over BUY (Phase 2)

    # --- Delta neutral ---
    delta_neutral_enabled: bool = False        # enable MINT + SELL BOTH path
    delta_neutral_max_edge: float = 0.03       # only go neutral when abs(edge) below this
    delta_neutral_min_spread: float = 0.02     # min profit margin for neutral path

    # --- Signal agreement ---
    require_signal_agreement: bool = False     # require both spot + BTC to agree for entry
    conflict_mode: str = "veto"                # "veto" | "reduce" | "ignore"
    conflict_size_mult: float = 0.5            # size multiplier when signals conflict (if mode="reduce")

    # --- Exit routing ---
    exit_mode: str = "limit"                   # "limit" | "market" | "auto"
    exit_taker_urgency_min: float = 2.0        # minutes to expiry → force market exit
    hold_to_settlement: bool = True            # if winning at expiry, hold for $1.00 payout
    settlement_hold_threshold: float = 0.70    # min probability of winning to hold vs exit early

    # --- Position management ---
    max_positions_per_coin: int = 1            # max concurrent positions per ticker
    max_total_positions: int = 5               # max concurrent across all coins
    position_size_mode: str = "fixed"          # "fixed" | "edge_scaled" | "kelly"
    fixed_position_size: float = 5.0           # USDC per position (if fixed)
    max_position_size: float = 20.0            # cap for scaled modes
    edge_size_multiplier: float = 100.0        # position = edge * multiplier (if edge_scaled)
```

**All values are defaults.** Every field goes into param_space for optimization.

---

## 2. Signal Engine (ported from limitless-recon)

Lives in controller's `update_processed_data()`. Runs every tick.

### Per-tick flow:

```
1. Fetch spot prices (Pyth or Hummingbot candles)
2. Fetch market data (YES/NO prices, orderbook, expiry)
3. For each active coin:
   a. Compute hourly volatility (EMA-smoothed)
   b. Compute B-S fair value → model_prob
   c. Update MispricingProfile (spot score)
   d. Update BtcImpliedProfile (BTC score)
   e. Run gate cascade → signal or no signal
   f. If signal: compute edge, z-score, direction
4. Store in self.processed_data
```

### processed_data structure:

```python
self.processed_data = {
    "timestamp": float,
    "coins": {
        "BTC": {
            "spot_price": float,
            "strike": float,
            "yes_price": float,
            "no_price": float,
            "hours_left": float,
            "model_prob": float,            # B-S fair value
            "hourly_vol": float,
            "market_slug": str,

            # Spot score
            "spot_edge": float,             # model_prob - yes_price
            "spot_z": float,                # mispricing z-score
            "spot_signal": bool,            # all gates passed

            # BTC score
            "btc_edge": float,              # btc_fair_prob - yes_price
            "btc_z": float,
            "btc_signal": bool,
            "btc_residual": float,          # beta * btc_return - coin_return
            "beta": float,

            # Combined
            "direction": "YES" | "NO" | None,
            "signal_agreement": bool,       # spot + BTC agree
            "signal_conflict": bool,        # spot + BTC disagree

            # Orderbook
            "bid": float,
            "ask": float,
            "spread": float,
            "bid_depth": float,
            "ask_depth": float,

            # Runtime params (from runtime.json, per-coin)
            "z_threshold": float,
            "cooldown": float,
            "stop_loss_pct": float,
            "timeout_mult": float,
            # ... all per-coin params
        },
        # ... other coins
    },
    "btc_spot": float,                      # shared BTC reference
    "btc_log_return": float,                # precomputed once per tick
}
```

### Gate cascade (ported from divergence_tracker)

All 30 gates preserved. They filter WHETHER to fire. The decision tree routes HOW.

Gates read their thresholds from `runtime.json` per-coin values:
- `z_threshold` — mispricing z-score minimum
- `min_mispricing` — absolute edge minimum (spread-derived)
- `min_vol_obs` — volatility warmup gate
- `cooldown` — seconds since last trade
- `btc_z_threshold` — BTC correlation z-score minimum
- `max_edge_entry_price` / `min_edge_entry_price` — price range gates
- Tier gates (main/probation/rehab/banned)
- Time gates (expiry too soon / too far)
- Spread gates

---

## 3. Decision Tree (action routing)

When a signal fires for a coin, the tree routes to an execution path:

```
Signal fires (direction = YES or NO)
│
├─ Check signal agreement
│  ├─ conflict_mode = "veto" → SKIP
│  ├─ conflict_mode = "reduce" → continue with reduced size
│  └─ conflict_mode = "ignore" → continue normally
│
├─ Check position limits
│  ├─ max_positions_per_coin reached → SKIP
│  └─ max_total_positions reached → SKIP
│
├─ Select entry method
│  │
│  ├─ delta_neutral_enabled AND abs(edge) < delta_neutral_max_edge
│  │  AND spread > delta_neutral_min_spread?
│  │  └─ YES → Path 11: MINT + SELL BOTH (neutral)
│  │
│  ├─ mint_enabled AND mint_prefer_over_buy
│  │  AND spread conditions met?
│  │  └─ YES → Path 4/9: MINT + LIMIT SELL opposite
│  │
│  ├─ entry_mode = "market"
│  │  OR (entry_mode = "auto" AND edge > taker_edge_threshold)
│  │  OR (entry_mode = "auto" AND minutes_left < taker_time_threshold)?
│  │  └─ YES → Path 1/6: MARKET BUY YES/NO
│  │
│  └─ DEFAULT → Path 2/7: LIMIT BUY YES/NO
│
└─ Compute position size
   ├─ position_size_mode = "fixed" → fixed_position_size
   ├─ position_size_mode = "edge_scaled" → min(edge * multiplier, max_position_size)
   └─ position_size_mode = "kelly" → kelly fraction * bankroll (TBD)
```

### Exit routing (separate, runs every tick for open positions):

```
For each active position:
│
├─ Market expired? → Path E3: settlement/redeem
│
├─ Stop loss hit? → exit_mode routing
│  ├─ exit_mode = "market" → Path E1: MARKET SELL
│  └─ exit_mode = "limit" or "auto" → Path E2: LIMIT SELL
│
├─ Trailing stop triggered? → same exit_mode routing
│
├─ BTC reversal detected? → same exit_mode routing
│
├─ Time running out (< exit_taker_urgency_min)?
│  ├─ Position winning AND prob > settlement_hold_threshold?
│  │  └─ Hold for settlement (Path E3)
│  └─ Otherwise → Path E1: MARKET SELL (emergency)
│
├─ Take profit target hit? → exit_mode routing
│
└─ Adaptive timeout? → exit_mode routing
```

Exit priority order (same as original 7-priority system):
1. Market expiry → settlement/redeem
2. BTC reversal close
3. Confirmed stop loss
4. Trailing stop arm
5. Take profit squeeze
6. Trailing stop fire
7. Adaptive timeout

---

## 4. determine_executor_actions()

Returns `List[ExecutorAction]` each tick.

```python
def determine_executor_actions(self) -> List[ExecutorAction]:
    actions = []

    # --- Exit checks (always run first) ---
    for executor_info in self.get_active_executors():
        exit_action = self._check_exit(executor_info)
        if exit_action:
            actions.append(exit_action)

    # --- Entry checks ---
    for coin, data in self.processed_data["coins"].items():
        if not data.get("spot_signal") and not data.get("btc_signal"):
            continue  # no signal

        entry_action = self._route_entry(coin, data)
        if entry_action:
            actions.append(entry_action)

    return actions
```

### _route_entry(coin, data) → Optional[CreateExecutorAction]

Implements the decision tree above. Returns a `CreateExecutorAction` with the
appropriate `PositionExecutorConfig` or `OrderExecutorConfig`.

**Key**: The executor config carries all the info needed:
- `trading_pair` = market slug
- `side` = TradeType.BUY or SELL
- `amount` = position size
- `triple_barrier_config` = stop loss, trailing, take profit, time limit

### _check_exit(executor_info) → Optional[StopExecutorAction]

Runs exit priority cascade. Returns `StopExecutorAction` if any exit condition met.

For settlement: detects market expiry → either holds (no action) or stops executor
and queues redeem call.

---

## 5. Market Discovery

Unlike normal controllers that trade one pair, we trade N coins on M markets.

### update_processed_data() — market refresh

```python
async def update_processed_data(self):
    # Every tick:
    # 1. Discover active markets (use connector's get_active_markets)
    # 2. ATM selection per coin (closest strike to spot)
    # 3. Filter by roster (config.json tiers)
    # 4. Fetch prices, orderbook
    # 5. Run signal engine per coin
    # 6. Store in self.processed_data

    # Market refresh rate can be slower than signal tick
    # (e.g., refresh markets every 60s, signal every 1.5s)
```

### Multi-market handling

The controller internally manages multiple "virtual positions" across different
market slugs. Each slug = a different binary option (different coin, strike, expiry).

Hummingbot V2 normally assumes one trading pair per controller. Options:
1. **One controller instance per coin** — cleanest, but 10+ controllers running
2. **Single controller, internal routing** — one controller manages all coins, creates
   executors with different trading_pair values per market slug
3. **Hybrid** — one controller, but group by coin family

**Recommended: Option 2** — matches current system architecture. Controller owns the
cross-coin logic (BTC correlation, portfolio limits). Trading pair in executor config
= market slug.

---

## 6. Runtime.json Integration

The controller reads `runtime.json` at startup and on a configurable refresh interval.

```python
def _load_runtime(self):
    """Load runtime.json, extract per-coin params."""
    with open(self.config.runtime_json_path) as f:
        rt = json.load(f)

    self._runtime = rt
    self._coin_params = {}
    for coin, params in rt.get("coins", {}).items():
        self._coin_params[coin] = {
            "z_threshold": params.get("z_threshold", 1.5),
            "cooldown": params.get("cooldown", 30),
            "stop_loss_pct": params.get("stop_loss_pct", 0.15),
            "timeout_mult": params.get("timeout_mult", 0.5),
            "decay_exp": params.get("decay_exp", 1.0),
            "btc_rev_mult": params.get("btc_rev_mult", 1.0),
            "trailing_trigger_pct": params.get("trailing_trigger_pct", 0.05),
            "trailing_distance_pct": params.get("trailing_distance_pct", 0.02),
            "btc_z_threshold": params.get("btc_z_threshold", 0.5),
            "current_halflife_secs": params.get("current_halflife_secs", 12),
            "mispricing_halflife_secs": params.get("mispricing_halflife_secs", 23),
            "baseline_halflife_secs": params.get("baseline_halflife_secs", 120),
            "baseline_beta": params.get("baseline_beta", 0.4),
            # ... all per-coin tunable params
        }
```

External Optuna writes to runtime.json → controller picks up new values on next refresh.
Controller never writes to runtime.json.

---

## 7. Spot Price Source

### Option A: Pyth oracle (same as current system)
- Port `PythFetcher` into controller
- Background thread, non-blocking
- Pro: exact same data source as market resolution
- Con: extra dependency, not Hummingbot native

### Option B: Hummingbot candles
- Use `MarketDataProvider.get_candles_df()`
- Pro: native, already wired
- Con: different data source than oracle, possible discrepancy

### Option C: Connector-provided
- Add `get_spot_price()` to Limitless connector
- Calls Pyth internally, exposes as connector method
- Pro: cleanest integration
- Con: new connector method

**Recommended: Option C** — spot price is critical for B-S, must match oracle.
Connector already talks to Limitless, adding Pyth endpoint is minimal.

---

## 8. Phase Plan

### Phase 1: Get It Trading
- Controller with signal engine (B-S + mispricing profiles)
- Gate cascade ported from divergence_tracker
- Entry: LIMIT BUY YES/NO only (paths 2, 7)
- Exit: LIMIT SELL + settlement (paths E2, E3)
- Single controller managing all coins
- Runtime.json integration for per-coin params
- Pyth spot via connector

### Phase 2: Mint Paths + Advanced Execution
- MINT + SELL paths (4, 9, 11)
- Delta neutral strategy
- Market order fallback for time-critical situations
- Edge-scaled position sizing
- Trailing stops via triple barrier config

### Phase 3: Custom Executor
- `BinaryOptionsExecutor` with:
  - BTC reversal close (not in standard PositionExecutor)
  - Settlement/redeem lifecycle
  - Maker rebate tracking
  - LP reward awareness
- Register in ExecutorOrchestrator._executor_mapping

---

## 9. Implementation Notes

### What NOT to port
- WebSocket manager (connector handles this)
- PID locking / process management (Hummingbot framework)
- Walk-the-book fill simulation (real fills from connector)
- CSV logging (use Hummingbot's built-in trade history)
- Telegram alerts (use controller's `to_format_status()` + external)

### What to port exactly
- `fair_value.py` → `controllers/generic/binary_options/fair_value.py`
  - `compute_model_prob()` — unchanged
  - `MispricingProfile` — unchanged
  - `BtcImpliedProfile` — unchanged
  - `halflife_to_alpha()` — unchanged
- Gate cascade logic from `divergence_tracker.py` tick loop
- Market selection (ATM) from `limitless_client.py`
- Exit priority system from `trader.py`

### Dependencies
- `order_types.py` — already built
- Limitless connector — already built (7/7 core functions)
- `runtime.json` — external, read-only
- `config.json` — external, read-only (roster, tiers)
