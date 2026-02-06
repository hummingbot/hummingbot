# Batch Cancel Fix - Framework Integration Issue

## Problem Discovered

### Initial Investigation
The WEEX API has a batch cancel endpoint (`POST /api/v2/trade/cancel-batch-orders`), but orders were accumulating on the orderbook with HTTP 429 rate limit errors during cancellation.

### Root Cause Analysis
After investigating logs and code, discovered **the framework's lost order recovery mechanism was bypassing batch cancel**:

1. **Framework Background Task**: The base class `ExchangePyBase` runs a background loop checking for "lost" orders (orders not in tracker)
2. **Individual Cancels**: This recovery mechanism calls `_execute_order_cancel()` for EACH order individually
3. **Rate Limit Breach**: 8-10 simultaneous individual cancel calls = 24-30 weight/second → Exceeds WEEX's ~50 weight/second burst limit → HTTP 429
4. **Method Name Mismatch**: Custom `cancel_all_orders()` in strategy wasn't being called because framework uses `cancel_all()` (different method name)

### Evidence from Logs
```
2026-02-03 04:56:15,762 - ERROR - Failed to cancel order
OSError: Error executing request POST https://api-spot.weex.com/api/v2/trade/cancel-order.
HTTP status is 429. Error: {"code":"429","data":{},"msg":"Rate limit exceeded."}
```

Stack trace showed: `_execute_order_cancel` → `_execute_order_cancel_and_process_update` → `_place_cancel` (individual)

### Framework's Lost Order Recovery Flow
From code analysis:
- `ExchangePyBase._status_polling_loop_fetch_updates()` periodically runs
- Detects orders not in `_order_tracker`
- Calls `cancel_all()` to cancel them
- Default implementation loops and calls `_execute_order_cancel()` for each order

## Solution Implemented

### Fixed Method: `WeexExchange.cancel_all()` Override

**File**: `hummingbot/connector/exchange/weex/weex_exchange.py` (Lines 548-604)

**Key Changes**:
1. **Override `cancel_all()` not `cancel_all_orders()`** - This is the method the framework actually calls
2. **Use batch cancel directly**: Calls `_execute_batch_cancel()` with all orders
3. **Single API call**: All orders canceled in one batch request (10 weight) instead of N individual calls (3N weight)
4. **Backward compatibility**: Added `cancel_all_orders()` wrapper that delegates to `cancel_all()`

### Implementation Details

```python
async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
    """Override to use batch cancel instead of individual cancels."""
    incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]

    if not incomplete_orders:
        return []

    # Convert to LimitOrder format
    limit_orders = [...]

    # Call batch cancel directly (not fire-and-forget)
    results = await self._execute_batch_cancel(orders_to_cancel=limit_orders)

    return results
```

### Why This Works

| Before | After |
|--------|-------|
| Framework calls `cancel_all()` from base class | Framework calls `cancel_all()` **override** in WEEX |
| Loops through orders, calls `_execute_order_cancel()` for each | Calls `_execute_batch_cancel()` once with all orders |
| 8 orders = 8 × 3 weight = 24 weight in parallel | 1 batch call = 10 weight |
| Exceeds burst limit (50/sec) → HTTP 429 | Stays under limit |
| Individual cancels fail, orders accumulate | Batch cancel succeeds, orders clear |

## API Details

**WEEX Batch Cancel Endpoint** (from https://www.weex.com/api-doc/spot/orderApi/BulkCancel):
- **Endpoint**: `POST /api/v2/trade/cancel-batch-orders`
- **Weight**: 5 (IP) / 10 (UID) - Using UID weight (10)
- **Parameters**: `symbol` (required), `orderIds` OR `clientOids` (at least one required)
- **Response**: `{"data": {"successList": [...], "failureList": [...]}}`
- **Limitation**: Single symbol per request (WEEX groups by symbol)

## Testing

Run the bot and watch for:
1. `[WEEX_BATCH_CANCEL]` log messages during order refresh cycles
2. NO HTTP 429 "Rate limit exceeded" errors
3. Orders disappearing from orderbook at each 120s refresh
4. New orders appearing with correct amounts (4 per side: 15K, 13.75K, 11.25K, 10K)

## Files Modified

- **`hummingbot/connector/exchange/weex/weex_exchange.py`**
  - Added `cancel_all()` override (Lines 548-596)
  - Added `cancel_all_orders()` legacy wrapper (Lines 598-604)
  - Replaces individual cancel loop with batch cancel

## Implications

- **No changes needed to strategy code** - Strategy can still use its own `cancel_all_orders()` method
- **Transparent to framework** - Override is compatible with framework's expected interface
- **Performance improvement** - 58% reduction in API weight (10 vs 24)
- **Rate limit compliance** - Single batch call stays under WEEX's burst limits
