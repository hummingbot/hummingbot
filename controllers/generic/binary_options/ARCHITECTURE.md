# BinaryOptionsController — Architecture

## Overview

Signal-driven binary options trading controller for Limitless Exchange prediction markets.
Extends Hummingbot V2 `ControllerBase` — platform-agnostic, modular, all params backtestable via Optuna.

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
├── spot_feed.py          # Spot prices: Pyth batch primary, Binance fallback
├── order_types.py        # Order type enums, dataclasses, BinaryOrderExecutor routing
├── __init__.py           # Exports BinaryOptionsController + Config
└── tests/
    ├── test_controller.py
    ├── test_config.py
    ├── test_signal_engine.py
    ├── test_fair_value.py
    ├── test_market_manager.py
    ├── test_position_tracker.py
    ├── test_exit_monitor.py
    ├── test_action_router.py
    └── test_spot_feed.py
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
│    1. exit_monitor.check_all()        → StopExecutorAction[]    │
│    2. action_router.route()           → CreateExecutorAction[]  │
│    3. sync closed executors           → position_tracker        │
└─────────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### controller.py
- Extends `ControllerBase` — ONLY file importing Hummingbot classes
- Wires all modules in `__init__`, connector in `on_start()`
- Converts plain dicts from modules → `CreateExecutorAction` / `StopExecutorAction`
- Builds `PositionExecutorConfig` + `TripleBarrierConfig` per entry (Phase 1)

### config.py
- `BinaryOptionsControllerConfig` — top-level controller config (Pydantic)
- `ActionRoutingConfig` — 18 toggles for decision tree (all Optuna-sweepable)
- `RuntimeBridge` — hot-reload `runtime.json`, per-coin param access, tier management
- `CoinRoster` — tier→multiplier mapping (NORMAL=1.0, REHAB=0.5, BANNED=0)

### signal_engine.py
- `SignalEngine` — main signal pipeline class
- `TypeStats`, `OpenSignal`, `EMALayer`, `CoinProfile`, `DynamicThresholds`
- Type 1/2/3 classification (plumbing → EMA layers, not entry decisions)
- Dual-score entry: SPOT z-score + BTC z-score → COMBINED
- Hour boundary rotation (EMA state rollover)

### fair_value.py
- `compute_model_prob()` — Black-Scholes probability with time decay
- `compute_edge()` — model_prob vs market_price
- `MispricingProfile` — spot mispricing magnitude + direction
- `BtcImpliedProfile` — BTC-implied price divergence
- `halflife_to_alpha()` — EMA alpha from halflife in seconds
- Pure math, zero side effects, explicit `ts` parameter

### market_manager.py
- 3-layer selection: discover → evaluate → per-tick prices
- `discover()` — find hourly crypto markets, ATM strike selection
- `evaluate()` — WS subscription scoring, liquidity check
- `build_market_data()` — current YES/NO prices, volume, expiry
- BANNED filtering, drain mode, expiry detection

### position_tracker.py
- 7 pre-entry gates (position limits, cooldown, streak, circuit breaker, etc.)
- `can_open(coin, now_ts)` → bool (called by action_router)
- `record_open()` / `record_close()` — state tracking
- Circuit breaker: N consecutive losses → pause trading for cooldown period

### exit_monitor.py (Phase 1 — temporary)
- BTC reversal: cross-asset exit when BTC moves against position ≥ threshold
- Settlement: hold winners near expiry (→ $1.00), exit losers
- Returns plain dicts — controller wraps in `StopExecutorAction`
- **Removed in Phase 2** when `BinaryOptionsExecutor` owns all exits

### action_router.py
- `ExecutionPath` enum — 12 entry paths (5 bullish, 5 bearish, 2 neutral)
- Decision tree: delta neutral → mint → taker/market → DEFAULT limit
- `_check_conflict()` — veto / reduce / ignore signal disagreement
- `_compute_size()` — fixed / edge_scaled / kelly
- Phase 1: only paths 2 (BUY_YES_LIMIT) and 7 (BUY_NO_LIMIT) active

### spot_feed.py
- Source-agnostic spot prices (Pyth primary, Binance fallback)
- Pyth: batch HTTP to Hermes API (all tickers in 1 call)
- Binance: individual ticker fallback
- Independent circuit breakers per source
- Cache with 3s TTL, auto Pyth recovery every 50 ticks
- `is_stale` property for health monitoring

### order_types.py
- `OrderSide`, `OrderExecution`, `MintAction` enums
- `BinaryOrderConfig` — order params (side, price, size, execution, mint)
- `BinaryOrderExecutor` — routing: limit/market/mint flows via connector
- Phase 1 plumbing — full executor lifecycle in Phase 2

## 14 Execution Paths

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
    → ActionRoutingConfig               ← 18 toggles (decision tree)
    → runtime_json_path                 ← points to runtime.json

runtime.json (external, hot-reloaded)   ← written by Optuna evaluator
  → per-coin params (stop_loss, trailing, timeout, thresholds)
  → param_space (Optuna search ranges)
  → tiers (NORMAL/REHAB/BANNED)
  → _pinned (locked params)
```

## Phase Plan

| Phase | What | Status |
|-------|------|--------|
| 1 | BinaryOptionsController + PositionExecutor (limit buy only) | **Building** |
| 2 | Custom BinaryOptionsExecutor (7-priority exits, mint, settlement) | Specced |
| 3 | Port signal logic fully, kill standalone tracker | Planned |

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
| controller | 9 (7 pass, 2 need mock fixes) |
| order_types | 32 |
| **Total** | **192** |

## Spec Documents

All in `docs/limitless/`:
- `system-map/01-divergence-tracker.md` — signal pipeline extraction (38KB)
- `system-map/02-orchestration-execution.md` — trading logic extraction (42KB)
- `system-map/03-param-tuning.md` — Optuna/evaluator extraction (25KB)
- `system-map/04-data-layer.md` — fair value + price feeds extraction (14KB)
- `specs/SPEC-binary-options-controller.md` — controller architecture
- `specs/SPEC-module-breakdown.md` — 9-module plan + build order
- `specs/SPEC-binary-options-executor.md` — Phase 2 executor
- `specs/SPEC-execution-paths.md` — 14 paths taxonomy
- `specs/SPEC-order-types.md` — order type system
- `specs/SPEC-script-and-config.md` — top-level script + YAML
- `specs/SPEC-v2-architecture-mapping.md` — system→V2 mapping
- `V2-REFERENCE.md` — Hummingbot V2 internals (502 lines)
