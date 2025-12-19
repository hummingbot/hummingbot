# Implementation Plan: Fix Coinsxyz Test Suite

## Task List

- [x] 1. Fix WebAssistantsFactory initialization in websocket connection manager


  - Update `coinsxyz_websocket_connection_manager.py` to create throttler when api_factory is None
  - Import AsyncThrottler and create instance with CONSTANTS.RATE_LIMITS
  - Pass throttler to WebAssistantsFactory constructor
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2. Add missing methods to TimeSynchronizer class


  - Add `time_ms()` method to return current time in milliseconds
  - Add `get_timestamp()` method to return current timestamp
  - Add `get_time_offset_ms()` method to return time offset
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 3. Fix event loop management in test_exchange_unit.py



  - Add event loop creation in setUp() method
  - Add event loop cleanup in tearDown() method
  - Ensure all test methods have access to event loop
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 4. Fix event loop management in test_integration.py


  - Add event loop creation in setUp() method
  - Add event loop cleanup in tearDown() method
  - Ensure all test methods have access to event loop
  - _Requirements: 1.1, 1.2, 1.4_

- [x] 5. Fix constructor parameters in test_order_lifecycle_unit.py




  - Change `CoinsxyzOrderLifecycle()` to accept `api_factory` parameter
  - Create mock api_factory in setUp()
  - Update all test instantiations
  - _Requirements: 3.1, 3.4_

- [x] 6. Fix constructor parameters in test_order_placement_unit.py


  - Change `api_client=` to `api_factory=` in all instantiations
  - Update mock object name from api_client to api_factory
  - _Requirements: 3.2, 3.5_

- [x] 7. Fix constructor parameters in test_trading_rules_unit.py


  - Change `api_client=` to `api_factory=` in all instantiations
  - Update mock object name from api_client to api_factory
  - _Requirements: 3.3, 3.6_

- [x] 8. Fix balance parsing test expectations


  - Update test to use dictionary access `parsed["BTC"]["total_balance"]` instead of attribute access
  - Verify balance calculation logic is correct (free + locked = total)
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 9. Fix balance validation logic



  - Update `validate_balance_data()` to return False when no numeric fields present
  - Ensure validation requires at least one of: free, locked, or total
  - _Requirements: 5.4_

- [x] 10. Fix authentication method signatures


  - Update `_generate_signature()` to accept optional timestamp parameter
  - Fix `is_timestamp_valid()` to properly validate old timestamps (>60 seconds)
  - Update test expectations for `header_for_authentication()` to check X-COINS-APIKEY
  - _Requirements: 6.1, 6.2, 6.4, 6.5_


- [x] 11. Fix async authentication test








  - Update `test_rest_authenticate` to properly await coroutine
  - Use `asyncio.run()` or make test method async
  - _Requirements: 6.3_



- [x] 12. Fix order utils apply_trading_rules


  - Update logic to return min_order_size when amount < min_order_size (not zero)
  - Ensure proper handling of trading rule constraints

  - _Requirements: 7.1_


- [x] 13. Fix order utils parse_order_response


  - Add `exchange_order_id` key to parsed response dictionary

  - Map from response `orderId` field
  - _Requirements: 7.2_


- [x] 14. Fix order validation quantization


  - Update `quantize_order_amount()` to match expected precision

  - Update `quantize_order_price()` to match expected precision
  - Ensure proper decimal rounding
  - _Requirements: 7.3, 7.4_


- [x] 15. Fix order validation for invalid symbols

  - Add symbol validation logic to check against valid trading pairs

  - Return `is_valid=False` for invalid symbols
  - _Requirements: 7.5_

- [x] 16. Fix exception message format

  - Remove "Coins.ph API Error: " prefix from CoinsxyzNetworkError __str__()
  - Remove "Coins.ph API Error: " prefix from CoinsxyzOrderError __str__()
  - _Requirements: 8.1, 8.2, 8.3_


- [x] 17. Fix WSRequest construction in test_auth_fixed.py


  - Replace `WSRequest(payload={})` with `MagicMock()` or fix WSRequest class
  - Ensure test can create request object for ws_authenticate test
  - _Requirements: 10.1, 10.2_


- [x] 18. Fix utility function validation


  - Update `is_pair_information_valid()` to properly validate trading pair info
  - Ensure function returns True for valid data structure

  - _Requirements: 11.1, 11.2_

- [x] 19. Fix retry handler attributes


  - Add `_retry_stats` attribute to CoinsxyzRetryHandler.__init__() if needed
  - Or update test to not check for this internal attribute
  - _Requirements: 12.1, 12.2_

- [x] 20. Fix format_balance_for_display signature





  - Update test to pass correct parameters (asset, balance_data, precision)
  - Ensure method signature matches test expectations
  - _Requirements: 5.1_

- [ ]* 21. Fix async test execution warnings


  - Review all async test methods that return coroutines
  - Add proper await or asyncio.run() wrappers
  - Ensure tests don't return non-None values
  - _Requirements: 9.1, 9.2, 9.3, 9.4_
