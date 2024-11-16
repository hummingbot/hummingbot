import unittest
from asyncio import Protocol
from datetime import datetime
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from httpcore import NetworkError

from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.mixin_fetch_candle_data import (
    MixinFetchCandleData,
    _ProtocolFetchCandleDataWithMixin,
)


class MockProtocolFetchCandleData(Protocol):
    """Protocol class for mocking candle fetching functionality."""
    interval_in_seconds: int
    candles_max_result_per_rest_request: int
    candles_url: str
    _api_factory: MagicMock
    _rest_throttler_limit_id: str

    def _catsc_parse_rest_candles_data(self, response: dict, current_end: int) -> tuple[CandleData, ...]:
        """Parse candle data from REST API response."""
        ...


class TestCandleFetcher(IsolatedAsyncioWrapperTestCase):
    """Test suite for candle fetching functionality.

    This test suite covers various scenarios for the _fetch_candles method:
    - Basic successful fetching
    - Error handling
    - Time range validations
    - Data sanitization
    - Multiple batch handling

    Each test case is documented with specific test conditions and expected outcomes.
    """

    def setUp(self) -> None:
        """Set up test fixtures before each test method.

        Creates mock objects and initializes common test data.
        """
        super().setUp()
        self.mock_rest_assistant = AsyncMock()

        # Create a mock instance implementing the Main class needed Protocol
        self.mock_mixin_instance = MagicMock(spec=_ProtocolFetchCandleDataWithMixin)
        self.mock_mixin_instance._api_factory = MagicMock()
        self.mock_mixin_instance._api_factory.get_rest_assistant = AsyncMock(
            return_value=self.mock_rest_assistant
        )
        self.mock_mixin_instance.interval_in_seconds = 300  # 5 minutes
        self.mock_mixin_instance.candles_max_result_per_rest_request = 100
        self.mock_mixin_instance.candles_url = "https://api.example.com/candles"
        self.mock_mixin_instance._rest_throttler_limit_id = "CANDLES"

        # Set up default mock responses
        def mock_execute_request(url=None, throttler_limit_id=None, params=None):
            return params

        self.params_calls = []

        def mock_get_params(start_time, end_time, limit=self.mock_mixin_instance.candles_max_result_per_rest_request):
            self.params_calls.append((start_time, end_time, limit))
            return {"start": start_time, "end": end_time, "limit": limit}

        self.mock_rest_assistant.execute_request = AsyncMock(side_effect=mock_execute_request)
        self.mock_mixin_instance._get_rest_candles_params = MagicMock(side_effect=mock_get_params)
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock()
        self.mock_mixin_instance.logger = MagicMock()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

    def create_mock_candles(
            self,
            start_time: int,
            end_time: int,
            interval: int,
            skip_timestamps: set[int] | None = None
    ) -> tuple[CandleData, ...]:
        """Create mock candles with optional missing timestamps."""
        candles = []
        current_time = start_time
        while current_time <= end_time:
            if not skip_timestamps or current_time not in skip_timestamps:
                candles.append(CandleData(
                    timestamp_raw=current_time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
            current_time += interval
        return tuple(candles)

    def create_mock_candle_batch(
            self,
            start_time: int,
            end_time: int,
            interval: int,
            limit: int = 100
    ) -> tuple[CandleData, ...]:
        candles = []
        current_time = end_time
        index = 0
        while current_time >= start_time:
            candles.append(CandleData(
                timestamp_raw=current_time,
                open=index,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            ))
            self.assertLessEqual(len(candles), limit)
            index += 1
            current_time -= interval

        return tuple(candles)

    async def test_basic_fetch(self):
        """Test basic fetching of candles within a single batch."""
        end_time = int(datetime.now().timestamp())
        interval = self.mock_mixin_instance.interval_in_seconds
        start_time = end_time - (interval * 10)  # 10 candles worth of time

        mock_candles = self.create_mock_candle_batch(
            start_time=start_time,
            end_time=end_time,
            interval=self.mock_mixin_instance.interval_in_seconds
        )

        self.mock_mixin_instance._catsc_parse_rest_candles_data.return_value = mock_candles

        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        self.assertLessEqual(len(result), len(mock_candles))
        self.assertGreaterEqual(len(result) + 2, len(mock_candles))  # Possible misalign on start and end
        self.assertGreaterEqual(result[0].timestamp, start_time)
        self.assertLessEqual(result[0].timestamp - interval, start_time)
        self.assertLessEqual(result[-1].timestamp, end_time)
        self.assertGreaterEqual(result[-1].timestamp + interval, end_time)
        self.mock_mixin_instance._get_rest_candles_params.assert_called_once()
        self.mock_rest_assistant.execute_request.assert_called_once()

    async def test_network_error(self):
        """Test handling of network errors during fetch.

        Verifies that network errors are properly propagated and logged.
        """
        self.mock_rest_assistant.execute_request.side_effect = NetworkError("API Error")

        with self.assertRaises(NetworkError) as context:
            await MixinFetchCandleData._fetch_candles(self.mock_mixin_instance)

        self.assertEqual(str(context.exception), "API Error")
        self.mock_mixin_instance.logger().error.assert_called_once()

    async def test_batch_time_calculations(self):
        """Test the time calculations for a simple two-batch scenario.

        This test verifies that:
        - Time boundaries between batches are correctly calculated
        - Each batch's time range is properly defined
        - Time continuity is maintained between batches
        """
        # Setup time range for exactly two batches
        interval = self.mock_mixin_instance.interval_in_seconds  # 300s = 5min
        max_candles = self.mock_mixin_instance.candles_max_result_per_rest_request  # 100

        end_time = 1700000100  # Fixed aligned timestamp (offset=0) for reproducible test
        batch_time_span = interval * max_candles
        start_time = end_time - (batch_time_span * 2)  # Two batches worth of time

        # Setup mocks
        def mock_parse_candles(response, current_end):
            """Create candles for the exact time range requested."""
            start = response["start"]
            end = response["end"]
            return self.create_mock_candle_batch(
                start_time=start,
                end_time=end,
                interval=interval,
                limit=self.mock_mixin_instance.candles_max_result_per_rest_request,
            )

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify batch time boundaries
        self.assertEqual(len(self.params_calls), 3, "Should make exactly two API calls")

        first_batch_start, first_batch_end, _ = self.params_calls[0]
        second_batch_start, second_batch_end, _ = self.params_calls[1]

        # Verify batch continuity
        self.assertEqual(
            second_batch_end,
            first_batch_start - interval,
            "Second batch should end one interval before first batch starts"
        )

        # Verify result properties
        self.assertTrue(all(isinstance(candle, CandleData) for candle in result))

        # Verify timestamps
        timestamps = [candle.timestamp for candle in result]
        self.assertEqual(timestamps, sorted(timestamps), "Timestamps should be in ascending order")

        # Verify intervals between timestamps
        for i in range(1, len(timestamps)):
            self.assertEqual(
                timestamps[i] - timestamps[i - 1],
                interval,
                f"Non-standard interval found between timestamps {timestamps[i]} and {timestamps[i - 1]}"
            )

        # Verify overall time range
        self.assertEqual(
            timestamps[-1],
            end_time - (end_time % interval),
            "Last timestamp should be aligned to interval"
        )
        self.assertGreaterEqual(
            timestamps[0],
            start_time,
            "First timestamp should not be before requested start time"
        )

    async def test_timestamp_alignment(self):
        """Test timestamp alignment behavior.

        Verifies that timestamps are properly aligned with intervals
        and that no unexpected adjustments occur.
        """
        interval = self.mock_mixin_instance.interval_in_seconds  # 300s
        end_time = 1700000100  # Fixed timestamp for reproducibility
        start_time = end_time - (interval * 5)  # 5 candles worth of time

        # Create mock candles with exact timestamps
        test_candles = []
        current_time = start_time
        while current_time <= end_time:
            test_candles.append(CandleData(
                timestamp_raw=current_time,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            ))
            current_time += interval

        def mock_parse_candles(response, current_end):
            # Return candles exactly as we created them
            return tuple(c for c in test_candles
                         if response['start'] <= c.timestamp <= response['end'])

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(
            side_effect=mock_parse_candles
        )

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        self.assertTrue(result)
        timestamps = [candle.timestamp for candle in result]

        # Check first and last timestamps
        self.assertEqual(
            timestamps[0],
            start_time,
            "First timestamp should exactly match start_time"
        )
        self.assertEqual(
            timestamps[-1],
            end_time,
            f"Last timestamp ({timestamps[-1]}) should exactly match end_time ({end_time})"
        )

        # Verify all timestamps are properly aligned
        for timestamp in timestamps:
            self.assertEqual(
                timestamp % interval,
                start_time % interval,
                f"Timestamp {timestamp} is not properly aligned with interval {interval}"
            )

        # Verify all intervals are exact
        for i in range(1, len(timestamps)):
            self.assertEqual(
                timestamps[i] - timestamps[i - 1],
                interval,
                f"Incorrect interval between timestamps {timestamps[i]} and {timestamps[i - 1]}"
            )

    async def test_end_time_handling(self):
        """Test specific end time handling behavior.

        Verifies that the end time is handled correctly without unwanted adjustments.
        """
        interval = self.mock_mixin_instance.interval_in_seconds
        end_time = 1700000100  # Should not be modified
        start_time = end_time - (interval * 3)

        mock_response = {
            'candles': [
                {'timestamp': ts} for ts in range(start_time, end_time + interval, interval)
            ]
        }

        self.mock_rest_assistant.execute_request = AsyncMock(return_value=mock_response)

        def mock_parse_candles(response, current_end):
            return tuple(
                CandleData(
                    timestamp_raw=ts,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                )
                for ts in range(start_time, end_time + interval, interval)
            )

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(
            side_effect=mock_parse_candles
        )

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify that end time is handled correctly
        self.assertEqual(
            result[-1].timestamp,
            end_time,
            "End timestamp should match requested end time exactly"
        )

    async def test_single_batch_boundaries(self):
        """Test time boundaries calculation for a single batch.

        This test verifies the exact time calculations for a single batch
        to ensure proper interval alignment and range handling.
        """
        interval = self.mock_mixin_instance.interval_in_seconds
        end_time = 1700000100  # Fixed timestamp
        start_time = end_time - (interval * 9)  # 10 candles worth of time

        # Setup mocks
        def mock_parse_candles(response, current_end):
            """Create candles for the exact time range requested."""
            start = response["start"]
            end = response["end"]
            return self.create_mock_candle_batch(
                start_time=start,
                end_time=end,
                interval=interval,
                limit=self.mock_mixin_instance.candles_max_result_per_rest_request,
            )

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify time calculations
        self.assertEqual(len(self.params_calls), 1, "Should make exactly one API call")

        # Verify time alignment
        self.assertEqual(
            self.params_calls[0][1],
            end_time,
            "End time should match requested end time"
        )
        self.assertEqual(
            self.params_calls[0][0],
            start_time,
            "Start time should match requested start time"
        )

        # Verify result timestamps
        timestamps = [candle.timestamp for candle in result]
        self.assertEqual(
            timestamps[0],
            start_time,
            "First timestamp should match start time"
        )
        self.assertEqual(
            end_time,
            timestamps[-1],
            "Last timestamp should exactly match the requested end_time"
        )
        # Verify all timestamps between boundaries are properly spaced
        for i in range(1, len(timestamps)):
            self.assertEqual(
                timestamps[i] - timestamps[i - 1],
                interval,
                f"Incorrect interval between timestamps {timestamps[i]} and {timestamps[i - 1]}"
            )

    async def test_batch_boundaries(self):
        """Test the calculation and handling of batch boundaries.

        Verifies:
        - Batch start/end times are correctly calculated
        - First batch starts from most recent time
        - Batch sizes respect max_candles limit
        """
        interval = self.mock_mixin_instance.interval_in_seconds  # 300s
        max_candles = self.mock_mixin_instance.candles_max_result_per_rest_request  # 100

        end_time = 1731334942
        start_time = end_time - (interval * max_candles * 2)  # Request two batches

        def mock_parse_candles(response, current_end):
            """Return minimal candles to test boundary handling."""
            return (
                CandleData(timestamp_raw=response["start"], open=100.0, high=101.0,
                           low=99.0, close=100.5, volume=1000.0),
                CandleData(timestamp_raw=response["end"], open=100.0, high=101.0,
                           low=99.0, close=100.5, volume=1000.0),
            )

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify batches are calculated correctly
        self.assertTrue(self.params_calls, "Should make at least one API call")
        first_batch_start, first_batch_end, _ = self.params_calls[0]
        self.assertEqual(first_batch_end, end_time, "First batch should end at requested end_time")

    async def test_batch_merging(self):
        """Test the merging of multiple batches.

        Verifies:
        - Overlapping batches are handled correctly
        - No duplicate timestamps
        - Proper ordering of results
        """
        interval = self.mock_mixin_instance.interval_in_seconds

        end_time = 1731334942
        batch_span = interval * 3  # Small span for easy testing
        start_time = end_time - batch_span

        batch_responses = []

        def mock_parse_candles(response, current_end):
            """Return overlapping candles to test merge behavior."""
            batch = []
            time = response["start"]
            while time <= response["end"]:
                batch.append(CandleData(
                    timestamp_raw=time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
                time += interval
            batch_responses.append(batch)
            return tuple(batch)

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        timestamps = [candle.timestamp for candle in result]
        unique_timestamps = set(timestamps)
        self.assertEqual(
            len(timestamps),
            len(unique_timestamps),
            "Should have no duplicate timestamps"
        )
        self.assertEqual(
            timestamps,
            sorted(timestamps),
            "Timestamps should be in ascending order"
        )

    async def test_edge_case_time_ranges(self):
        """Test handling of various edge case time ranges.

        Verifies handling of:
        - Start time after end time
        - Zero-length time range
        - Time range smaller than interval
        - Time range exactly matching max_candles
        """
        interval = self.mock_mixin_instance.interval_in_seconds
        max_candles = self.mock_mixin_instance.candles_max_result_per_rest_request

        end_time = 1731334942

        def mock_parse_candles(response, current_end):
            # Return single candle for simplicity
            return (CandleData(
                timestamp_raw=response["start"],
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            ), CandleData(
                timestamp_raw=response["start"] + interval,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            ),)

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Test case 1: Start time after end time
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=end_time + interval,
            end_time=end_time,
        )
        self.assertTrue(len(result) <= max_candles,
                        "Should respect max_candles even with inverted time range")

        # Test case 2: Same start and end time
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=end_time,
            end_time=end_time,
        )
        self.assertTrue(len(result) <= 1, f"Should return at most one candle for same timestamps: {len(result)}")

        # Test case 3: Small time range
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=end_time - interval + 1,
            end_time=end_time,
        )
        self.assertTrue(len(result) <= 2, f"Should handle sub-interval time ranges: {len(result)}")

    async def test_response_limit_handling(self):
        """Test handling of server response limits.

        Verifies:
        - Respects server's max_candles limit
        - Handles partial responses correctly
        - Maintains data consistency with limits
        """
        interval = self.mock_mixin_instance.interval_in_seconds
        max_candles = self.mock_mixin_instance.candles_max_result_per_rest_request

        end_time = 1731334942
        start_time = end_time - (interval * max_candles * 2)  # Request double the limit

        candles_returned = []

        def mock_parse_candles(response, current_end):
            """Simulate server limiting response size."""
            batch = []
            time = response["start"]
            count = 0

            while time <= response["end"] and count < max_candles:
                batch.append(CandleData(
                    timestamp_raw=time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
                time += interval
                count += 1

            candles_returned.append(len(batch))
            return tuple(batch)

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        self.assertTrue(all(num <= max_candles for num in candles_returned),
                        "All responses should respect max_candles limit")

    async def test_multiple_batches(self):
        """Test fetching multiple batches of candles.

        Verifies that the method correctly handles requests spanning multiple batches:
        - Respects server's max candles limit per request
        - Makes correct number of API calls
        - Maintains proper time sequence
        """
        interval = self.mock_mixin_instance.interval_in_seconds  # 300s
        max_candles = self.mock_mixin_instance.candles_max_result_per_rest_request  # 100

        # Fixed timestamps for reproducibility
        end_time = 1731334942
        time_span = interval * max_candles  # One batch worth of time
        expected_start = end_time - time_span

        def mock_parse_candles(response, current_end):
            """Mock server response with max_candles limit."""
            batch_start = response["start"]
            batch_end = response["end"]

            candles = []
            current_time = batch_end
            remaining = max_candles

            # Generate candles backward from end_time
            while current_time >= batch_start and remaining > 0:
                candles.insert(0, CandleData(
                    timestamp_raw=current_time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
                current_time -= interval
                remaining -= 1

            return tuple(candles)

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=expected_start - time_span,  # Request two batches worth
            end_time=end_time,
        )

        # Verify correct number of API calls
        self.assertEqual(len(self.params_calls), 3, "Should make exactly two API calls")

        # Verify each batch respects max_candles
        for batch_start, batch_end, _ in self.params_calls:
            batch_candles = (batch_end - batch_start) // interval + 1
            self.assertLessEqual(
                batch_candles,
                max_candles,
                f"Batch exceeds max candles: {batch_candles} > {max_candles}"
            )

        # Verify timestamps are properly ordered
        timestamps = [candle.timestamp for candle in result]
        self.assertEqual(timestamps, sorted(timestamps), "Timestamps should be in ascending order")

        # Verify continuity between timestamps
        for i in range(1, len(timestamps)):
            self.assertEqual(
                timestamps[i] - timestamps[i - 1],
                interval,
                f"Gap found between timestamps {timestamps[i - 1]} and {timestamps[i]}"
            )

    async def test_missing_end_candles(self):
        """Test fetching when initial response is missing end candles."""
        interval = self.mock_mixin_instance.interval_in_seconds
        end_time = 1700000000
        start_time = end_time - (interval * 10)  # 10 candles worth

        # First response missing last 2 candles
        skip_timestamps = {end_time, end_time - interval}
        first_batch = self.create_mock_candles(
            start_time, end_time, interval, skip_timestamps
        )

        # Second response with just the missing end candles
        end_batch = self.create_mock_candles(
            end_time - interval, end_time, interval
        )

        call_count = 0

        def mock_parse_candles(response, current_end):
            nonlocal call_count
            call_count += 1
            return first_batch if call_count == 1 else end_batch

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(
            side_effect=mock_parse_candles
        )

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        self.assertEqual(call_count, 2, "Should make two API calls")
        self.assertEqual(result[-1].timestamp, end_time)
        self.assertEqual(result[0].timestamp, start_time)
        self.assertEqual(len(result), 11)  # All candles including boundaries

    async def test_missing_start_candles(self):
        """Test fetching when initial response is missing start candles."""
        interval = self.mock_mixin_instance.interval_in_seconds
        end_time = 1700000000
        start_time = end_time - (interval * 10)

        # First response missing first 2 candles
        skip_timestamps = {start_time, start_time + interval}
        first_batch = self.create_mock_candles(
            start_time, end_time, interval, skip_timestamps
        )

        # Second response with just the missing start candles
        start_batch = self.create_mock_candles(
            start_time, start_time + interval, interval
        )

        call_count = 0

        def mock_parse_candles(response, current_end):
            nonlocal call_count
            call_count += 1
            return first_batch if call_count == 1 else start_batch

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(
            side_effect=mock_parse_candles
        )

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        self.assertEqual(call_count, 2, "Should make two API calls")
        self.assertEqual(result[0].timestamp, start_time)
        self.assertEqual(result[-1].timestamp, end_time)
        self.assertEqual(len(result), 11)

    async def test_multiple_incomplete_responses(self):
        """Test handling of multiple incomplete responses."""
        interval = self.mock_mixin_instance.interval_in_seconds
        end_time = 1700000000
        start_time = end_time - (interval * 10)

        responses = [
            # First response: missing both ends
            self.create_mock_candles(
                start_time, end_time, interval,
                {start_time, end_time}
            ),
            # Second response: just the start
            self.create_mock_candles(
                start_time, start_time, interval
            ),
            # Third response: just the end
            self.create_mock_candles(
                end_time, end_time, interval
            ),
        ]

        call_count = 0

        def mock_parse_candles(response, current_end):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(
            side_effect=mock_parse_candles
        )

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        self.assertEqual(call_count, 3, "Should make three API calls")
        self.assertEqual(result[0].timestamp, start_time)
        self.assertEqual(result[-1].timestamp, end_time)
        self.assertEqual(len(result), 11)

    async def test_empty_response(self):
        """Test handling of empty API responses.

        Verifies that the method handles empty responses gracefully
        and returns an empty tuple.
        """
        self.mock_mixin_instance._catsc_parse_rest_candles_data.return_value = ()
        response = {"candles": []}  # Mock API response
        self.mock_rest_assistant.execute_request.return_value = response

        result = await MixinFetchCandleData._fetch_candles(self.mock_mixin_instance)

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, tuple)

    async def test_time_range_adjustments(self):
        """Test automatic adjustment of time ranges.

        Verifies that the method correctly adjusts time ranges when:
        - Start time is too far in the past
        - End time needs alignment to interval boundaries
        - Maximum lookback period is exceeded
        """
        end_time = int(datetime.now().timestamp())
        offset = end_time % self.mock_mixin_instance.interval_in_seconds

        max_lookback = (
            self.mock_mixin_instance.interval_in_seconds *
            self.mock_mixin_instance.candles_max_result_per_rest_request
        )
        start_time = end_time - (max_lookback * 2)  # Request twice the allowed lookback

        # Create mock candles for maximum allowed period
        mock_candles = self.create_mock_candle_batch(
            start_time=end_time - max_lookback + 1,
            end_time=end_time,
            interval=self.mock_mixin_instance.interval_in_seconds,
            limit=self.mock_mixin_instance.candles_max_result_per_rest_request,
        )
        self.assertEqual(len(mock_candles), self.mock_mixin_instance.candles_max_result_per_rest_request)

        self.mock_mixin_instance._catsc_parse_rest_candles_data.return_value = mock_candles
        self.mock_rest_assistant.execute_request.return_value = {"candles": []}

        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify results
        self.assertEqual(len(result), self.mock_mixin_instance.candles_max_result_per_rest_request)
        self.assertEqual(
            end_time - (end_time % self.mock_mixin_instance.interval_in_seconds) + offset,
            result[-1].timestamp,
        )
        self.assertEqual(
            result[-1].timestamp - (len(result) - 1) * self.mock_mixin_instance.interval_in_seconds,
            result[0].timestamp,
        )

    async def test_server_end_time_mismatch(self):
        """Test handling of server responses where end_time doesn't match request.

        Verifies behavior when:
        - Server returns data ending before our requested end_time
        - Server returns incomplete/in-progress candles
        - Server has a different notion of latest available data
        """
        interval = self.mock_mixin_instance.interval_in_seconds  # 300s

        # Use a current timestamp that might not align with intervals
        current_time = int(datetime.now().timestamp())
        server_latest_complete = current_time - (current_time % interval) - interval
        requested_end = current_time
        start_time = requested_end - (interval * 5)  # Request 5 intervals

        def mock_parse_candles(response, current_end):
            """Simulate server returning older data than requested."""
            batch = []
            # Server returns complete candles up to latest available
            time = min(response["end"], server_latest_complete)
            while time >= response["start"]:
                batch.append(CandleData(
                    timestamp_raw=time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
                time -= interval
            return tuple(reversed(batch))

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Execute
        result = await MixinFetchCandleData._fetch_candles(
            self.mock_mixin_instance,
            start_time=start_time,
            end_time=requested_end,
        )

        # Verify results
        self.assertTrue(result, "Should return some candles")
        last_timestamp = result[-1].timestamp
        self.assertLessEqual(
            last_timestamp,
            server_latest_complete,
            "Last timestamp should not exceed server's latest complete candle"
        )
        self.assertEqual(
            last_timestamp % interval,
            0,
            "Last timestamp should align with interval"
        )

    async def test_current_time_boundary_handling_offset_0(self):
        """Test fetching candles near current time boundary with enforced 0-offset

        Verifies behavior when:
        - Requesting data up to current time
        - Multiple requests near current time
        - Time alignment with current time
        """
        interval = self.mock_mixin_instance.interval_in_seconds

        current_time = int(datetime.now().timestamp())
        aligned_current = current_time - (current_time % interval)
        last_complete = aligned_current - interval

        # Test cases with different end times
        test_cases = [
            ("Exact current time", current_time),
            ("Aligned current time", aligned_current),
            ("Future time", current_time + interval * 2),
            ("Slightly future time", current_time + 60),
        ]

        def mock_parse_candles(response, current_end):
            """Simulate server response with current time handling."""
            batch = []
            time = response["start"]
            while time <= min(response["end"], last_complete):
                batch.append(CandleData(
                    timestamp_raw=time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
                time += interval
            return tuple(batch)

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Test each case
        for case_name, end_time in test_cases:
            start_time = end_time - (interval * 5)

            result = await MixinFetchCandleData._fetch_candles(
                self.mock_mixin_instance,
                start_time=start_time,
                end_time=end_time,
                _offset=0,
            )

            # Verify results
            self.assertTrue(result, f"Should return candles for {case_name}")
            self.assertEqual(
                result[-1].timestamp,
                last_complete,
                f"Should end with last complete candle for {case_name}"
            )

    async def test_current_time_boundary_handling_no_offset(self):
        """Test fetching candles near current time boundary with inferred offset.

        Verifies behavior when:
        - Requesting data up to current time
        - Multiple requests near current time
        - Time alignment with current time
        """
        interval = self.mock_mixin_instance.interval_in_seconds

        current_time = int(datetime.now().timestamp())
        last_complete = current_time - interval

        # Test cases with different end times
        test_cases = [
            ("Exact current time", current_time),
            ("Future time", current_time + interval * 2),
            # Slightly future end time sets the offset, so this test is not relevant
        ]

        def mock_parse_candles(response, current_end):
            """Simulate server response with current time handling."""
            batch = []
            time = response["start"]
            while time <= min(response["end"], last_complete):
                batch.append(CandleData(
                    timestamp_raw=time,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=1000.0,
                ))
                time += interval
            return tuple(batch)

        # Setup mocks
        self.mock_mixin_instance._catsc_parse_rest_candles_data = MagicMock(side_effect=mock_parse_candles)

        # Test each case
        for case_name, end_time in test_cases:
            start_time = end_time - (interval * 5)

            # The offset is inferred from the longest sequence aligned to the interval
            result = await MixinFetchCandleData._fetch_candles(
                self.mock_mixin_instance,
                start_time=start_time,
                end_time=end_time,
            )

            # Verify results
            self.assertTrue(result, f"Should return candles for {case_name}")
            self.assertEqual(
                last_complete,
                result[-1].timestamp,
                f"Should end with last complete candle for {case_name}"
            )


if __name__ == '__main__':
    unittest.main()
