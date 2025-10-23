# Requirements Document: Fix Coinsxyz Test Suite

## Introduction

This document outlines the requirements for fixing all test failures and warnings in the Coinsxyz exchange connector test suite. The goal is to achieve 100% test pass rate with zero warnings by addressing asyncio issues, constructor mismatches, missing methods, and other compatibility problems.

## Glossary

- **System**: The Coinsxyz exchange connector test suite
- **Event Loop**: Python asyncio event loop required for async operations
- **WebAssistantsFactory**: Factory class for creating web assistant instances
- **TimeSynchronizer**: Class for synchronizing time with exchange servers
- **Test Fixture**: Setup code that runs before each test method
- **Mock Object**: Test double that simulates real object behavior

## Requirements

### Requirement 1: Event Loop Management

**User Story:** As a test developer, I want all tests to have proper event loop setup, so that async operations work correctly without RuntimeError.

#### Acceptance Criteria

1. WHEN a test class instantiates CoinsxyzExchange, THE System SHALL create an event loop in setUp method
2. WHEN a test completes, THE System SHALL close the event loop in tearDown method
3. WHEN test_exchange_unit.py runs, THE System SHALL NOT raise RuntimeError about missing event loop
4. WHEN test_integration.py runs, THE System SHALL NOT raise RuntimeError about missing event loop

### Requirement 2: WebAssistantsFactory Initialization

**User Story:** As a test developer, I want WebAssistantsFactory to initialize with required throttler parameter, so that websocket connection tests pass.

#### Acceptance Criteria

1. WHEN CoinsxyzWebSocketConnectionManager initializes without api_factory, THE System SHALL create WebAssistantsFactory with throttler
2. WHEN throttler is created, THE System SHALL use CONSTANTS.RATE_LIMITS configuration
3. WHEN test_websocket_connection_manager_unit.py runs, THE System SHALL NOT raise TypeError about missing throttler
4. WHEN test_websocket_unit.py runs, THE System SHALL NOT raise TypeError about missing throttler

### Requirement 3: Constructor Parameter Consistency

**User Story:** As a test developer, I want test fixtures to use correct constructor parameters, so that object instantiation succeeds.

#### Acceptance Criteria

1. WHEN test creates CoinsxyzOrderLifecycle, THE System SHALL pass api_factory parameter
2. WHEN test creates CoinsxyzOrderPlacement, THE System SHALL pass api_factory parameter (not api_client)
3. WHEN test creates CoinsxyzTradingRules, THE System SHALL pass api_factory parameter (not api_client)
4. WHEN test_order_lifecycle_unit.py runs, THE System SHALL NOT raise TypeError about missing api_factory
5. WHEN test_order_placement_unit.py runs, THE System SHALL NOT raise TypeError about unexpected api_client
6. WHEN test_trading_rules_unit.py runs, THE System SHALL NOT raise TypeError about unexpected api_client

### Requirement 4: TimeSynchronizer Method Implementation

**User Story:** As a test developer, I want TimeSynchronizer to have all required methods, so that time synchronization tests pass.

#### Acceptance Criteria

1. WHEN test calls time_sync.time_ms(), THE System SHALL return current timestamp in milliseconds
2. WHEN test calls time_sync.get_timestamp(), THE System SHALL return current timestamp
3. WHEN test calls time_sync.get_time_offset_ms(), THE System SHALL return time offset in milliseconds
4. WHEN test_auth_unit.py runs TimeSynchronizer tests, THE System SHALL NOT raise AttributeError
5. WHEN test_unit_tests.py runs TimeSynchronizer tests, THE System SHALL NOT raise AttributeError

### Requirement 5: Balance Parsing Correctness

**User Story:** As a test developer, I want balance parsing to calculate total correctly, so that balance tests pass.

#### Acceptance Criteria

1. WHEN _parse_account_balances receives balance data, THE System SHALL calculate total as free + locked
2. WHEN test accesses parsed["BTC"]["total_balance"], THE System SHALL return Decimal("1.5") for free=1.0 and locked=0.5
3. WHEN test_account_data_source_unit.py runs, THE System SHALL NOT raise AssertionError about balance mismatch
4. WHEN validate_balance_data receives data without numeric fields, THE System SHALL return False

### Requirement 6: Authentication Method Signatures

**User Story:** As a test developer, I want authentication methods to have correct signatures, so that auth tests pass.

#### Acceptance Criteria

1. WHEN test calls _generate_signature with query_string and timestamp, THE System SHALL accept both parameters
2. WHEN test calls is_timestamp_valid with old timestamp, THE System SHALL return False
3. WHEN test calls rest_authenticate, THE System SHALL return awaitable coroutine
4. WHEN test calls header_for_authentication, THE System SHALL return headers with X-COINS-APIKEY (not X-MBX-APIKEY)
5. WHEN test_unit_tests.py runs auth tests, THE System SHALL NOT raise TypeError about argument count

### Requirement 7: Order Utils and Validation

**User Story:** As a test developer, I want order utilities to handle edge cases correctly, so that order tests pass.

#### Acceptance Criteria

1. WHEN apply_trading_rules receives amount below minimum, THE System SHALL return minimum amount (not zero)
2. WHEN parse_order_response parses response, THE System SHALL include exchange_order_id key
3. WHEN quantize_order_amount quantizes amount, THE System SHALL match expected precision
4. WHEN quantize_order_price quantizes price, THE System SHALL match expected precision
5. WHEN validate_order receives invalid symbol, THE System SHALL return is_valid=False

### Requirement 8: Exception Message Format

**User Story:** As a test developer, I want exception messages to match expected format, so that exception tests pass.

#### Acceptance Criteria

1. WHEN CoinsxyzNetworkError is created with message, THE System SHALL return message without prefix
2. WHEN CoinsxyzOrderError is created with message, THE System SHALL return message without prefix
3. WHEN test_exceptions_unit.py runs, THE System SHALL NOT raise AssertionError about message format

### Requirement 9: Async Test Execution

**User Story:** As a test developer, I want async test methods to execute properly, so that no coroutine warnings appear.

#### Acceptance Criteria

1. WHEN test method is async, THE System SHALL use await or asyncio.run to execute
2. WHEN test returns coroutine, THE System SHALL NOT return non-None value
3. WHEN pytest runs, THE System SHALL NOT show RuntimeWarning about unawaited coroutines
4. WHEN pytest runs, THE System SHALL NOT show DeprecationWarning about test return values

### Requirement 10: WSRequest Construction

**User Story:** As a test developer, I want WSRequest to construct properly, so that websocket auth tests pass.

#### Acceptance Criteria

1. WHEN test creates WSRequest, THE System SHALL accept constructor parameters or use mock
2. WHEN test_auth_fixed.py runs ws_authenticate_async, THE System SHALL NOT raise TypeError about WSRequest arguments

### Requirement 11: Utility Function Validation

**User Story:** As a test developer, I want utility functions to validate data correctly, so that utility tests pass.

#### Acceptance Criteria

1. WHEN is_pair_information_valid checks valid info, THE System SHALL return True
2. WHEN test_utils_unit.py runs, THE System SHALL NOT raise AssertionError about validation

### Requirement 12: Retry Handler Attributes

**User Story:** As a test developer, I want CoinsxyzRetryHandler to have expected attributes, so that retry handler tests pass.

#### Acceptance Criteria

1. WHEN CoinsxyzRetryHandler initializes, THE System SHALL create _retry_stats attribute if tests expect it
2. WHEN test_unit_tests.py runs retry handler tests, THE System SHALL NOT raise AttributeError about _retry_stats
