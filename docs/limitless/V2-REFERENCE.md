# Hummingbot V2 Architecture Reference

Complete reference extracted from source code. For sub-agents building on V2.

---

## 1. Class Hierarchy

```
RunnableBase (async control loop)
├── ControllerBase (strategy brain)
│   ├── DirectionalTradingControllerBase (signal → position)
│   └── MarketMakingControllerBase (two-sided quoting)
└── ExecutorBase (order lifecycle manager)
    ├── PositionExecutor (entry + triple barrier + close)
    ├── OrderExecutor (single order: market/limit/chaser)
    ├── DCAExecutor
    ├── GridExecutor
    ├── TWAPExecutor
    ├── XEMMExecutor
    ├── ArbitrageExecutor
    └── LPExecutor

StrategyV2Base (the engine — owns connectors, market data, orchestrator)
└── ExecutorOrchestrator (spawns/manages all executors)
```

## 2. RunnableBase

Source: `strategy_v2/runnable_base.py`

Async control loop base class. Provides:
- `start()` / `stop()` — lifecycle
- `control_loop()` — calls `control_task()` at `update_interval`
- `_status: RunnableStatus` — NOT_STARTED → RUNNING → SHUTTING_DOWN → TERMINATED
- Both Controller and Executor inherit from this

```python
class RunnableStatus(Enum):
    NOT_STARTED = 0
    RUNNING = 1
    SHUTTING_DOWN = 2
    TERMINATED = 3
```

## 3. ControllerBase

Source: `strategy_v2/controllers/controller_base.py`

### ControllerConfigBase (Pydantic)
```python
class ControllerConfigBase(BaseClientModel):
    id: str                              # Unique controller ID (required)
    controller_name: str                 # Module path (e.g., "generic.binary_options")
    controller_type: str = "generic"     # "generic", "directional_trading", "market_making"
    total_amount_quote: Decimal = 100    # Budget (updatable)
    manual_kill_switch: bool = False     # Emergency stop (updatable)
    initial_positions: List[InitialPositionConfig] = []

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """Register trading pairs with strategy."""

    def get_controller_class(self):
        """Dynamic class loading from controller_name module."""
```

### ControllerBase
```python
class ControllerBase(RunnableBase):
    def __init__(self, config, market_data_provider, actions_queue, update_interval=1.0):
        self.config: ControllerConfigBase
        self.executors_info: List[ExecutorInfo]     # Updated by orchestrator
        self.positions_held: List[PositionSummary]  # Held positions
        self.performance_report: Optional[PerformanceReport]
        self.market_data_provider: MarketDataProvider
        self.actions_queue: asyncio.Queue           # Send actions to orchestrator
        self.processed_data: dict                   # Your custom state

    # === MUST OVERRIDE ===
    async def update_processed_data(self):
        """Fetch data, compute signals, update self.processed_data."""

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """Return Create/Stop actions based on processed_data."""

    # === CONTROL FLOW (called every tick) ===
    async def control_task(self):
        """If market_data ready: update_processed_data() → determine_executor_actions() → send_actions()"""

    # === TRADING API (built-in, use directly) ===
    def buy(self, connector_name, trading_pair, amount, price=None,
            execution_strategy=MARKET, chaser_config=None,
            triple_barrier_config=None, leverage=1, keep_position=True) -> str:
        """Creates OrderExecutor or PositionExecutor. Returns executor_id."""

    def sell(self, ...) -> str:  # Same params as buy

    def cancel(self, executor_id) -> bool:
        """Cancel active executor by ID."""

    def cancel_all(self, connector_name=None, trading_pair=None,
                   executor_filter=None) -> List[str]:
        """Cancel matching executors. Returns cancelled IDs."""

    # === QUERY API ===
    def open_orders(self, connector_name=None, trading_pair=None,
                    executor_filter=None) -> List[Dict]
    def open_positions(self, connector_name=None, trading_pair=None,
                       executor_filter=None) -> List[Dict]
    def get_active_executors(...) -> List[ExecutorInfo]
    def get_completed_executors(...) -> List[ExecutorInfo]
    def get_executors_by_type(executor_types) -> List[ExecutorInfo]
    def get_executors_by_side(sides) -> List[ExecutorInfo]
    def filter_executors(executors=None, executor_filter=None, filter_func=None) -> List[ExecutorInfo]
    def get_current_price(connector_name, trading_pair, price_type) -> Decimal

    # === OPTIONAL OVERRIDES ===
    def get_candles_config(self) -> List[CandlesConfig]   # Default: []
    def to_format_status(self) -> List[str]               # Dashboard display
    def get_custom_info(self) -> dict                     # MQTT reporting
```

### ExecutorFilter (dataclass)
All fields optional, AND logic between fields, OR within lists:
```python
@dataclass
class ExecutorFilter:
    executor_ids: Optional[List[str]]
    connector_names: Optional[List[str]]
    trading_pairs: Optional[List[str]]
    executor_types: Optional[List[str]]
    statuses: Optional[List[RunnableStatus]]
    sides: Optional[List[TradeType]]
    is_active: Optional[bool]
    is_trading: Optional[bool]
    close_types: Optional[List[CloseType]]
    controller_ids: Optional[List[str]]
    min_pnl_pct / max_pnl_pct: Optional[Decimal]
    min_pnl_quote / max_pnl_quote: Optional[Decimal]
    min_timestamp / max_timestamp: Optional[float]
    min_close_timestamp / max_close_timestamp: Optional[float]
```

### _create_order (internal — what buy/sell calls)
```python
def _create_order(self, connector_name, trading_pair, side, amount,
                  price=None, execution_strategy=MARKET, ...):
    if triple_barrier_config:
        config = PositionExecutorConfig(...)  # Full lifecycle
    else:
        config = OrderExecutorConfig(...)     # Single order
    action = CreateExecutorAction(controller_id=self.config.id, executor_config=config)
    self.actions_queue.put_nowait([action])
    return config.id
```

## 4. ExecutorBase

Source: `strategy_v2/executors/executor_base.py` (417 lines)

```python
class ExecutorBase(RunnableBase):
    def __init__(self, strategy: StrategyV2Base, connectors: List[str],
                 config: ExecutorConfigBase, update_interval=0.5):
        self.config: ExecutorConfigBase
        self.close_type: Optional[CloseType]
        self.close_timestamp: Optional[float]
        self._strategy: StrategyV2Base
        self.connectors: Dict[str, ConnectorBase]
        # Event forwarders registered for all order lifecycle events

    # === PROPERTIES ===
    @property status -> RunnableStatus
    @property is_trading -> bool      # active AND net_pnl != 0
    @property is_active -> bool       # RUNNING or NOT_STARTED
    @property is_closed -> bool       # TERMINATED
    @property executor_info -> ExecutorInfo   # Snapshot for reporting
    @property net_pnl_quote -> Decimal
    @property net_pnl_pct -> Decimal
    @property cum_fees_quote -> Decimal

    # === MUST OVERRIDE ===
    def early_stop(self, keep_position=False): raise NotImplementedError
    async def validate_sufficient_balance(self): raise NotImplementedError
    def get_net_pnl_quote(self) -> Decimal: raise NotImplementedError
    def get_net_pnl_pct(self) -> Decimal: raise NotImplementedError
    def get_cum_fees_quote(self) -> Decimal: raise NotImplementedError

    # === ORDER HELPERS ===
    def place_order(self, connector_name, trading_pair, order_type, side,
                    amount, position_action=NIL, price=NaN) -> str
    def get_price(self, connector_name, trading_pair, price_type) -> Decimal
    def get_trading_rules(self, connector_name, trading_pair) -> TradingRule
    def get_order_book(self, connector_name, trading_pair)
    def get_balance(self, connector_name, asset) -> Decimal
    def get_available_balance(self, connector_name, asset) -> Decimal
    def get_in_flight_order(self, connector_name, order_id)

    # === EVENT HANDLERS (override as needed) ===
    def process_order_created_event(self, event_tag, market, event)
    def process_order_filled_event(self, event_tag, market, event)
    def process_order_completed_event(self, event_tag, market, event)
    def process_order_canceled_event(self, event_tag, market, event)
    def process_order_failed_event(self, event_tag, market, event)

    # === OPTIONAL ===
    def get_custom_info(self) -> Dict    # Custom data for reporting
```

## 5. PositionExecutor

Source: `strategy_v2/executors/position_executor/position_executor.py` (803 lines)

Full position lifecycle: entry → barriers → exit.

### Config
```python
class PositionExecutorConfig(ExecutorConfigBase):
    type: Literal["position_executor"]
    trading_pair: str
    connector_name: str
    side: TradeType                           # BUY or SELL
    entry_price: Optional[Decimal]            # None = use market price
    amount: Decimal
    triple_barrier_config: TripleBarrierConfig = TripleBarrierConfig()
    leverage: int = 1
    activation_bounds: Optional[List[Decimal]]  # Only place when price in range
    level_id: Optional[str]
```

### TripleBarrierConfig
```python
class TripleBarrierConfig(BaseModel):
    stop_loss: Optional[Decimal]          # Percentage (0.03 = 3%)
    take_profit: Optional[Decimal]        # Percentage
    time_limit: Optional[int]             # Seconds
    trailing_stop: Optional[TrailingStop] # activation_price + trailing_delta
    open_order_type: OrderType = LIMIT
    take_profit_order_type: OrderType = MARKET
    stop_loss_order_type: OrderType = MARKET     # MUST be MARKET
    time_limit_order_type: OrderType = MARKET    # MUST be MARKET
```

### Lifecycle
```
on_start() → validate_sufficient_balance()
     ↓
control_task() loop (every 1s):
  ├── control_open_order()
  │   ├── Not placed? → check activation_bounds → place_open_order()
  │   └── Placed but out of bounds? → cancel
  ├── control_barriers() (only after open order filled + min size met)
  │   ├── control_stop_loss()     → net_pnl_pct <= -stop_loss → close
  │   ├── control_trailing_stop() → activate at threshold, close on pullback
  │   ├── control_take_profit()   → limit TP order or market close
  │   └── control_time_limit()    → is_expired → close
  └── If SHUTTING_DOWN:
      └── control_shutdown_process() → cancel opens, place close, wait for fills
```

### Key Properties
```python
entry_price → average_executed_price (after fill) or config.entry_price
close_price → average_executed_price of close order or current_market_price
trade_pnl_pct → (close - entry) / entry for BUY, inverse for SELL
net_pnl_quote → trade_pnl_quote - cum_fees_quote
is_expired → timestamp + time_limit <= current_time
end_time → timestamp + time_limit (or None)
```

### Order Tracking
```python
_open_order: Optional[TrackedOrder]
_close_order: Optional[TrackedOrder]
_take_profit_limit_order: Optional[TrackedOrder]
_failed_orders: List[TrackedOrder]
```

### CloseTypes
```python
class CloseType(Enum):
    TIME_LIMIT = 1
    STOP_LOSS = 2
    TAKE_PROFIT = 3
    EXPIRED = 4           # Already expired when started
    EARLY_STOP = 5        # Manual stop
    TRAILING_STOP = 6
    INSUFFICIENT_BALANCE = 7
    FAILED = 8            # Max retries exceeded
    COMPLETED = 9
    POSITION_HOLD = 10    # Executor done but position kept open
```

## 6. OrderExecutor

Source: `strategy_v2/executors/order_executor/order_executor.py` (362 lines)

Simpler: single order with optional limit chasing.

### Config
```python
class OrderExecutorConfig(ExecutorConfigBase):
    type: Literal["order_executor"]
    trading_pair: str
    connector_name: str
    side: TradeType
    amount: Decimal
    execution_strategy: ExecutionStrategy
    position_action: PositionAction = OPEN
    price: Optional[Decimal] = None
    chaser_config: Optional[LimitChaserConfig] = None
    leverage: int = 1
    level_id: Optional[str] = None

class ExecutionStrategy(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    LIMIT_MAKER = "limit_maker"
    LIMIT_CHASER = "limit_chaser"

class LimitChaserConfig(BaseModel):
    distance: Decimal      # Distance from best price (percentage)
    refresh_threshold: Decimal  # Re-price when price moves this much
```

### Lifecycle
```
on_start() → validate_sufficient_balance()
     ↓
control_task() loop:
  ├── control_order()
  │   ├── No order? → place_open_order()
  │   └── LIMIT_CHASER? → control_limit_chaser() → renew if price drifts
  └── If SHUTTING_DOWN:
      └── Cancel if open, hold position if filled, stop if nothing
```

PnL always returns 0 (OrderExecutor is fire-and-forget, PnL tracked at position level).

## 7. ExecutorOrchestrator

Source: `strategy_v2/executors/executor_orchestrator.py` (653 lines)

### Executor Type Registry
```python
_executor_mapping = {
    "position_executor": PositionExecutor,
    "grid_executor": GridExecutor,
    "dca_executor": DCAExecutor,
    "arbitrage_executor": ArbitrageExecutor,
    "twap_executor": TWAPExecutor,
    "xemm_executor": XEMMExecutor,
    "order_executor": OrderExecutor,
    "lp_executor": LPExecutor,
}
```

**To register a custom executor:** Add to `_executor_mapping` dict.
The `type` field in `ExecutorConfigBase` must match the key.

### Key Flow
```python
def create_executor(self, action: CreateExecutorAction):
    executor_class = self._executor_mapping[action.executor_config.type]
    executor = executor_class(strategy=self.strategy, config=action.executor_config, ...)
    executor.start()
    self.active_executors[controller_id].append(executor)
```

### What It Manages
- `active_executors: Dict[controller_id, List[ExecutorBase]]`
- `positions_held: Dict[controller_id, List[PositionHold]]`
- `cached_performance: Dict[controller_id, PerformanceReport]`
- DB persistence via `MarketsRecorder`
- Performance reporting per controller

## 8. ExecutorActions

Source: `strategy_v2/models/executor_actions.py`

```python
class ExecutorAction(BaseModel):
    controller_id: str

class CreateExecutorAction(ExecutorAction):
    executor_config: AnyExecutorConfig   # Discriminated union by type field

class StopExecutorAction(ExecutorAction):
    executor_id: str
    keep_position: bool = False

class StoreExecutorAction(ExecutorAction):
    executor_id: str
```

## 9. ExecutorInfo

Source: `strategy_v2/models/executors_info.py`

What controllers see about each executor:
```python
class ExecutorInfo(BaseModel):
    id: str
    timestamp: float
    type: str                              # "position_executor", "order_executor", etc.
    status: RunnableStatus
    config: AnyExecutorConfig
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    filled_amount_quote: Decimal
    is_active: bool
    is_trading: bool
    custom_info: Dict
    close_timestamp: Optional[float]
    close_type: Optional[CloseType]
    controller_id: Optional[str]

    @property side -> Optional[TradeType]
    @property trading_pair -> Optional[str]
    @property connector_name -> Optional[str]
```

## 10. TrackedOrder

Source: `strategy_v2/models/executors.py`

Wraps `InFlightOrder` with safe property access:
```python
class TrackedOrder:
    order_id: str
    order: Optional[InFlightOrder]

    @property average_executed_price -> Decimal
    @property executed_amount_base -> Decimal
    @property executed_amount_quote -> Decimal
    @property cum_fees_base -> Decimal
    @property cum_fees_quote -> Decimal
    @property is_done -> bool
    @property is_open -> bool
    @property is_filled -> bool
    @property fee_asset -> Optional[str]
```

## 11. PerformanceReport

```python
class PerformanceReport(BaseModel):
    realized_pnl_quote: Decimal = 0
    unrealized_pnl_quote: Decimal = 0
    unrealized_pnl_pct: Decimal = 0
    realized_pnl_pct: Decimal = 0
    global_pnl_quote: Decimal = 0
    global_pnl_pct: Decimal = 0
    volume_traded: Decimal = 0
    positions_summary: List = []
    close_type_counts: Dict[CloseType, int] = {}
```

## 12. Script (Entry Point)

Source: `scripts/v2_with_controllers.py`

```python
class V2WithControllers(StrategyV2Base):
    def __init__(self, connectors, config):
        # Loads controllers from YAML configs
        # Creates ExecutorOrchestrator
        # Sets up performance reporting

    def on_tick(self):
        # Check kill switches
        # Control max drawdown (per-controller and global)
        # Send performance reports
```

## 13. How to Add a Custom Executor

1. Create `ExecutorConfigBase` subclass with `type: Literal["your_executor"]`
2. Add `"your_executor"` to `ExecutorConfigBase.type` Literal union
3. Create `ExecutorBase` subclass implementing control_task, PnL, etc.
4. Register in `ExecutorOrchestrator._executor_mapping`
5. Add config to `AnyExecutorConfig` union in `executors_info.py`
6. Controller creates it via `CreateExecutorAction(executor_config=YourConfig(...))`

## 14. How to Add a Custom Controller

1. Create `ControllerConfigBase` subclass
2. Create `ControllerBase` subclass
3. Override `update_processed_data()` and `determine_executor_actions()`
4. Place in `controllers/` directory (auto-discovered by controller_name)
5. Create YAML config in `conf/controllers/`
6. Run via `v2_with_controllers.py` script

## 15. Key Contracts

- Executors are **self-managing** — once started, they run their own control loop
- Controllers communicate with orchestrator ONLY via `ExecutorAction` objects in `actions_queue`
- Controllers never touch executors directly — only read `executors_info` snapshots
- All PnL is tracked per-executor, aggregated per-controller by orchestrator
- DB persistence is automatic via `MarketsRecorder`
- Order events (created, filled, completed, cancelled, failed) flow through `SourceInfoEventForwarder`
