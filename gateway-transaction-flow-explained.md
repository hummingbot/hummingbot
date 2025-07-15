# Gateway Transaction Flow - Comprehensive Technical Explanation

## Overview

The Gateway transaction handling system in Hummingbot has been redesigned to eliminate retry logic and provide a cleaner, more predictable transaction flow. The system monitors blockchain transactions and updates the order database based on transaction status, with clear separation between order creation, transaction monitoring, and database updates.

## Key Components

### 1. GatewayConnector
- **Location**: `hummingbot/connector/gateway/core/gateway_connector.py`
- **Purpose**: Single entry point for all Gateway operations
- **Key Features**:
  - Manages orders via `ClientOrderTracker`
  - Uses composition pattern with trading handlers (SwapHandler, AMMHandler, CLMMHandler)
  - Handles both strategy-initiated and CLI-initiated orders

### 2. GatewayClient
- **Location**: `hummingbot/connector/gateway/core/gateway_client.py`
- **Purpose**: HTTP communication layer with Gateway service
- **Key Features**:
  - Single transaction execution (no retry logic)
  - Uses TransactionMonitor for status monitoring
  - Manages fee estimation and compute units

### 3. TransactionMonitor
- **Location**: `hummingbot/connector/gateway/core/transaction_monitor.py`
- **Purpose**: Simple polling mechanism for transaction status
- **Key Features**:
  - Polls every 2 seconds for up to 30 seconds
  - Three transaction states: PENDING (0), CONFIRMED (1), FAILED (-1)
  - Calls callbacks for state changes

### 4. SwapHandler
- **Location**: `hummingbot/connector/gateway/trading_types/swap.py`
- **Purpose**: Handles swap-specific operations
- **Key Features**:
  - Creates transaction parameters
  - Processes transaction callbacks
  - Creates TradeUpdate and OrderUpdate objects

### 5. ClientOrderTracker
- **Location**: `hummingbot/connector/client_order_tracker.py`
- **Purpose**: Tracks in-flight orders and processes updates
- **Key Features**:
  - Manages order state transitions
  - Triggers market events for UI updates
  - Maintains order cache

### 6. MarketsRecorder
- **Location**: `hummingbot/connector/markets_recorder.py`
- **Purpose**: Records orders and trades to database
- **Key Features**:
  - Listens to market events
  - Creates Order and TradeFill database records
  - Maintains market state persistence

## Transaction Flow - Step by Step

### Step 1: Order Creation

When a user initiates a swap (via strategy or CLI command):

```python
# From GatewayConnector._create_order()
order = GatewayInFlightOrder(
    client_order_id=order_id,
    exchange_order_id=self.wallet_address,  # Placeholder
    trading_pair=trading_pair,
    order_type=order_type,
    trade_type=trade_type,
    price=price,
    amount=amount,
    creation_timestamp=self.current_timestamp,
    connector_name=self.connector_name,
    method="execute-swap"
)
self._in_flight_orders[order_id] = order
```

### Step 2: Transaction Execution

The SwapHandler prepares transaction parameters and calls GatewayClient:

```python
# From SwapHandler.execute_swap()
await self.connector.client.execute_transaction(
    chain=self.connector.config.chain,
    network=self.connector.config.network,
    connector=connector_path,
    method="execute-swap",
    params=params,
    order_id=order_id,
    callback=self._transaction_callback
)
```

### Step 3: Gateway Client Processing

GatewayClient executes the transaction ONCE (no retry):

```python
# From GatewayClient.execute_transaction()
# 1. Estimate fees and compute units
# 2. Make single API call to Gateway
response = await self.request("POST", f"connectors/{connector}/{method}", data=request_params)

# 3. Start monitoring if callback provided
if callback:
    monitor = TransactionMonitor(self)
    safe_ensure_future(
        monitor.monitor_transaction(
            response=response,
            chain=chain,
            network=network,
            order_id=order_id,
            callback=callback
        )
    )
```

### Step 4: Transaction Monitoring

TransactionMonitor handles the polling logic:

```python
# From TransactionMonitor.monitor_transaction()
# 1. Notify callback of transaction hash
callback("tx_hash", order_id, tx_hash)

# 2. Check initial status
if status == STATUS_CONFIRMED:
    callback("confirmed", order_id, response)
elif status == STATUS_FAILED:
    callback("failed", order_id, response.get("message"))
elif status == STATUS_PENDING:
    # 3. Start polling loop
    await self._poll_until_complete(tx_hash, chain, network, order_id, callback)
```

### Step 5: Status Updates via Callbacks

The SwapHandler processes transaction status updates:

```python
# From SwapHandler._transaction_callback()
if event_type == "tx_hash":
    # Update order with transaction hash
    order.exchange_order_id = data

elif event_type == "confirmed":
    # Create trade update for successful transaction
    trade_update = TradeUpdate(
        trade_id=tx_result.tx_hash,
        client_order_id=order_id,
        fill_price=order.price,
        fill_base_amount=order.amount,
        ...
    )
    self.connector._process_trade_update(trade_update)

    # Mark order as filled
    order_update = OrderUpdate(
        new_state="FILLED",
        client_order_id=order_id,
        ...
    )
    self.connector._process_order_update(order_update)

elif event_type == "failed":
    # Handle failure
    self.connector._handle_order_failure(order_id, str(data))
```

## Database Interaction Flow

### Order Creation in Database

1. **Order Created Event**: When an order is placed, GatewayConnector creates an InFlightOrder
2. **Event Triggered**: `BuyOrderCreated` or `SellOrderCreated` event is triggered
3. **MarketsRecorder Listening**: `_did_create_order()` method captures the event
4. **Database Entry**: Creates Order and OrderStatus records

```python
# From MarketsRecorder._did_create_order()
order_record = Order(
    id=evt.order_id,
    config_file_path=self._config_file_path,
    strategy=self._strategy_name,
    market=market.display_name,
    symbol=evt.trading_pair,
    creation_timestamp=timestamp,
    order_type=evt.type.name,
    amount=evt.amount,
    last_status=event_type.name,
    exchange_order_id=evt.exchange_order_id
)
session.add(order_record)

order_status = OrderStatus(
    order=order_record,
    timestamp=timestamp,
    status=event_type.name
)
session.add(order_status)
```

### Trade Fill Recording

1. **Trade Update Processed**: When transaction confirms, SwapHandler creates TradeUpdate
2. **Event Triggered**: `OrderFilled` event is triggered
3. **MarketsRecorder Listening**: `_did_fill_order()` method captures the event
4. **Database Entry**: Creates TradeFill and updates Order status

```python
# From MarketsRecorder._did_fill_order()
trade_fill_record = TradeFill(
    config_file_path=self.config_file_path,
    market=market.display_name,
    symbol=evt.trading_pair,
    timestamp=timestamp,
    order_id=order_id,
    trade_type=evt.trade_type.name,
    price=evt.price,
    amount=evt.amount,
    exchange_trade_id=evt.exchange_trade_id
)
session.add(trade_fill_record)

# Update order status
order_record.last_status = event_type.name
order_record.last_update_timestamp = timestamp
```

### Order Completion

1. **Order Update Processed**: When order is marked as FILLED
2. **Event Triggered**: `BuyOrderCompleted` or `SellOrderCompleted` event
3. **MarketsRecorder Listening**: `_update_order_status()` method captures the event
4. **Database Update**: Updates Order record with final status

## Error Handling Scenarios

### 1. API Error (Transaction Submission Fails)
- **Where**: GatewayClient.execute_transaction() try/except block
- **What Happens**:
  - Exception caught immediately
  - Callback notified with "failed" event
  - Order removed from tracking
  - No database entry created (order never confirmed as created)

### 2. Transaction Failed on Chain
- **Where**: TransactionMonitor polling detects STATUS_FAILED (-1)
- **What Happens**:
  - Callback notified with "failed" event
  - SwapHandler calls `_handle_order_failure()`
  - Order marked as FAILED in database
  - OrderFailure event triggered

### 3. Transaction Timeout
- **Where**: TransactionMonitor exceeds 30-second polling limit
- **What Happens**:
  - Treated as failure
  - Callback notified: "Transaction timed out after 30 seconds"
  - Same flow as transaction failure

### 4. Polling Error
- **Where**: TransactionMonitor._poll_until_complete() exception handling
- **What Happens**:
  - Error logged but polling continues
  - Prevents single network hiccup from failing transaction
  - Will eventually timeout if persistent

## State Transitions

### Order States
```
PENDING_CREATE → OPEN → PARTIALLY_FILLED → FILLED
                  ↓           ↓              ↓
               CANCELED    CANCELED      (Terminal)
                  ↓           ↓
               FAILED      FAILED
```

### Transaction States (Gateway)
```
PENDING (0) → CONFIRMED (1)
     ↓
  FAILED (-1)
```

## Key Design Decisions

### 1. No Retry Logic
- Transactions are submitted exactly once
- Failed transactions are not retried with higher fees
- Simplifies state management and prevents fee escalation

### 2. Polling vs WebSocket
- Uses simple polling (2s intervals for 30s)
- More reliable than WebSocket for transaction monitoring
- Automatic timeout prevents infinite waiting

### 3. Callback Pattern
- Decouples transaction monitoring from order handling
- Allows different handlers to process events differently
- Maintains single responsibility principle

### 4. Database Write Timing
- Order record created immediately when order placed
- Trade fill recorded when transaction confirmed
- Status updates throughout lifecycle
- Ensures audit trail even for failed orders

## Integration Points

### 1. Strategy Integration
Strategies create orders through standard buy/sell methods:
```python
order_id = connector.buy(
    trading_pair="ETH-USDC",
    amount=Decimal("1.0"),
    order_type=OrderType.MARKET
)
```

### 2. CLI Integration
CLI commands use the same GatewayConnector:
```python
# From gateway_command.py
await connector.execute_swap(...)
```

### 3. Event System
Market events connect all components:
- Order creation → MarketsRecorder → Database
- Trade fills → MarketsRecorder → Database
- Status updates → UI notifications

## Advantages of This Design

1. **Simplicity**: Single attempt, clear success/failure paths
2. **Reliability**: No complex retry state machines
3. **Transparency**: Every transaction attempt is recorded
4. **Consistency**: All Gateway operations follow same pattern
5. **Maintainability**: Clear separation of concerns

## Summary

The Gateway transaction system follows a clear flow:
1. Order created in memory and tracked
2. Transaction submitted to blockchain (once)
3. Status monitored via polling
4. Callbacks update order status
5. Events trigger database writes

This design ensures that every order has a clear lifecycle with proper database recording at each stage, while handling errors gracefully without complex retry logic.
