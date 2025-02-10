# Executor Core Components Interaction

## Component Overview

### ExecutorFactory

The ExecutorFactory serves as the central registration and creation point for executors. It maintains a registry of executor types and their corresponding configurations, and handles the instantiation of new executors.

```python
class ExecutorFactory:
    _registry: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorBaseFactoryProtocol]] = {}
    _update_types: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorUpdateBase]] = {}

    @classmethod
    def register_executor(cls, config_type: Type[ExecutorConfigFactoryProtocol]) -> Callable:
        """Decorator for registering executor implementations"""
```

Key responsibilities:
- Executor type registration
- Configuration validation
- Executor instantiation
- Update type management

### ExecutorOrchestrator

The ExecutorOrchestrator manages the lifecycle of executors and coordinates their actions. It maintains the state of active and archived executors and tracks their performance.

```python
class ExecutorOrchestrator:
    def __init__(self, strategy: ScriptStrategyBase, executors_update_interval: float = 1.0):
        self.active_executors = {}
        self.archived_executors = {}
        self.cached_performance = {}
```

Key responsibilities:
- Executor lifecycle management
- Action processing
- Performance tracking
- Position management

### Configuration System

The configuration system uses Pydantic models to define and validate executor configurations:

```python
class ExecutorConfigBase(BaseModel):
    id: str
    timestamp: int
    connector_name: str
    trading_pair: str
```

## Interaction Patterns

### 1. Executor Registration

The registration flow occurs when a new executor type is defined:

```python
@ExecutorFactory.register_executor(ProgressiveExecutorConfig)
class ProgressiveExecutor(ExecutorBase):
    """Progressive executor implementation"""
```

This registration:
1. Validates the config type
2. Adds the executor to the registry
3. Associates update types
4. Enables factory creation

### 2. Executor Creation Flow

When a new executor is needed:

1. Strategy creates an action:
```python
action = CreateExecutorAction(
    controller_id="my_controller",
    executor_config=config,
)
```

2. Orchestrator processes the action:
```python
def execute_action(self, action: ExecutorAction):
    if isinstance(action, CreateExecutorAction):
        executor = ExecutorFactory.create_executor(
            self.strategy, 
            action.executor_config,
            self.executors_update_interval,
        )
        self.active_executors[action.controller_id].append(executor)
```

3. Factory creates the executor:
```python
@classmethod
def create_executor(cls, strategy, config, update_interval):
    executor_cls = cls._registry[type(config)]
    return executor_cls(strategy, config, update_interval)
```

### 3. Lifecycle Management

The orchestrator manages executor lifecycles through several phases:

1. **Initialization**:
```python
executor.start()
self.active_executors[controller_id].append(executor)
```

2. **Monitoring**:
```python
def generate_performance_report(self, controller_id: str) -> PerformanceReport:
    report = deepcopy(self.cached_performance[controller_id])
    for executor in self.active_executors[controller_id]:
        report.update(executor.executor_info)
```

3. **Termination**:
```python
def stop_executor(self, action: StopExecutorAction):
    executor = self.get_executor(action.controller_id, action.executor_id)
    executor.stop()
    self.archive_executor(executor)
```

### 4. Update Flow

Updates to running executors follow this pattern:

1. Create update action:
```python
action = UpdateExecutorAction(
    controller_id="my_controller",
    executor_id="exec_1",
    update_data=update_config,
)
```

2. Validate and apply:
```python
def update_executor(self, action: UpdateExecutorAction):
    executor = self.get_executor(action.controller_id, action.executor_id)
    update_type = ExecutorFactory.get_update_type(type(executor.config))
    if isinstance(action.update_data, update_type):
        executor.update_live(action.update_data)
```

## State Management

The system maintains several important state collections:

1. **Factory Registry**:
- Executor types
- Config mappings
- Update types

2. **Orchestrator State**:
- Active executors
- Archived executors
- Performance cache
- Position tracking

3. **Executor State**:
- Configuration
- Order tracking
- Performance metrics

## Best Practices

1. **Registration**:
- Always use the decorator pattern for registration
- Validate config types at registration time
- Provide clear update types

2. **Creation**:
- Use the factory exclusively for executor creation
- Validate configurations before creation
- Handle creation failures gracefully

3. **Lifecycle**:
- Monitor executor status regularly
- Cache performance metrics efficiently
- Clean up resources on termination

4. **Updates**:
- Validate update types strictly
- Handle update failures gracefully
- Maintain consistency in state

## Error Handling

The system implements various error handling strategies:

1. **Configuration Validation**:
```python
@root_validator
def validate_config(cls, values):
    """Validate configuration values"""
    return values
```

2. **Creation Failures**:
```python
try:
    executor = factory.create_executor(config)
except ValueError as e:
    logger.error(f"Failed to create executor: {e}")
```

3. **Update Failures**:
```python
def update_live(self, update_data):
    try:
        self.apply_update(update_data)
    except Exception as e:
        self.logger().error(f"Update failed: {e}")
```

## Performance Considerations

1. **State Management**:
- Use efficient data structures
- Implement caching strategies
- Regular cleanup of archived data

2. **Resource Usage**:
- Monitor memory usage
- Implement resource limits
- Regular garbage collection

3. **Concurrency**:
- Handle async operations properly
- Implement proper locking
- Manage shared resources

## Extension Points

The system can be extended through:

1. New executor implementations
2. Custom configuration types
3. Additional update types
4. Enhanced monitoring capabilities