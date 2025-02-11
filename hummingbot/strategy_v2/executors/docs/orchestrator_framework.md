# Executor Framework Documentation

## Overview

The Executor Framework provides a flexible and robust system for managing trading execution in the Hummingbot platform. It consists of several key components that work together to handle order execution, position management, and risk control.

### Key Components

1. **ExecutorFactory**: Responsible for creating and registering executor instances
2. **ExecutorOrchestrator**: Manages the lifecycle of executors and coordinates actions
3. **ExecutorAction**: Defines the actions that can be performed on executors
4. **ExecutorBase**: Base class providing common executor functionality
5. **ProgressiveExecutor**: Specialized executor implementation for progressive trading strategies

## Architecture

The framework follows a modular architecture with clear separation of concerns:

![Executor Framework Architecture](./assets/orchestrator-framework.svg)

### Component Responsibilities

#### ExecutorFactory
- Registers executor implementations
- Creates executor instances from configurations
- Manages executor type registry
- Handles executor updates

#### ExecutorOrchestrator
- Coordinates executor lifecycle
- Processes executor actions
- Manages active and archived executors
- Tracks performance metrics
- Handles position management

#### ExecutorAction
- Defines available actions (create, stop, store, update)
- Validates action parameters
- Provides factory methods for action creation

#### ExecutorBase
- Implements core executor functionality
- Manages order tracking
- Handles state management
- Provides extension points

#### ProgressiveExecutor
- Implements progressive trading strategy
- Manages barrier controls
- Handles position entry/exit
- Implements risk management

## Lifecycle

The executor lifecycle follows a well-defined state machine:

![Executor Lifecycle](assets/executor-lifecycle.svg)

### State Transitions

1. **Created**: Initial state after factory creation
2. **Running**: Active state during normal operation
3. **ShuttingDown**: Transitional state during cleanup
4. **Terminated**: Final state after successful completion
5. **Failed**: Final state after error condition

### Control Flow

The executor framework implements a control loop pattern:

```python
async def control_task(self):
    if self.status == RunnableStatus.RUNNING:
        self.control_open_order_process()
        self.control_barriers()
    elif self.status == RunnableStatus.SHUTTING_DOWN:
        await self.control_shutdown_process()
    self.evaluate_max_retries()
```

## Configuration

Executors are configured using Pydantic models:

```python
class ProgressiveExecutorConfig(PositionExecutorConfig):
    type = "progressive_executor"
    triple_barrier_config: YieldTripleBarrierConfig
```

### Barrier Configuration

Triple barrier configuration includes:

- Stop loss
- Take profit
- Time limit
- Trailing stop

## Usage Example

Basic usage pattern:

```python
# Create executor config
config = ProgressiveExecutorConfig(
    trading_pair="BTC-USDT",
    side=TradeType.BUY,
    amount=Decimal("0.1"),
    entry_price=Decimal("50000"),
    triple_barrier_config=YieldTripleBarrierConfig(
        stop_loss=Decimal("0.02"),
        take_profit=Decimal("0.05"),
        time_limit=3600,
    )
)

# Create action
action = CreateExecutorAction(
    controller_id="my_controller",
    executor_config=config,
)

# Execute via orchestrator
orchestrator.execute_action(action)
```

## Performance Monitoring

The framework provides comprehensive performance tracking:

```python
# Get performance report
report = orchestrator.generate_performance_report(controller_id)

# Access metrics
print(f"PnL: {report.global_pnl_quote}")
print(f"Volume: {report.volume_traded}")
print(f"Win Rate: {report.win_rate}")
```

## Error Handling

The framework implements robust error handling:

1. Retry mechanism for failed orders
2. Validation of configurations
3. State validation during transitions
4. Balance checks before execution

## Best Practices

1. Always use the factory pattern for executor creation
2. Implement proper cleanup in shutdown
3. Monitor performance metrics
4. Handle edge cases in barrier logic
5. Validate configurations thoroughly

## Extension Points

The framework can be extended through:

1. New executor implementations
2. Custom action types
3. Additional performance metrics
4. Enhanced barrier controls

## Database Integration

Position and executor data is persisted using SQLAlchemy:

```python
def store_executor(self, executor: ExecutorBase):
    markets_recorder = MarketsRecorder.get_instance()
    markets_recorder.store_executor(executor)
```

## API Reference

[Detailed API documentation here]

## Contributing

[Contribution guidelines here]