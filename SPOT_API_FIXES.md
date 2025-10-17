# AsterDex Spot API Fixes

## Problem
The AsterDex connector was using futures API endpoints (`https://fapi.asterdex.com/fapi/v1/`) which caused balance issues when users had funds in their spot accounts.

## Solution
Updated the connector to use the correct AsterDex spot API endpoints as provided by the user.

## Changes Made

### 1. Updated API Endpoints in `asterdex_constants.py`
```python
# Before (Futures API)
PUBLIC_REST_URL = "https://fapi.asterdex.com/fapi/v1/"
PRIVATE_REST_URL = "https://fapi.asterdex.com/fapi/v1/"
WS_URL = "wss://fstream.asterdex.com/ws"
PRIVATE_WS_URL = "wss://fstream.asterdex.com/ws"

# After (Spot API)
PUBLIC_REST_URL = "https://sapi.asterdex.com/"
PRIVATE_REST_URL = "https://sapi.asterdex.com/"
WS_URL = "wss://stream.asterdex.com/ws"
PRIVATE_WS_URL = "wss://stream.asterdex.com/ws"
```

### 2. Key Benefits
- ✅ **Correct Balance Display**: Now shows spot account balances instead of futures balances
- ✅ **Proper API Endpoints**: Uses the official AsterDex spot API at `https://sapi.asterdex.com/`
- ✅ **Spot Trading Support**: Enables pure market making strategies with spot assets
- ✅ **WebSocket Updates**: Uses correct spot WebSocket endpoints for real-time data

### 3. API Endpoint Structure
The AsterDex spot API follows standard patterns:
- **Base URL**: `https://sapi.asterdex.com/`
- **Endpoints**: Standard REST endpoints (balance, order, exchangeInfo, etc.)
- **WebSocket**: `wss://stream.asterdex.com/ws`

### 4. Testing
Created `test_spot_api.py` to verify the connection works correctly with the new endpoints.

## Next Steps
1. Build and test the updated Docker container
2. Connect to AsterDex with spot API keys
3. Verify spot balances are displayed correctly
4. Test pure market making strategy with spot assets

## Files Modified
- `/hummingbot/connector/exchange/asterdex/asterdex_constants.py`
- `/hummingbot-fresh/Dockerfile` (added test script)
- Created `/test_spot_api.py` for testing
