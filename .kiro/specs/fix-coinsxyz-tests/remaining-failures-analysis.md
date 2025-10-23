# Remaining Test Failures Analysis

## Summary
29 tests are failing across multiple test files. This document categorizes them by root cause and provides recommended fixes.

## Category 1: Exception Message Format (2 failures)
**Tests:**
1. `test_exceptions_unit.py::TestCoinsxyzExceptions::test_network_error`
2. `test_exceptions_unit.py::TestCoinsxyzExceptions::test_order_error`

**Root Cause:** Exception `__str__()` methods are adding "Coins.ph API Error: " prefix but tests expect raw message.

**Expected:** `"Network timeout"`
**Actual:** `"Coins.ph API Error: Network timeout"`

**Fix:** Remove prefix from `CoinsxyzNetworkError` and `CoinsxyzOrderError` `__str__()` methods.

---

## Category 2: Authentication Issues (2 failures)
**Tests:**
1. `test_unit_tests.py::TestCoinsxyzAuth::test_generate_signature`
2. `test_auth_fixed.py::TestCoinsxyzAuthFixed::test_is_timestamp_valid`

**Root Cause 1:** `_generate_signature()` parameter order issue - test passes (query_string, timestamp) but method expects (params, query_string, timestamp).

**Root Cause 2:** `is_timestamp_valid()` returns False for valid timestamps (1 minute old).

**Fix:** 
- Update `_generate_signature()` to handle positional arguments correctly
- Fix `is_timestamp_valid()` logic to accept timestamps within valid window

---

## Category 3: Balance Handling (2 failures)
**Tests:**
1. `test_account_data_source_unit.py::TestCoinsxyzAccountDataSource::test_parse_account_balances`
2. `test_balance_utils_unit.py::TestCoinsxyzBalanceUtils::test_format_balance_for_display`

**Root Cause 1:** `_parse_account_balances()` returns AccountBalance objects but test expects dictionary with subscriptable access.

**Root Cause 2:** `format_balance_for_display()` signature mismatch - test calls with (balance, precision=4) but method expects (asset, balance_data, precision).

**Fix:**
- Update `_parse_account_balances()` to return dict format or update test
- Fix `format_balance_for_display()` signature or update test

---

## Category 4: Missing Methods in OrderLifecycle (5 failures)
**Tests:**
1. `test_order_lifecycle_unit.py::TestCoinsxyzOrderLifecycle::test_calculate_order_fees`
2. `test_order_lifecycle_unit.py::TestCoinsxyzOrderLifecycle::test_create_order_request`
3. `test_order_lifecycle_unit.py::TestCoinsxyzOrderLifecycle::test_is_order_complete`
4. `test_order_lifecycle_unit.py::TestCoinsxyzOrderLifecycle::test_process_order_update`
5. `test_order_lifecycle_unit.py::TestCoinsxyzOrderLifecycle::test_validate_order_params`

**Root Cause:** CoinsxyzOrderLifecycle class missing methods:
- `calculate_order_fees()`
- `create_order_request()`
- `is_order_complete()`
- `process_order_update()`
- `validate_order_params()`

**Fix:** Add these methods to CoinsxyzOrderLifecycle class.

---

## Category 5: Missing Methods in OrderPlacement (2 failures)
**Tests:**
1. `test_order_placement_unit.py::TestCoinsxyzOrderPlacement::test_format_order_request`
2. `test_order_placement_unit.py::TestCoinsxyzOrderPlacement::test_validate_order_params`

**Root Cause:** CoinsxyzOrderPlacement class missing methods:
- `_format_order_request()`
- `_validate_order_params()`

**Fix:** Add these methods to CoinsxyzOrderPlacement class.

---

## Category 6: Missing Attributes/Methods in TradingRules (5 failures)
**Tests:**
1. `test_trading_rules_unit.py::TestCoinsxyzTradingRules::test_get_all_symbols`
2. `test_trading_rules_unit.py::TestCoinsxyzTradingRules::test_get_trading_rule`
3. `test_trading_rules_unit.py::TestCoinsxyzTradingRules::test_is_symbol_supported`
4. `test_trading_rules_unit.py::TestCoinsxyzTradingRules::test_parse_lot_size_filter`
5. `test_trading_rules_unit.py::TestCoinsxyzTradingRules::test_parse_price_filter`

**Root Cause:** CoinsxyzTradingRules class missing:
- `_rules` attribute
- `_parse_lot_size_filter()` method
- `_parse_price_filter()` method

**Fix:** Add missing attribute and methods to CoinsxyzTradingRules class.

---

## Category 7: Retry Handler Missing Attribute (1 failure)
**Test:** `test_unit_tests.py::TestCoinsxyzRetryHandler::test_init`

**Root Cause:** CoinsxyzRetryHandler missing `_retry_stats` attribute.

**Fix:** Add `_retry_stats` attribute to `__init__()` method.

---

## Category 8: User Stream Data Source Issues (4 failures)
**Tests:**
1. `test_user_stream_data_source_unit.py::TestCoinsxyzAPIUserStreamDataSource::test_create_listen_key`
2. `test_user_stream_data_source_unit.py::TestCoinsxyzAPIUserStreamDataSource::test_process_balance_update`
3. `test_user_stream_data_source_unit.py::TestCoinsxyzAPIUserStreamDataSource::test_process_order_update`
4. `test_user_stream_data_source_unit.py::TestCoinsxyzAPIUserStreamDataSource::test_validate_balance_update`
5. `test_user_stream_data_source_unit.py::TestCoinsxyzAPIUserStreamDataSource::test_validate_order_update`

**Root Cause:** 
- Mock not working correctly for `_create_listen_key()`
- Validation returns STALE_DATA instead of VALID (timestamp too old: 1234567890000 is from 2009)
- Processing methods return None due to validation failures

**Fix:** Update test data to use current timestamps or adjust validation logic.

---

## Category 9: WebSocket Connection Manager Issues (4 failures)
**Tests:**
1. `test_websocket_connection_manager_unit.py::TestCoinsxyzWebSocketConnectionManager::test_connect_websocket`
2. `test_websocket_connection_manager_unit.py::TestCoinsxyzWebSocketConnectionManager::test_disconnect`
3. `test_websocket_connection_manager_unit.py::TestCoinsxyzWebSocketConnectionManager::test_get_connection_url`
4. `test_websocket_connection_manager_unit.py::TestCoinsxyzWebSocketConnectionManager::test_is_connected`

**Root Cause:**
- Missing `websockets` module
- `is_connected` is a property (bool) not a method
- Missing `get_connection_url()` method

**Fix:** 
- Install websockets module or mock it
- Update tests to access `is_connected` as property
- Add `get_connection_url()` method

---

## Category 10: WebSocket Unit Test (1 failure)
**Test:** `test_websocket_unit.py::TestCoinsxyzWebSocketConnectionManager::test_start`

**Root Cause:** Connection timeout trying to connect to real wss://wsapi.coins.xyz/ws

**Fix:** Mock the websocket connection in test.

---

## Fix Priority
1. **High Priority** (Quick fixes, 11 tests):
   - Exception messages (2)
   - Authentication issues (2)
   - Balance handling (2)
   - Retry handler (1)
   - User stream timestamps (4)

2. **Medium Priority** (Requires adding methods, 12 tests):
   - OrderLifecycle methods (5)
   - OrderPlacement methods (2)
   - TradingRules methods (5)

3. **Low Priority** (Infrastructure/mocking, 6 tests):
   - WebSocket issues (5)
   - Connection timeout (1)
