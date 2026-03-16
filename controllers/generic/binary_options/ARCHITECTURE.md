# BinaryOptionsController — Architecture

## Overview

Signal-driven binary options controller for Limitless Exchange prediction markets.
Extends Hummingbot V2 `ControllerBase` — platform-agnostic, modular, all params backtestable via Optuna.

**Dual mode:** Directional trading (action_router) OR signal-informed market making (quote_manager).
Config toggle switches between modes. Both share the same signal infrastructure.

## Module Map

```
controllers/generic/binary_options/
├── controller.py         # Thin orchestrator — wires modules, only HB import boundary
├── config.py             # Config classes, RuntimeBridge (hot-reload), CoinRoster
├── signal_engine.py      # EMA layers, type classification, dual-score entry signals
├── fair_value.py         # Black-Scholes pricing, MispricingProfile, BtcImpliedProfile
├── market_manager.py     # Market discovery → evaluation → per-tick data (3-layer)
├── position_tracker.py   # Pre-entry gates, cooldowns, streaks, circuit breaker
├── exit_monitor.py       # BTC reversal + settlement detection (Phase 1 only)
├── action_router.py      # Decision tree → 12 entry paths, conflict modes, sizing
├── quote_manager.py      # Signal-informed MM — reward tunnel, z-score driven quoting
├── spot_feed.py          # Spot prices: Pyth batch primary, Binance fallback
├── order_types.py        # Order type enums, dataclasses, BinaryOrderExecutor routing
├── __init__.py           # Exports BinaryOptionsController + Config
└── tests/
    ├── conftest.py           # Shared HB module stubs
    ├── test_controller.py
    ├── test_config.py
    ├── test_signal_engine.py
    ├── test_fair_value.py
    ├── test_market_manager.py
    ├── test_position_tracker.py
    ├── test_exit_monitor.py
    ├── test_action_router.py
    ├── test_spot_feed.py
    └── test_quote_manager.py
```

## Data Flow (per tick)

```
┌─────────────────────────────────────────────────────────────────┐
│                    controller.py (orchestrator)                  │
│                                                                 │
│  update_processed_data():                                       │
│    1. runtime_bridge.check()          ← hot-reload runtime.json │
│    2. spot_feed.get_prices()          ← Pyth/Binance spot       │
│    3. market_manager.discover()       ← find active markets     │
│    4. market_manager.evaluate()       ← WS scoring              │
│    5. market_manager.build_market_data() ← per-tick prices      │
│    6. signal_engine.tick()            ← generate signals        │
│                                                                 │
│  determine_executor_actions():                                  │
│    if quoting.enabled:                                          │
│      7a. quote_manager.tick()         → QuoteActions            │
│    else:                                                        │
│      7b. exit_monitor.check_all()     → StopExecutorAction[]    │
│      7c. action_router.route()        → CreateExecutorAction[]  │
│    8. sync closed executors           → position_tracker        │
└─────────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### controller.py
- Extends `ControllerBase` — ONLY file importing Hummingbot classes
- Wires all modules in `__init__`, connector in `on_start()`
- Routes to quote_manager (MM mode) or action_router (directional mode) based on config
- Converts plain dicts from modules → `CreateExecutorAction` / `StopExecutorAction`

### config.py
- `BinaryOptionsControllerConfig` — top-level controller config (Pydantic)
- `ActionRoutingConfig` — 18 toggles for directional decision tree
- `QuoteConfig` — MM parameters (tunnel bounds, skew, sizing)
- `RuntimeBridge` — hot-reload `runtime.json`, per-coin param access
- `CoinRoster` — tier→multiplier mapping (MAIN=1.0, REHAB=0.5, BANNED=0)

### signal_engine.py
- `SignalEngine` — main signal pipeline class
- Type 1/2/3 classification → EMA layers (behavioral plumbing)
- Dual-score entry: SPOT z-score + BTC z-score → COMBINED
- Output used by BOTH action_router and quote_manager

### fair_value.py
- `compute_model_prob()` — Black-Scholes probability with time decay
- `compute_edge()` — model_prob vs market_price
- `MispricingProfile` — spot mispricing tracking + z-score gating
- `BtcImpliedProfile` — BTC-implied price divergence
- Pure math, zero side effects

### market_manager.py
- 3-layer selection: discover → evaluate → per-tick prices
- ATM strike selection, BANNED filtering, drain mode, expiry detection

### position_tracker.py
- 7 pre-entry gates (position limits, cooldown, streak, circuit breaker)
- Used by BOTH action_router (directional) and quote_manager (post-fill)

### exit_monitor.py (Phase 1)
- BTC reversal detection (cross-asset exit trigger)
- Settlement proximity detection (hold winners, exit losers)
- Used in directional mode AND for filled MM positions

### action_router.py (directional mode)
- 12 entry paths via `ExecutionPath` enum
- Decision tree: delta neutral → mint → taker/market → limit
- Signal conflict handling (veto/reduce/ignore)
- Position sizing (fixed/edge_scaled/kelly)

### quote_manager.py (MM mode)
- Signal-informed market making within LP reward tunnel
- **Reward tunnel:** inner wall (competitive) ↔ outer wall (LP spread limit)
- Z-score slides quote position within tunnel
- Model disagreement skews tunnel asymmetrically
- At threshold: favored side stays (inner wall), opposing side pulls
- Post-fill: dynamic close order using `tp_distance` from runtime.json
- 5 states: IDLE → SYMMETRIC → SKEWED → ONE_SIDED → FILLED → CONVERGED
- **No new thresholds** — all from existing runtime.json via RuntimeBridge

### spot_feed.py
- Pyth batch primary + Binance individual fallback
- Independent circuit breakers per source, cache with 3s TTL

### order_types.py
- Order type enums, dataclasses, routing plumbing
- Phase 1: limit buy only. Phase 2: full lifecycle.

## Revenue Streams (MM Mode)

| Stream | Mechanism | Requires Fills? |
|--------|-----------|-----------------|
| LP Rewards | Orders within spread of midpoint, per-minute calculation | No |
| Maker Rebates | 20% of taker fees on Hourly + 15-min Crypto | Yes |
| Spread Capture | Both sides filled at total < $1.00 = settlement profit | Yes (both) |

**LP Reward Rules:**
- Max spread from midpoint (per-market, e.g. 3¢)
- Min shares threshold (per-market, e.g. 100)
- Bonus multiplier for tighter quotes
- One-sided OK only at 5%–95% odds
- **Makers pay ZERO fees** — placing/cancelling is free

## Threshold Reuse (MM Mode)

| runtime.json param | Directional usage | MM usage |
|---|---|---|
| `edge_z_threshold` | Entry trigger | Opposing-side pull trigger |
| `btc_z_threshold` | BTC signal gate | Opposing-side pull trigger |
| `tp_distance` | Take profit | Post-fill close order distance |
| `scale_in_cooldown_seconds` | Scale-in cooldown | Post-fill requoting cooldown |

## 14 Execution Paths (Directional Mode)

| # | Path | Direction | Method | Phase |
|---|------|-----------|--------|-------|
| 1 | BUY_YES_MARKET | Bullish | Market buy YES | 1 |
| 2 | **BUY_YES_LIMIT** | Bullish | Limit buy YES | **1 (default)** |
| 3 | MINT_SELL_NO_MARKET | Bullish | Mint + market sell NO | 2 |
| 4 | MINT_SELL_NO_LIMIT | Bullish | Mint + limit sell NO | 2 |
| 5 | SELL_NO_LIMIT | Bullish | Limit sell NO (held) | 2 |
| 6 | BUY_NO_MARKET | Bearish | Market buy NO | 1 |
| 7 | **BUY_NO_LIMIT** | Bearish | Limit buy NO | **1 (default)** |
| 8 | MINT_SELL_YES_MARKET | Bearish | Mint + market sell YES | 2 |
| 9 | MINT_SELL_YES_LIMIT | Bearish | Mint + limit sell YES | 2 |
| 10 | SELL_YES_LIMIT | Bearish | Limit sell YES (held) | 2 |
| 11 | MINT_SELL_BOTH | Neutral | Mint + sell both sides | 2 |
| 12 | BUY_BOTH | Neutral | Buy both sides | 2 |
| 13 | EXIT (sell/redeem) | Exit | exit_monitor / executor | 1+2 |
| 14 | EXIT (settlement hold) | Exit | Hold for $1 payout | 1+2 |

## External Dependencies

```
controller.py imports:
  hummingbot.strategy_v2.controllers.controller_base.ControllerBase
  hummingbot.strategy_v2.models.executor_actions.{Create,Stop}ExecutorAction
  hummingbot.strategy_v2.executors.position_executor.data_types.*
  hummingbot.core.data_type.common.{TradeType, OrderType}

All other modules: stdlib + sibling imports only
  (logging, time, enum, dataclasses, math, statistics, requests)
```

## Config Hierarchy

```
conf/controllers/binary_options.yml     ← YAML loaded by Hummingbot
  → BinaryOptionsControllerConfig       ← Pydantic model
    → ActionRoutingConfig               ← 18 toggles (directional)
    → QuoteConfig                       ← MM parameters (tunnel, skew, sizing)
    → runtime_json_path                 ← points to runtime.json

runtime.json (external, hot-reloaded)   ← written by Optuna evaluator
  → per-coin params (thresholds, tp_distance, cooldowns)
  → param_space (Optuna search ranges)
  → tiers (MAIN/REHAB/BANNED)
  → _pinned (locked params)
```

## Phase Plan

| Phase | What | Status |
|-------|------|--------|
| 1 | BinaryOptionsController + PositionExecutor (limit buy only) | ✅ Done |
| 2 | Integration test + MM module (quote_manager) | ✅ Building |
| 3 | Custom BinaryOptionsExecutor (7-priority exits, mint, settlement) | Specced |
| 4 | Port signal logic fully, kill standalone tracker | Planned |

## Test Summary

| Module | Tests |
|--------|-------|
| fair_value | 46 |
| config | 15 |
| signal_engine | 18 |
| market_manager | 18 |
| position_tracker | 13 |
| exit_monitor | 11 |
| action_router | 20 |
| spot_feed | 10 |
| controller | 9 |
| order_types | 32 |
| quote_manager | TBD |
| **Total** | **192+** |

## Spec Documents

All in `docs/limitless/`:
- `system-map/01-divergence-tracker.md` — signal pipeline extraction (38KB)
- `system-map/02-orchestration-execution.md` — trading logic extraction (42KB)
- `system-map/03-param-tuning.md` — Optuna/evaluator extraction (25KB)
- `system-map/04-data-layer.md` — fair value + price feeds extraction (14KB)
- `specs/SPEC-binary-options-controller.md` — controller architecture
- `specs/SPEC-module-breakdown.md` — 9-module plan + build order
- `specs/SPEC-binary-options-executor.md` — Phase 2 executor
- `specs/SPEC-quote-manager.md` — MM module (reward tunnel, z-score quoting)
- `specs/SPEC-execution-paths.md` — 14 paths taxonomy
- `specs/SPEC-order-types.md` — order type system
- `specs/SPEC-script-and-config.md` — top-level script + YAML
- `specs/SPEC-v2-architecture-mapping.md` — system→V2 mapping
- `V2-REFERENCE.md` — Hummingbot V2 internals (502 lines)
