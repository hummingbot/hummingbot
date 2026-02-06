# Batch Cancel Investigation & Fix

## Problem Summary
Orders were accumulating on the WEEX orderbook (10 buy/10 sell visible) despite configuration for only 4 per side. Root cause: batch cancel was not being used, leading to rate limit failures.

## Root Cause Analysis

### The Chain of Events
1. Strategy calls `cancel_all_orders()` to clear old orders before refresh cycle
2. Framework's base class `ExchangePyBase.cancel_all_orders()` **uses individual cancel operations in parallel**
3. Each individual cancel is a separate API call: `POST /api/v2/trade/cancel-order`
4. With 8-10 orders, parallel execution = 8-10 simultaneous requests
5. WEEX has aggressive rate limits (~50 weight/second burst limit)
6. Individual cancels hit HTTP 429 "Rate limit exceeded" errors
7. Orders fail to cancel, persist on orderbook
8. Next 120s refresh cycle places new orders on top → **accumulation**

### Evidence from Logs
From `logs/logs_weex_vcc_pmm.log` lines 882-950:

```
2026-02-03 04:10:24,384 - hummingbot.connector.exchange.weex.weex_exchange.WeexExchange - ERROR - Failed to cancel order...
OSError: Error executing request POST https://api-spot.weex.com/api/v2/trade/cancel-order.
HTTP status is 429. Error: {"code":"429","data":{},"msg":"Rate limit exceeded."}
```

Multiple failures in rapid succession (~10-15 at timestamp 04:10:24) showing parallel execution hitting rate limits.

### Why Batch Cancel Wasn't Used
- WEEX connector has `batch_order_cancel()` method implemented (Lines 441-545)
- More efficient: Single API call with 10 weight vs 8 individual calls with 24 weight combined
- **BUT** framework's `ExchangePyBase.cancel_all_orders()` doesn't know about it
- It only calls `_execute_cancel()` for each order individually
- The `batch_order_cancel()` method was sitting unused

### Framework Architecture
**File**: `hummingbot/connector/exchange_py_base.py`

```python
async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
    incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
    # Creates individual async tasks for each order:
    tasks = [self._execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
    # Executes ALL in parallel - hits rate limits!
    cancellation_results = await safe_gather(*tasks, return_exceptions=True)
```

This parallel approach works for most exchanges but not WEEX's strict limits.

## Solution Implemented

### Override `cancel_all_orders()` in WEEX Connector
**File**: `hummingbot/connector/exchange/weex/weex_exchange.py`

Added new method (Lines 546-604) that:

1. **Gets incomplete orders** - Same as framework
2. **Converts to LimitOrder format** - Required by batch_order_cancel()
3. **Uses batch_order_cancel()** - Single API call instead of 8-10 parallel calls
4. **Waits for completion** - 2 second wait for batch operation to settle
5. **Checks order states** - Verifies orders actually canceled
6. **Returns results** - CancellationResult list as expected by framework

### Key Advantages
- **Single API call**: 10 weight instead of 24 weight (58% reduction)
- **Avoids rate limits**: One 10-weight batch call vs 8-10 simultaneous 3-weight calls
- **Backwards compatible**: Same interface, framework doesn't need changes
- **Logging**: Added `[WEEX_BATCH_CANCEL]` debug logs for monitoring

### Code Diff
```python
async def cancel_all_orders(self, timeout_seconds: float) -> List[CancellationResult]:
    """Override to use batch cancel instead of individual cancels."""
    incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]

    if not incomplete_orders:
        return []

    # Convert to LimitOrder format
    limit_orders = [...]

    # Use batch cancel (fires off async operation)
    self.batch_order_cancel(limit_orders)

    # Wait for completion
    await asyncio.sleep(min(2.0, timeout_seconds))

    # Check results
    return [CancellationResult(o.client_order_id, o.is_done) for o in incomplete_orders]
```

## Expected Impact

### Before Fix
- Individual cancels hit HTTP 429
- Orders fail to cancel
- Accumulation on orderbook (10 buy/10 sell)
- Strategy can't refresh properly

### After Fix
- Single batch cancel call (10 weight)
- Stays under rate limits
- Orders cancel cleanly
- New 4x4 orders placed on refresh
- Proper market-making operation

## Testing
1. Run weex_vcc_pmm.py and monitor logs for `[WEEX_BATCH_CANCEL]` messages
2. Check that orders appear/disappear as expected (4 buy + 4 sell)
3. No HTTP 429 errors in logs
4. Verify orderbook shows correct number of orders per refresh cycle

## Files Modified
- `hummingbot/connector/exchange/weex/weex_exchange.py` - Added cancel_all_orders() override

## Related Code
- **Batch cancel implementation**: Lines 441-545 (`batch_order_cancel()`, `_execute_batch_cancel()`)
- **Individual cancel**: Lines 253-271 (`_place_cancel()` - still used for manual cancels)
- **Strategy on_tick**: `/scripts/weex_vcc_pmm.py` lines 100-155 (calls cancel_all_orders)
