# AsterDex 404 Error Fix

## Problem
Getting `HTTP status is 404` error when trying to connect to AsterDex spot API:
```
Error: Error executing request GET https://sapi.asterdex.com/balance. HTTP status is 404.
```

## Root Cause
The AsterDex spot API endpoint structure is different from what we initially configured. The 404 error indicates the endpoint path is incorrect.

## Fixes Applied

### 1. Updated Base URL Structure
```python
# Before
PUBLIC_REST_URL = "https://sapi.asterdex.com/"
PRIVATE_REST_URL = "https://sapi.asterdex.com/"

# After - Added API version path
PUBLIC_REST_URL = "https://sapi.asterdex.com/api/v3/"
PRIVATE_REST_URL = "https://sapi.asterdex.com/api/v3/"
```

### 2. Updated Balance Endpoint
```python
# Before
BALANCE_PATH_URL = "balance"

# After - Using account endpoint (more common)
BALANCE_PATH_URL = "account"
```

### 3. Alternative Endpoint Options
Created test script to try multiple endpoint combinations:
- `https://sapi.asterdex.com/api/v1/account`
- `https://sapi.asterdex.com/api/v3/account`
- `https://sapi.asterdex.com/api/v1/wallet/balance`
- `https://sapi.asterdex.com/api/v3/wallet/balance`

## Next Steps

1. **Test the updated configuration**:
   ```bash
   docker build -t hummingbot-asterdex .
   docker run -it --rm --name hb-asterdex hummingbot-asterdex
   ```

2. **If still getting 404, try the test script**:
   ```bash
   python3 test_asterdex_endpoints.py
   ```

3. **Alternative base URLs to try**:
   - `https://api.asterdex.com/api/v3/` (standard pattern)
   - `https://sapi.asterdex.com/` (direct, no version)
   - `https://sapi.asterdex.com/api/v1/` (v1 instead of v3)

## Expected Result
The connector should now successfully connect to AsterDex and show your spot account balances instead of getting a 404 error.

## Files Modified
- `/hummingbot/connector/exchange/asterdex/asterdex_constants.py`
- Created `/test_asterdex_endpoints.py` for endpoint testing
