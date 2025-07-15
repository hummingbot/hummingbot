# Gateway Transaction Monitor Design (Simplified)

## Overview

This document outlines a simplified transaction monitoring system that monitors Gateway transactions and updates the orders database appropriately.

## Goals

1. Remove retry logic from gateway client
2. Create a simple handler that takes Gateway responses and monitors transactions
3. Use existing poll endpoints to check transaction status
4. Write to OrdersDB when transactions are confirmed or failed
5. Keep implementation minimal and straightforward

## Architecture Overview

### High-Level Flow
```
┌─────────────────────────┐                ┌─────────────────────────┐
│    Trading Strategy     │                │    CLI User Command     │
│  (PMM/XMM/Arbitrage)    │                │  $ gateway swap ETH...  │
│                         │                │  $ gateway wrap 1.0     │
│  strategy.buy_order()   │                │  $ gateway approve...   │
└─────────────────────────┘                └─────────────────────────┘
            │                                           │
            │ Creates order                             │ Creates order
            ▼                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         GatewayConnector                             │
│  • Single entry point for all Gateway operations                    │
│  • Manages orders via ClientOrderTracker                            │
│  • SwapHandler, AMMHandler, CLMMHandler for different ops           │
└─────────────────────────────────────────────────────────────────────┘
            │                                           ▲
            │ 1. Execute transaction                    │ 4. Status update
            ▼                                           │
┌─────────────────────────┐                ┌─────────────────────────┐
│     GatewayClient       │                │  TransactionMonitor     │
│  • HTTP communication   │                │  • NEW: Monitors tx      │
│  • No more retry logic  │                │  • Polls every 2s/30s    │
│  • Returns immediately  │                │  • Updates order status  │
└─────────────────────────┘                └─────────────────────────┘
            │                                           ▲
            │ 2. Gateway API call                       │ 3. Poll status
            ▼                                           │
┌─────────────────────────────────────────────────────────────────────┐
│                         Gateway Service                              │
│  • REST endpoints (/swap, /wrap, /approve, /poll)                   │
│  • Blockchain interaction (Ethereum, Solana, etc)                   │
│  • Returns: {txHash: "0x...", status: 0/1/-1}                      │
└─────────────────────────────────────────────────────────────────────┘
            │                                           ▲
            │ Submit to blockchain                      │ Query tx status
            ▼                                           │
┌─────────────────────────────────────────────────────────────────────┐
│                          Blockchain                                  │
│  • Transaction submitted with hash 0x123...                         │
│  • Status: PENDING → CONFIRMED or FAILED                            │
└─────────────────────────────────────────────────────────────────────┘

Final Result:
┌─────────────────────────────────────────────────────────────────────┐
│                           OrdersDB                                   │
│  • Orders table: order created → filled/failed                      │
│  • TradeFills table: swap execution details                         │
│  • OrderStatus table: state transitions                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Detailed Component Interaction (Simplified)
```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Hummingbot Process                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐                    ┌──────────────────────────┐  │
│  │ Strategy (PMM)   │                    │  CLI Command Handler     │  │
│  │                  │                    │  (gateway_command.py)    │  │
│  │ - Creates order  │                    │ - gateway swap           │  │
│  │ - Calls swap()   │                    │ - gateway wrap           │  │
│  └──────────────────┘                    └──────────────────────────┘  │
│           │                                           │                  │
│           │                                           │                  │
│           └─────────────────┬─────────────────────────┘                  │
│                             │                                            │
│                             ▼                                            │
│               ┌──────────────────────────┐                              │
│               │   GatewayConnector       │                              │
│               │   (Single Entry Point)   │                              │
│               │                          │                              │
│               │ - Handles both strategy  │                              │
│               │   and command orders     │                              │
│               │ - Uses ClientOrderTracker│                              │
│               │ - Has SwapHandler, etc   │                              │
│               └──────────────────────────┘                              │
│                             │                                            │
│                             ▼                                            │
│               ┌──────────────────────────┐                              │
│               │    TransactionMonitor    │                              │
│               │    (New component)       │                              │
│               │ - Monitors tx status     │                              │
│               │ - Updates via OT         │                              │
│               └──────────────────────────┘                              │
│                             │                                            │
│                             ▼                                            │
│               ┌──────────────────────────┐                              │
│               │  ClientOrderTracker      │                              │
│               │  - process_order_update()│                              │
│               │  - process_trade_update()│                              │
│               └──────────────────────────┘                              │
│                             │                                            │
│                             ▼                                            │
│                    ┌──────────────────┐                                 │
│                    │   OrdersDB       │                                 │
│                    │ - Orders table   │                                 │
│                    │ - TradeFills     │                                 │
│                    │ - OrderStatus    │                                 │
│                    └──────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Gateway Service                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────────┐   │
│  │   REST API   │───▶│ Route Handler   │───▶│ Chain Connector      │   │
│  │  Endpoints   │    │ (swap/wrap/etc) │    │ (ETH/SOL)           │   │
│  └──────────────┘    └─────────────────┘    └──────────────────────┘   │
│         ▲                                              │                 │
│         │                                              ▼                 │
│         │                                     ┌──────────────────────┐   │
│         │                                     │    Blockchain        │   │
│         │                                     │    Transaction       │   │
│         │                                     └──────────────────────┘   │
│         │                                                                │
│         └────────────────── /poll endpoint ──────────────────────────────┤
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Transaction State Flow
```
                            Gateway Response
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   Check Status      │
                        └─────────────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                ▼                  ▼                  ▼
         Status = 1         Status = 0         Status = -1
         (CONFIRMED)        (PENDING)           (FAILED)
                │                  │                  │
                ▼                  ▼                  ▼
    ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Write Success    │  │Start Polling │  │ Write Failed │
    │ to OrdersDB      │  │   Task       │  │ to OrdersDB  │
    └──────────────────┘  └──────────────┘  └──────────────┘
                                   │
                                   ▼
                          ┌──────────────┐
                          │ Poll every 2s│
                          │ for 30s max  │
                          └──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
              Status change                   Timeout
              (1 or -1)                      (30 sec)
                    │                             │
                    ▼                             ▼
           ┌──────────────┐              ┌──────────────┐
           │Update OrdersDB│              │Mark as FAILED│
           │(SUCCESS/FAIL)│              │in OrdersDB   │
           └──────────────┘              └──────────────┘
```

## Simplified Design

### Core Concept
When any gateway command (wrap, approve, swap) is executed:
1. Pass the Gateway response and route to the transaction handler
2. If already succeeded (status 1), write to OrdersDB immediately as SUCCESS
3. If already failed (status -1), write to OrdersDB immediately as FAILURE
4. If pending (status 0, 2, or 3), start monitoring for ~30 seconds
5. Update OrdersDB when status changes or on timeout

### Transaction Status (Using Existing Constants)
```typescript
// From Gateway codebase
export enum TransactionStatus {
  PENDING = 0,
  CONFIRMED = 1,
  FAILED = -1,
}
```

- **PENDING (0)**: Transaction submitted but not confirmed
- **CONFIRMED (1)**: Transaction confirmed and succeeded
- **FAILED (-1)**: Transaction failed (including timeout)

## Implementation

### Core Changes

#### 1. Remove Retry Logic from GatewayClient
```python
# In gateway_client.py - REMOVE this method entirely
async def _execute_with_retry(...):
    # DELETE ALL RETRY LOGIC
    pass

# Simplify execute_transaction to:
async def execute_transaction(
    self,
    chain: str,
    network: str,
    connector: str,
    method: str,
    params: Dict[str, Any],
    order_id: Optional[str] = None,
    callback: Optional[Callable] = None
) -> str:
    """Execute transaction ONCE and return immediately."""
    # Just make the API call
    response = await self.api_request(
        method="POST",
        path_url=f"{connector}/{method}",
        params=params
    )

    # Return empty string to maintain compatibility
    # The callback will handle the actual transaction
    if callback:
        asyncio.create_task(
            self._monitor_transaction(
                response, chain, network, order_id, callback
            )
        )

    return ""

async def _monitor_transaction(
    self,
    response: Dict,
    chain: str,
    network: str,
    order_id: str,
    callback: Callable
):
    """New method that uses TransactionLandingHandler."""
    tx_handler = TransactionLandingHandler(
        gateway_client=self,
        chain=chain,
        network=network
    )

    await tx_handler.monitor_transaction(
        response=response,
        order_id=order_id,
        callback=callback
    )
```

#### 2. Add Simple TransactionLandingHandler

```python
# New file: hummingbot/connector/gateway/core/transaction_landing_handler.py
class TransactionLandingHandler:
    """Simple handler that monitors transaction status."""

    def __init__(self, gateway_client, chain: str, network: str):
        self._client = gateway_client
        self._chain = chain
        self._network = network

    async def monitor_transaction(
        self,
        response: Dict[str, Any],
        order_id: str,
        callback: Callable
    ):
        """Monitor a transaction until confirmed/failed/timeout."""
        tx_hash = response.get("txHash", "")
        status = response.get("status", 0)

        if not tx_hash:
            return

        # Notify callback of tx hash
        if callback:
            callback("tx_hash", order_id, tx_hash)

        # If already done, notify and return
        if status == 1:  # CONFIRMED
            if callback:
                callback("confirmed", order_id, response)
            return
        elif status == -1:  # FAILED
            if callback:
                callback("failed", order_id, response.get("message", "Transaction failed"))
            return

        # Status is PENDING (0) - start polling
        await self._poll_until_complete(tx_hash, order_id, callback)

    async def _poll_until_complete(
        self,
        tx_hash: str,
        order_id: str,
        callback: Callable
    ):
        """Poll transaction status for up to 30 seconds."""
        poll_interval = 2  # seconds
        max_attempts = 15  # 30 seconds total

        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)

            try:
                # Call poll endpoint
                poll_response = await self._client.get_transaction_status(
                    self._chain,
                    self._network,
                    tx_hash
                )

                status = poll_response.get("status", 0)

                if status == 1:  # CONFIRMED
                    if callback:
                        callback("confirmed", order_id, poll_response)
                    return
                elif status == -1:  # FAILED
                    if callback:
                        callback("failed", order_id, poll_response.get("message", "Transaction failed"))
                    return

                # Still pending, continue polling

            except Exception as e:
                # Log error but continue polling
                pass

        # Timeout - treat as failure
        if callback:
            callback("failed", order_id, "Transaction timed out after 30 seconds")

### How It All Works Together

The key insight is that **everything already exists** - we just need to change the retry behavior:

1. **Current Flow (with retry)**:
   ```
   GatewayClient.execute_transaction()
   └── _execute_with_retry()  ← REMOVE THIS
       └── Retries with higher fees
       └── Monitors until complete
   ```

2. **New Flow (no retry)**:
   ```
   GatewayClient.execute_transaction()
   └── API call (once)
   └── TransactionLandingHandler.monitor_transaction()  ← ADD THIS
       └── Polls status every 2s for 30s
       └── Calls existing callbacks
   ```

3. **Existing Components We Keep**:
   - `GatewayConnector` - Main connector class
   - `SwapHandler` - Handles swap operations
   - `ClientOrderTracker` - Writes to database
   - Callback mechanism - Updates order status

4. **What Actually Changes**:
   - Remove `_execute_with_retry()` from GatewayClient
   - Add `TransactionLandingHandler` for simple polling
   - Everything else stays exactly the same

### NO Need To:
- Create new interfaces
- Change how strategies work
- Modify gateway_command.py significantly
- Change database schema
- Create new order types

The beauty is in the simplicity - we're just replacing the retry logic with a simple polling mechanism.

### Usage Examples (Nothing Changes!)

#### For Strategy Developers:
```python
# Your strategy code doesn't change at all!
class MyStrategy(StrategyBase):
    async def execute_buy_order(self, amount: Decimal, price: Decimal):
        """Works exactly the same as before."""
        order = self.buy_with_specific_market(
            market_pair=self.market_info,
            amount=amount,
            price=price,
            order_type=OrderType.LIMIT
        )
        # That's it! Transaction monitoring happens automatically
```

#### For CLI Users:
```bash
# Commands work exactly the same as before!
>>> gateway swap ethereum mainnet uniswap ETH USDC 1.0
# Transaction is submitted once and monitored automatically

>>> gateway wrap ethereum mainnet 1.0
# No more retry spam - just clean monitoring

>>> gateway approve ethereum mainnet USDC 0x123...
# Works as expected
```

## Implementation Steps

1. **Remove retry logic from GatewayClient**
   - Remove `_execute_with_retry` method
   - Simplify `execute_transaction` to just send request once
   - Keep existing callback mechanism for compatibility

2. **Create TransactionLandingHandler class**
   - Add to `hummingbot/connector/gateway/core/transaction_landing_handler.py`
   - Initialize with ClientOrderTracker reference
   - Integrate into existing callback flow

3. **Update GatewayConnector & Handlers**
   - Modify SwapHandler to use new transaction landing
   - Ensure all operations create proper InFlightOrders
   - Remove duplicate retry logic

4. **Update gateway_command.py**
   - Use GatewayConnector for all operations (not direct API calls)
   - Create orders for command-initiated transactions
   - Leverage existing connector infrastructure

5. **Test with different scenarios**
   - Strategy-initiated swaps
   - Command-initiated swaps/wraps/approvals
   - Immediate confirmation (status 1)
   - Pending then confirmed
   - Failed transactions
   - Timeout scenarios

## Data Flow Example

### What Happens When You Execute a Transaction
```
1. User initiates transaction (strategy or CLI):
   ┌─────────────────┐
   │ "swap ETH→USDC" │
   └─────────────────┘
           │
           ▼
2. GatewayConnector creates order and calls GatewayClient:
   execute_transaction(chain="ethereum", method="executeSwap", ...)
           │
           ▼
3. GatewayClient makes ONE API call (no retry):
   POST /ethereum/executeSwap
           │
           ▼
4. Gateway returns immediately:
   {
     "txHash": "0x123...",
     "status": 0  // PENDING
   }
           │
           ▼
5. TransactionLandingHandler starts monitoring:

   t=0s:   callback("tx_hash", order_id, "0x123...")
   t=2s:   Poll → status: 0 (still pending)
   t=4s:   Poll → status: 0 (still pending)
   t=6s:   Poll → status: 1 (CONFIRMED!)
           callback("confirmed", order_id, {...})
           │
           ▼
6. Existing callbacks update database:
   - SwapHandler processes confirmation
   - Creates TradeUpdate → OrderFilledEvent
   - Creates OrderUpdate → Order completed
   - ClientOrderTracker writes to OrdersDB
           │
           ▼
7. Result in database:
   Orders table:      Order FILLED ✓
   TradeFills table:  Swap recorded ✓
   OrderStatus table: State history ✓
```

### Key Point: The ONLY Change
```
OLD: GatewayClient._execute_with_retry()
     └── Retries transaction with higher fees
     └── Complex fee escalation logic
     └── Can spam the blockchain

NEW: TransactionLandingHandler.monitor_transaction()
     └── Just polls for status
     └── No retries
     └── Clean and simple
```

## Benefits

1. **Simplicity**: No complex state management or caching
2. **Consistency**: All gateway transactions handled the same way
3. **Reliability**: Direct OrdersDB updates when confirmed
4. **Minimal Changes**: Works with existing infrastructure
5. **No External Dependencies**: No Redis, no complex handlers

## Key Design Principles

```
┌─────────────────────────────────────────────────────┐
│                  Design Principles                    │
├─────────────────────────────────────────────────────┤
│                                                       │
│  1. Single Responsibility                             │
│     └─▶ Handler only monitors and updates            │
│                                                       │
│  2. Use Existing Infrastructure                       │
│     └─▶ ClientOrderTracker, poll endpoints           │
│                                                       │
│  3. Fail-Safe Defaults                               │
│     └─▶ Timeout = FAILED, no infinite polling        │
│                                                       │
│  4. Stateless Operations                              │
│     └─▶ Each poll is independent                     │
│                                                       │
│  5. Clear State Transitions                          │
│     └─▶ PENDING → CONFIRMED or FAILED only           │
│                                                       │
└─────────────────────────────────────────────────────┘
```

## API Design

### New Endpoints

#### 1. Submit Transaction
```typescript
POST /transactions/submit
{
  orderId: string;
  chain: string;
  transaction: {
    // Chain-specific transaction data
  };
  callbacks?: {
    onHash?: string;
    onConfirmed?: string;
    onFailed?: string;
  };
}
```

#### 2. Transaction Status
```typescript
GET /transactions/:txHash/status
Response: {
  txHash: string;
  orderId: string;
  chain: string;
  status: TransactionStatus;
  confirmations: number;
  gasUsed?: string;
  effectiveGasPrice?: string;
  blockNumber?: number;
  error?: string;
}
```

### Modified Endpoints

#### Execute Swap
- Return transaction handle instead of waiting for confirmation
- Let TransactionManager handle monitoring and callbacks

## Migration Strategy

1. Implement new system alongside existing code
2. Add feature flag to enable new transaction handling
3. Migrate connectors one by one
4. Deprecate old callback mechanism
5. Remove legacy code after validation

## Benefits

1. **Consistency**: Uniform transaction handling across all chains
2. **Reliability**: Better error handling and retry mechanisms
3. **Visibility**: Clear transaction lifecycle tracking
4. **Extensibility**: Easy to add new chains or transaction types
5. **Integration**: Seamless connection to Hummingbot's order tracking

## Implementation Summary

### Key Design Decisions

1. **Centralized Management**: Single TransactionManager instance handles all transaction monitoring across chains
2. **Chain Abstraction**: Chain-specific handlers implement common interface for portability
3. **Async Monitoring**: Non-blocking transaction submission with callback-based updates
4. **Order Integration**: Direct integration with ClientOrderTracker via OrderUpdate/TradeUpdate events
5. **Existing Infrastructure**: Leverages existing gateway client retry logic and callback mechanisms

### Benefits Over Current System

1. **Unified Transaction Handling**: Consistent behavior across all chains
2. **Better Error Recovery**: Centralized timeout and retry policies
3. **Improved Monitoring**: Dedicated monitoring loops with configurable intervals
4. **Enhanced Debugging**: Transaction state tracking and detailed error categorization
5. **Future Extensibility**: Easy to add new chains or transaction types

### Development Roadmap

#### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Implement TransactionManager singleton
- [ ] Define ITransactionHandler interface
- [ ] Create transaction state machine
- [ ] Add basic monitoring loops

#### Phase 2: Chain Handlers (Week 2-3)
- [ ] Implement EthereumTransactionHandler
- [ ] Implement SolanaTransactionHandler
- [ ] Add transaction parsing logic
- [ ] Test with mainnet/testnet

#### Phase 3: Integration (Week 3-4)
- [ ] Update execute swap endpoints
- [ ] Integrate with gateway command
- [ ] Connect to ClientOrderTracker
- [ ] Update callback mechanisms

#### Phase 4: Testing & Refinement (Week 4-5)
- [ ] Unit tests for all components
- [ ] Integration tests with mock chains
- [ ] Performance testing
- [ ] Documentation updates

### Next Steps

1. **Review this design document** with the team
2. **Discuss and resolve key questions** listed above
3. **Create GitHub issues** for each development task
4. **Set up development branch** for implementation
5. **Begin Phase 1** implementation

### Additional Considerations

1. **Monitoring & Metrics**: Consider adding Prometheus metrics for transaction states
2. **Persistence**: Evaluate Redis/SQLite for transaction state persistence
3. **WebSocket Support**: Future enhancement for real-time transaction updates
4. **Multi-Transaction Orders**: Support for complex operations (approve + swap)
5. **Gas Optimization**: Implement intelligent gas price recommendations
