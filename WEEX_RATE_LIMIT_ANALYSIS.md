# WEEX Rate Limit Analysis & Recommendations

## Current Rate Limit Configuration

### From `weex_constants.py`:
```python
PUBLIC_MAX_REQUEST = 20    # 20 requests per 2 seconds (public endpoints)
PRIVATE_MAX_REQUEST = 500  # 500 requests per 10 seconds (private endpoints)
```

### From WEEX API Documentation:
- **Public endpoints**: 20 requests per 2 seconds (IP-based)
- **Private endpoints**: "endpoint-specific weights (typically 2-10 per request)"

## ⚠️ **CRITICAL FINDING**

The documentation mentions **"endpoint-specific weights"** which suggests that private endpoints may have **different costs per call**. Our current implementation assumes **weight = 1** for all endpoints, which may be incorrect.

## API Call Analysis from PMM Strategy Run

When the PMM strategy refreshed 8 orders (4 buy + 4 ask), the following calls were made:

### Order Status Monitoring (Before Cancel):
- `/api/v2/trade/orderInfo` × 8 = 8 calls
- `/api/v2/trade/fills` × 8 = 8 calls

### Order Cancellation:
- `/api/v2/trade/cancel-order` × 8 = 8 calls

### Account Updates:
- `/api/v2/account/assets` × 1-2 = 2 calls

**Total: ~26 API calls in rapid succession**

### Actual Rate Limit Errors (from logs):
```
Error executing request POST https://api-spot.weex.com/api/v2/trade/fills.
HTTP status is 429. Error: {"code":"429","data":{},"msg":"Rate limit exceeded."}

Error executing request POST https://api-spot.weex.com/api/v2/trade/orderInfo.
HTTP status is 429. Error: {"code":"429","data":{},"msg":"Rate limit exceeded."}

Error executing request POST https://api-spot.weex.com/api/v2/trade/cancel-order.
HTTP status is 429. Error: {"code":"429","data":{},"msg":"Rate limit exceeded."}
```

## Root Cause

The issue is **NOT** with our rate limit configuration, but with **strategy behavior**:

1. **PMM Refresh Pattern**: Strategy cancels ALL orders every 30 seconds
2. **Individual Order Management**: Each order requires multiple API calls:
   - Status check
   - Fill check
   - Cancellation
3. **Burst Traffic**: 8 orders × 3 calls = 24 calls in <1 second
4. **WEEX's Actual Limits**: Likely **lower than documented** or has **per-endpoint sub-limits**

## Recommendations

### 1. **IMMEDIATE: Increase Order Refresh Time** ✅
**Current**: 30 seconds
**Recommended**: 120-300 seconds (2-5 minutes)

Rationale: WEEX is not a high-frequency exchange. Longer refresh times reduce API pressure while still maintaining market making effectiveness.

```yaml
# conf/scripts/weex_vcc_pmm.yml
order_refresh_time: 120  # Change from 30 to 120
```

### 2. **Use Batch Cancellation API** 🔧

WEEX provides `/api/v2/trade/cancel-batch-orders` which cancels multiple orders in **one API call**.

**Current approach**: 8 individual cancel calls
**Better approach**: 1 batch cancel call

**Implementation needed**: Modify connector to use batch cancel endpoint.

### 3. **Reduce Order Status Polling** 🔧

The connector polls order status and fills for each active order. With 8 orders, this creates constant API pressure.

**Options**:
- Use WebSocket updates for order status (already implemented)
- Reduce polling frequency for REST fallback
- Only poll orders that haven't been updated via WS

### 4. **Investigate Actual Per-Endpoint Weights** 🔍

The API doc mentions "endpoint-specific weights (typically 2-10 per request)" but doesn't specify which endpoints have which weights.

**Action Required**: Contact WEEX support to get actual weight values for:
- `/api/v2/trade/orderInfo`
- `/api/v2/trade/fills`
- `/api/v2/trade/cancel-order`
- `/api/v2/account/assets`

### 5. **Add Exponential Backoff on 429 Errors** ✅ (Already Implemented)

Hummingbot's throttler should already handle this, but verify behavior.

### 6. **Consider Order-Level Strategy** 🎯

Instead of refreshing ALL orders simultaneously:
- Refresh orders one at a time with delays
- Only refresh orders that have drifted significantly from target price
- Use "rolling refresh" - replace 1-2 orders per interval

## Immediate Action Plan

### Phase 1: Configuration (Now)
1. ✅ Update `order_refresh_time` to 120 seconds in config
2. Test with longer refresh interval
3. Monitor for 429 errors

### Phase 2: Code Optimization (Next)
1. Implement batch cancel in connector
2. Reduce REST polling frequency (rely more on WebSocket)
3. Add smart refresh logic (only refresh orders that need it)

### Phase 3: Verification (After)
1. Contact WEEX support for official rate limit documentation
2. Update `weex_constants.py` with accurate weights
3. Add safety margins to rate limits

## Conservative Safe Rate Limits

Until we get official documentation, recommend **conservative limits**:

```python
# Reduce to 50% of documented limits for safety
PUBLIC_MAX_REQUEST = 10    # Was 20, now 10 per 2 seconds
PRIVATE_MAX_REQUEST = 250  # Was 500, now 250 per 10 seconds
```

**Rationale**:
- WEEX may have undocumented sub-limits
- Actual endpoint weights are unknown
- Better to be conservative than risk account suspension

## Monitoring

Track these metrics:
- Number of 429 errors per hour
- API call distribution (which endpoints hit most)
- Time between bursts of calls
- Average calls per order refresh cycle

## Conclusion

**The connector's rate limit configuration is likely correct**, but the **PMM strategy's refresh pattern is too aggressive for WEEX's actual limits**.

**Immediate fix**: Increase `order_refresh_time` to 120+ seconds
**Long-term fix**: Implement batch cancellation and smarter refresh logic
**Critical need**: Get official per-endpoint weight documentation from WEEX
