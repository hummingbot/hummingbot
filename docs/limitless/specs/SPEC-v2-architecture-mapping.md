# Hummingbot V2 Architecture Mapping for BinaryOptionsController

## V2 Architecture Overview

### Hierarchy
```
Script (v2_with_controllers.py)
  └── StrategyV2Base — the main strategy engine
        ├── ExecutorOrchestrator — spawns/manages all executors
        │     ├── PositionExecutor — entry + triple barrier (SL/TP/time) + trailing stop
        │     ├── OrderExecutor — single order (market/limit/chaser)
        │     ├── DCAExecutor — dollar cost averaging
        │     ├── GridExecutor — grid trading
        │     ├── TWAPExecutor — time-weighted average price
        │     ├── XEMMExecutor — cross-exchange market making
        │     ├── ArbitrageExecutor — arb between exchanges
        │     └── LPExecutor — liquidity providing
        └── Controllers (loaded from YAML configs)
              ├── DirectionalTradingControllerBase — signal → position
              ├── MarketMakingControllerBase — two-sided quoting
              └── ControllerBase (generic) — anything custom
```

### Control Flow (every tick)
1. `StrategyV2Base.on_tick()` → calls each controller
2. Controller `control_task()`:
   a. `update_processed_data()` — fetch market data, compute signals
   b. `determine_executor_actions()` — return list of Create/Stop actions
3. `ExecutorOrchestrator.execute_actions()` — spawns/stops executors
4. Each Executor runs its own `control_loop()` at 0.5s intervals
   - Checks barriers (SL, TP, time limit, trailing stop)
   - Places/cancels orders via connector
   - Reports PnL back to controller

### What Controllers Get For Free
- **Lifecycle management** — start/stop/restart, status reporting
- **Executor tracking** — `executors_info` list with PnL, status, filters
- **Market data provider** — candles, prices, orderbooks
- **Config system** — Pydantic validated, YAML serializable, hot-updatable fields
- **Performance reporting** — global PnL, per-controller PnL, MQTT publishing
- **Dashboard** — automatic via performance reports
- **Drawdown protection** — max global/controller drawdown in script
- **Backtesting** — executor simulators for position/DCA strategies

### What Controllers Must Implement
1. `update_processed_data()` — compute signals, features
2. `determine_executor_actions()` — return Create/Stop executor actions
3. Config class extending `ControllerConfigBase`

### Key Abstractions

#### ControllerConfigBase
- `id` — unique controller ID
- `controller_name` — matches module path
- `total_amount_quote` — budget for this controller
- `manual_kill_switch` — emergency stop
- `update_markets()` — register trading pairs with strategy

#### DirectionalTradingControllerConfigBase (extends ControllerConfigBase)
- `connector_name` — which exchange
- `trading_pair` — what to trade
- `max_executors_per_side` — concurrency limit
- `cooldown_time` — seconds between signals
- `leverage` — for perps
- `stop_loss` / `take_profit` / `time_limit` — triple barrier defaults
- `trailing_stop` — activation_price + trailing_delta
- `triple_barrier_config` property — builds TripleBarrierConfig

#### PositionExecutorConfig
- `trading_pair`, `connector_name`, `side` (BUY/SELL)
- `entry_price`, `amount`
- `triple_barrier_config` — TripleBarrierConfig
- `leverage`, `activation_bounds`

#### TripleBarrierConfig
- `stop_loss` — decimal percentage (0.03 = 3%)
- `take_profit` — decimal percentage
- `time_limit` — seconds
- `trailing_stop` — TrailingStop(activation_price, trailing_delta)
- Order types for each barrier (MARKET/LIMIT)

#### ExecutorActions
- `CreateExecutorAction(controller_id, executor_config)` — spawn executor
- `StopExecutorAction(controller_id, executor_id)` — kill executor
- `StoreExecutorAction(controller_id, executor_id)` — persist to DB

## Mapping Our System → V2

### What Maps Cleanly

| Our Concept | V2 Equivalent |
|---|---|
| Divergence signal | `update_processed_data()` → `processed_data["signal"]` |
| Entry decision | `determine_executor_actions()` → CreateExecutorAction |
| Stop loss | TripleBarrierConfig.stop_loss |
| Time limit (expiry) | TripleBarrierConfig.time_limit |
| Cooldown between trades | `cooldown_time` config |
| Max concurrent positions | `max_executors_per_side` |
| Position PnL tracking | Free via ExecutorInfo |
| Budget management | `total_amount_quote` |

### What Needs Custom Implementation

| Our Concept | Why Custom |
|---|---|
| **Market selection** | V2 assumes single `trading_pair`; we need to dynamically select from 25+ markets each cycle |
| **Binary outcome** | V2 TripleBarrier is price-based %; binary options resolve to 0 or 1, not price movement |
| **Token minting** | `splitPosition` (USDC→YES+NO) has no V2 equivalent |
| **Position redemption** | `redeemPositions` after settlement — no V2 equivalent |
| **Limit order as maker** | V2 defaults to taker; we want LIMIT_MAKER for MM rebates |
| **Expiry-aware exit** | Must exit before market settles, not just time_limit |
| **ATM detection** | Current price vs strike price — custom signal logic |
| **Multi-market** | Simultaneously watching N markets, trading the best opportunity |

### Architecture Decision: Generic Controller (NOT DirectionalTrading)

DirectionalTradingControllerBase is too rigid:
- Single `connector_name` + `trading_pair` (we need dynamic multi-market)
- Assumes perpetual-style price-based PnL
- TripleBarrier percentages don't map to binary outcomes

**We should extend `ControllerBase` directly** (like `full_trading_example.py`), giving us:
- Full control over `update_processed_data()` and `determine_executor_actions()`
- Can manage multiple markets simultaneously
- Can implement binary-specific PnL logic
- Still get all the executor tracking, performance reporting, and lifecycle for free

### Executor Decision: PositionExecutor With Custom Close Logic

The `PositionExecutor` already handles:
- Entry orders (market/limit/chaser)
- Triple barrier (SL/TP/time)
- Trailing stop
- PnL tracking

What we'd override/customize:
- `time_limit` = seconds until market expiry (not arbitrary timeout)
- `stop_loss` = max loss in USDC terms (not % of entry price — binary option costs $0.01-$0.99)
- Custom close: if price reverses toward strike, exit early via SELL order on CLOB

We can likely use PositionExecutor AS-IS for Phase 1 by mapping:
- Binary YES token = "asset" priced 0-1
- Buy YES at 0.40 → TP at 0.80 (0.40/0.40 = 100%), SL at 0.20 (0.20/0.40 = 50%)
- Time limit = seconds until 2 minutes before expiry

Phase 2: Custom `BinaryOptionsExecutor` for:
- Reversal close (exit when price crosses back through strike)
- Token minting + two-sided quoting for MM rebates
- Settlement handling (redeem after expiry)

## Implementation Plan

### Phase 1: BinaryOptionsController (Generic Controller, Limit-First)

```
controllers/
  generic/
    binary_options/
      __init__.py
      binary_options_controller.py   # ControllerBase subclass
```

Config:
- `connector_name` = "limitless"
- `asset_whitelist` = ["BTC", "ETH", "SOL"]
- `max_concurrent_positions` = 3
- `position_size_usdc` = 1.0 (per trade)
- `min_signal_strength` = 0.5
- `time_buffer_seconds` = 120 (exit 2 min before expiry)
- `taker_threshold_seconds` = 300 (only go taker if <5 min to expiry)
- `taker_signal_threshold` = 0.8 (strong signal required for taker)
- `limit_price_offset` = 0.01 (1¢ better than best bid for priority)

**Limit-first execution model:**
Every entry and exit defaults to LIMIT MAKER orders. This earns:
1. LP Rewards — every minute while order rests on book
2. Maker Rebates — 20% of taker fee when filled

`update_processed_data()`:
1. Fetch active markets from connector
2. Filter: asset whitelist, hourly only, >10 min to expiry
3. For each market: compute ATM score (how close to strike)
4. For each ATM market: compute directional signal (our divergence/beta logic)
5. Rank by signal_strength × ATM_score
6. Track resting order LP reward accumulation time

`determine_executor_actions()`:
1. Check active executors count + cooldown
2. If best signal > threshold AND budget available:
   - Time to expiry > `taker_threshold_seconds`:
     → LIMIT BUY YES/NO at best bid + offset (maker entry)
   - Time to expiry < `taker_threshold_seconds` AND signal > `taker_signal_threshold`:
     → MARKET BUY YES/NO (taker fallback, rare)
   - Else: SKIP (not enough edge or time)
3. Exits:
   - Approaching expiry (< time_buffer): Limit SELL or hold to settlement
   - Reversal signal: Limit SELL (if time), Market SELL (if urgent)
   - Strong unrealized gain: Limit SELL to lock profit + earn exit rebate

### Phase 2: Mint Paths + Delta Neutral
- MINT + SELL opposite side for capital-efficient directional entries
- MINT + SELL BOTH for delta neutral income (when spread > $1)
- Two-sided order management (linked YES+NO)
- Inventory tracking across minted pairs
- Post-settlement redemption automation

### Phase 3: Adaptive Execution + Signal Integration
- Dynamic path selection: limit vs mint vs market based on orderbook + time + signal
- Port divergence tracker signal logic INTO controller's `update_processed_data()`
- Use Hummingbot's candles feed for price data
- Smart order routing with cost model per execution path

## File Structure
```
hummingbot/
  connector/exchange/limitless/    # ✅ DONE
  strategy_v2/                     # Framework (don't touch)

controllers/
  generic/
    binary_options/                 # NEW — Phase 1
      __init__.py
      binary_options_controller.py

scripts/
  v2_binary_options.py             # NEW — entry point script (like v2_with_controllers.py)

conf/controllers/
  binary_options_btc.yml           # NEW — per-asset configs
```

## Key V2 Methods We'll Use

```python
# From ControllerBase
self.buy(connector_name, trading_pair, amount, price, execution_strategy, triple_barrier_config)
self.sell(connector_name, trading_pair, amount, price, execution_strategy)
self.cancel(executor_id)
self.cancel_all()
self.open_orders()
self.open_positions()
self.get_active_executors()
self.get_completed_executors()
self.filter_executors(executor_filter)
self.get_current_price(connector_name, trading_pair, price_type)

# From MarketDataProvider
self.market_data_provider.get_price_by_type()
self.market_data_provider.get_candles_df()
self.market_data_provider.time()
self.market_data_provider.ready
```
