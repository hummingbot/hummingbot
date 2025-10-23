# Design Document: Fix Coinsxyz Test Suite

## Overview

This design document outlines the technical approach to fix all 74 test failures and 50 warnings in the Coinsxyz exchange connector test suite. The solution involves fixing event loop management, constructor signatures, missing methods, balance calculations, authentication signatures, and async test execution patterns.

## Architecture

### Component Structure

```
Test Fixes
├── Event Loop Management (test_exchange_unit.py, test_integration.py)
├── Constructor Fixes (test_order_lifecycle_unit.py, test_order_placement_unit.py, test_trading_rules_unit.py)
├── WebAssistantsFactory Initialization (coinsxyz_websocket_connection_manager.py)
├── TimeSynchronizer Methods (coinsxyz_time_synchronizer.py)
├── Balance Parsing (coinsxyz_account_data_source.py)
├── Authentication Signatures (coinsxyz_auth.py, test_unit_tests.py)
├── Order Utils (coinsxyz_order_utils.py)
├── Exception Messages (coinsxyz_exceptions.py)
└── Async Test Patterns (multiple test files)
```

## Components and Interfaces

### 1. Event Loop Management

**Location:** `test/hummingbot/connector/exchange/coinsxyz/test_exchange_unit.py`, `test_integration.py`

**Problem:** Tests instantiate `CoinsxyzExchange` which requires an event loop, but none exists in synchronous test context.

**Solution:**
- Add `setUp()` method to create and set event loop
- Add `tearDown()` method to close event loop
- Use `asyncio.new_event_loop()` and `asyncio.set_event_loop()`

**Implementation:**
```python
def setUp(self):
    self.ev_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.ev_loop)
    # ... rest of setup

def tearDown(self):
    if hasattr(self, 'ev_loop') and self.ev_loop:
        self.ev_loop.close()
```

### 2. WebAssistantsFactory Initialization

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_websocket_connection_manager.py`

**Problem:** `WebAssistantsFactory()` requires `throttler` parameter but code calls it without arguments.

**Solution:**
- Check if `api_factory` is None
- Create `AsyncThrottler` with `CONSTANTS.RATE_LIMITS`
- Pass throttler to `WebAssistantsFactory`

**Implementation:**
```python
if api_factory is None:
    from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
    throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
    api_factory = WebAssistantsFactory(throttler=throttler)
self._api_factory = api_factory
```

### 3. Constructor Parameter Fixes

**Location:** Multiple test files

**Problem:** Tests use `api_client` parameter but classes expect `api_factory`.

**Solution:**
- Update test fixtures to use `api_factory` instead of `api_client`
- Create mock `api_factory` using `MagicMock()`

**Files to Fix:**
- `test_order_lifecycle_unit.py`: Change `CoinsxyzOrderLifecycle()` to `CoinsxyzOrderLifecycle(api_factory=mock_api_factory)`
- `test_order_placement_unit.py`: Change `api_client=` to `api_factory=`
- `test_trading_rules_unit.py`: Change `api_client=` to `api_factory=`

### 4. TimeSynchronizer Methods

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_time_synchronizer.py`

**Problem:** Tests call `time_ms()`, `get_timestamp()`, `get_time_offset_ms()` but these methods don't exist.

**Solution:**
Add missing methods to `TimeSynchronizer` class:

```python
def time_ms(self) -> int:
    """Get current time in milliseconds."""
    return int(time.time() * 1000) + self._time_offset_ms

def get_timestamp(self) -> int:
    """Get current timestamp."""
    return self.time_ms()

def get_time_offset_ms(self) -> int:
    """Get time offset in milliseconds."""
    return self._time_offset_ms
```

### 5. Balance Parsing Fix

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_account_data_source.py`

**Problem:** Test expects `parsed["BTC"].total_balance` but gets `Decimal('1.0')` instead of `Decimal('1.5')`.

**Root Cause:** The method returns dictionary, not object with attributes. Test is accessing wrong way.

**Solution:**
Fix the test to use dictionary access: `parsed["BTC"]["total_balance"]`

**Location:** `test/hummingbot/connector/exchange/coinsxyz/test_account_data_source_unit.py`

### 6. Balance Validation Fix

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_balance_utils.py`

**Problem:** `validate_balance_data({"asset": "BTC"})` returns `True` but should return `False`.

**Solution:**
The validation should require at least one numeric field. Current implementation returns `True` if no numeric fields fail validation. Fix logic to require presence of numeric fields.

### 7. Authentication Method Signatures

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_auth.py`

**Problems:**
1. `_generate_signature()` takes 2 args but test passes 3
2. `is_timestamp_valid()` doesn't properly validate old timestamps
3. `rest_authenticate()` returns coroutine but test expects synchronous result
4. `header_for_authentication()` returns `X-COINS-APIKEY` but test expects `X-MBX-APIKEY`

**Solutions:**
1. Update `_generate_signature(self, query_string, timestamp=None)` to accept optional timestamp
2. Fix `is_timestamp_valid()` to check if timestamp is older than threshold (e.g., 60 seconds)
3. Update test to use `await` or `asyncio.run()` for `rest_authenticate()`
4. Update test expectation to check for `X-COINS-APIKEY` instead of `X-MBX-APIKEY`

### 8. Order Utils Fixes

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_order_utils.py`

**Problems:**
1. `apply_trading_rules()` returns `Decimal('0.000')` for amount below minimum instead of minimum
2. `parse_order_response()` doesn't include `exchange_order_id` key

**Solutions:**
1. Fix `apply_trading_rules()` to return `min_order_size` when amount < min_order_size
2. Add `exchange_order_id` to parsed response dictionary

### 9. Order Validation Fixes

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_order_validation.py`

**Problems:**
1. Quantization doesn't match expected precision
2. Invalid symbol validation returns `True` instead of `False`

**Solutions:**
1. Fix quantization to properly round to expected decimal places
2. Add symbol validation logic to check against valid trading pairs

### 10. Exception Message Format

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_exceptions.py`

**Problem:** Exception `__str__()` adds prefix "Coins.ph API Error: " but tests expect raw message.

**Solution:**
Remove prefix from `__str__()` method or update base class to not add prefix.

### 11. Async Test Execution

**Location:** Multiple test files

**Problem:** Async test methods return coroutines without awaiting, causing warnings.

**Solution:**
- Convert async test methods to use `asyncio.run()` wrapper
- Or use `@pytest.mark.asyncio` decorator
- Ensure tests don't return non-None values

### 12. WSRequest Construction

**Location:** `test/hummingbot/connector/exchange/coinsxyz/test_auth_fixed.py`

**Problem:** `WSRequest(payload={})` raises `TypeError: WSRequest() takes no arguments`.

**Solution:**
- Check `WSRequest` class signature
- Use mock object instead: `request = MagicMock()`
- Or fix `WSRequest` to accept parameters

### 13. Utility Function Validation

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_utils.py`

**Problem:** `is_pair_information_valid()` returns `False` for valid data.

**Solution:**
Review validation logic and fix to properly validate trading pair information.

### 14. Retry Handler Attributes

**Location:** `hummingbot/connector/exchange/coinsxyz/coinsxyz_retry_utils.py`

**Problem:** Test expects `_retry_stats` attribute but it doesn't exist.

**Solution:**
- Add `_retry_stats` attribute to `__init__()` if tests require it
- Or update test to not check for this attribute

## Data Models

### Event Loop Lifecycle
```
Test Start → setUp() → Create Event Loop → Set Event Loop → Run Test → tearDown() → Close Event Loop → Test End
```

### Balance Data Structure
```python
{
    "BTC": {
        "total_balance": Decimal("1.5"),
        "available_balance": Decimal("1.0"),
        "locked_balance": Decimal("0.5")
    }
}
```

### Order Response Structure
```python
{
    "exchange_order_id": "12345",
    "client_order_id": "test_order_1",
    "symbol": "BTCUSDT",
    "status": "NEW",
    "timestamp": 1234567890000
}
```

## Error Handling

### Event Loop Errors
- Catch `RuntimeError` about missing event loop
- Ensure event loop is created before any async operations
- Always close event loop in tearDown to prevent resource leaks

### Constructor Errors
- Validate parameter names match class signatures
- Use mock objects for dependencies in tests
- Provide default values where appropriate

### Validation Errors
- Return `False` for invalid data instead of raising exceptions
- Check for required fields before accessing
- Validate numeric ranges and formats

## Testing Strategy

### Unit Test Fixes
1. Fix event loop setup in 18 test methods
2. Fix constructor calls in 13 test methods
3. Add missing methods to 4 classes
4. Fix 5 assertion expectations
5. Update 50 async test methods

### Validation Approach
1. Run pytest after each category of fixes
2. Verify failure count decreases
3. Check for new errors introduced
4. Ensure warnings are eliminated

### Success Criteria
- 0 test failures
- 0 warnings
- All 246 tests pass
- No coroutine warnings
- No deprecation warnings

## Implementation Priority

1. **High Priority** (Blocks most tests):
   - Event loop management (18 failures)
   - WebAssistantsFactory initialization (13 failures)
   - Constructor parameter fixes (13 failures)

2. **Medium Priority** (Blocks specific test suites):
   - TimeSynchronizer methods (7 failures)
   - Authentication signatures (4 failures)
   - Order utils/validation (5 failures)

3. **Low Priority** (Individual test fixes):
   - Balance parsing (3 failures)
   - Exception messages (2 failures)
   - Utility validation (1 failure)
   - Retry handler attributes (1 failure)
   - WSRequest construction (1 failure)

4. **Cleanup** (Warnings):
   - Async test execution patterns (50 warnings)

## Dependencies

- Python 3.11+
- asyncio
- pytest
- pytest-asyncio
- unittest.mock
- decimal

## Migration Notes

- Tests already fixed in previous session should not be modified
- WebAssistantsFactory fix was partially implemented but needs completion
- Event loop setup was added to some tests but not all
