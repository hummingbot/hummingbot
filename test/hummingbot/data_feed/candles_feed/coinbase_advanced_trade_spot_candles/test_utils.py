import unittest
from collections import deque
from typing import Sequence

import numpy as np

from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.utils import (
    CandleArray,
    _t_to_i,
    adjust_start_end_to_interval,
    merge_sanitized_collections,
    sanitize_data,
    update_deque_from_sequence,
)


class TestDequeTypedUpdate(unittest.IsolatedAsyncioTestCase):
    """Test suite for updating typed deque[CandleArray] from sequences."""

    def create_candle_data(self, base_time: float, count: int) -> tuple[tuple[float, ...], ...]:
        """Create list of candle data lists.

        :param base_time: Base timestamp
        :param count: Number of candles to create
        :return: List of [timestamp, open, high, low, close, volume] lists
        """
        return tuple(
            (base_time + i * 300, 100.0, 101.0, 99.0, 100.5, 1000.0)
            for i in range(count)
        )

    def print_deque_state(self, d: deque[CandleArray], msg: str) -> None:
        """Helper to print deque state."""
        print(f"\n{msg}")
        print(f"Deque length: {len(d)}/{d.maxlen}")
        if d:
            print(f"First candle: {d[0]}")
            print(f"Last candle: {d[-1]}")
            print("Timestamps:", [arr[0] for arr in d])

    async def test_empty_deque(self):
        """Test updating an empty deque."""
        maxlen = 5
        d: deque[CandleArray] = deque(maxlen=maxlen)

        # Create 7 candles
        candles = self.create_candle_data(1000, 7)

        print("\nEmpty Deque Test:")
        print("Input data:", [data[0] for data in candles])

        update_deque_from_sequence(
            d, candles, False
        )

        self.print_deque_state(d, "After update")

        # Verify type and content
        self.assertEqual(len(d), maxlen)
        self.assertTrue(all(isinstance(x, np.ndarray) for x in d))
        self.assertTrue(all(x.dtype == np.float64 for x in d))

    def test_extend_right(self):
        """Test extending with newer candles."""
        maxlen = 5
        d: deque[CandleArray] = deque(maxlen=maxlen)

        # Initialize with 3 candles
        initial_data = self.create_candle_data(10000, 3)
        initial_arrays = [np.array(x, dtype=np.float64) for x in initial_data]
        d.extend(initial_arrays)

        # Add newer candles
        new_data = self.create_candle_data(10900, 3)

        self.print_deque_state(d, "Initial state")
        print("New data timestamps:", [x[0] for x in new_data])

        update_deque_from_sequence(d, new_data, False)

        self.print_deque_state(d, "After update")

        # Verify ordering and types
        self.assertLessEqual(len(d), maxlen)
        timestamps = [x[0] for x in d]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertTrue(all(x.dtype == np.float64 for x in d))

    def test_extend_left(self):
        """Test extending with older candles."""
        maxlen = 5
        d: deque[CandleArray] = deque(maxlen=maxlen)

        # Initialize with newer candles
        initial_data = self.create_candle_data(10900, 3)
        initial_arrays = [np.array(x, dtype=np.float64) for x in initial_data]
        d.extend(initial_arrays)

        # Add older candles
        older_data = self.create_candle_data(10000, 3)

        self.print_deque_state(d, "Initial state")
        print("Older data timestamps:", [x[0] for x in older_data])

        update_deque_from_sequence(d, older_data, True)

        self.print_deque_state(d, "After update")

        # Verify ordering and types
        self.assertLessEqual(len(d), maxlen)
        timestamps = [x[0] for x in d]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertTrue(all(x.dtype == np.float64 for x in d))

    def test_mixed_input_types(self):
        """Test handling of different input sequence types."""
        maxlen = 5
        d: deque[CandleArray] = deque(maxlen=maxlen)

        # Test with different sequence types
        test_data = [
            ("List of lists", self.create_candle_data(10000, 2)),
            ("List of tuples", [(10600.0, 100.0, 101.0, 99.0, 100.5, 1000.0),
                                (10900.0, 101.0, 102.0, 100.0, 101.5, 1100.0)]),
            ("Tuple of lists", tuple([
                [101200.0, 100.0, 101.0, 99.0, 100.5, 1000.0],
                [101500.0, 101.0, 102.0, 100.0, 101.5, 1100.0]
            ])),
        ]

        for name, data in test_data:
            print(f"\n=== Testing {name} ===")
            update_deque_from_sequence(d, data, False)

            self.print_deque_state(d, f"After {name}")
            self.assertTrue(all(isinstance(x, np.ndarray) for x in d))
            self.assertTrue(all(x.dtype == np.float64 for x in d))

    def test_dtype_consistency(self):
        """Test consistency of numpy array dtypes."""
        maxlen = 5
        d: deque[CandleArray] = deque(maxlen=maxlen)

        # Test with integer timestamps
        data_with_ints = [
            [10000, 100, 101, 99, 100, 1000],  # integers
            [10300.0, 100.5, 101.5, 99.5, 100.5, 1000.5],  # floats
        ]

        update_deque_from_sequence(d, data_with_ints, False)

        print("\nDtype Consistency Test:")
        for arr in d:
            print(f"Array dtype: {arr.dtype}")
            print(f"First element type: {type(arr[0])}")

        # Verify all arrays are float64
        self.assertTrue(all(x.dtype == np.float64 for x in d))


class TestSanitizeData(unittest.TestCase):
    """Tests for sanitize_data function."""

    def create_candles(self, timestamps: Sequence[int]) -> tuple[CandleData, ...]:
        """Helper to create test candle data."""
        return tuple(
            CandleData(
                timestamp_raw=ts,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            )
            for ts in timestamps
        )

    def test_sanitize_with_bounds(self):
        """Test sanitization with bounds."""
        # Create test data
        candles = [
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1060, open=101, high=102, low=100, close=101, volume=1),
            CandleData(timestamp_raw=1120, open=102, high=103, low=101, close=102, volume=1),
            # Invalid interval
            CandleData(timestamp_raw=1200, open=103, high=104, low=102, close=103, volume=1),
            CandleData(timestamp_raw=1260, open=104, high=105, low=103, close=104, volume=1),
            CandleData(timestamp_raw=1320, open=105, high=106, low=104, close=105, volume=1),
        ]

        # Test with both bounds
        result = sanitize_data(
            tuple(candles),
            interval_in_s=60,
            inclusive_bounds=(1060, 1260)
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].timestamp, 1200)
        self.assertEqual(result[-1].timestamp, 1260)

        # Test with only start bound
        result = sanitize_data(
            tuple(candles),
            interval_in_s=60,
            inclusive_bounds=(1120, None)
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].timestamp, 1200)

        # Test with only end bound
        result = sanitize_data(
            tuple(candles),
            interval_in_s=60,
            inclusive_bounds=(None, 1120)
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1].timestamp, 1120)

    def test_sanitize_empty_after_bounds(self):
        """Test when data becomes empty after applying bounds."""
        candles = [
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1060, open=101, high=102, low=100, close=101, volume=1),
        ]

        result = sanitize_data(
            tuple(candles),
            interval_in_s=60,
            inclusive_bounds=(2000, 3000)
        )
        self.assertEqual(len(result), 0)

    def test_sanitize_invalid_intervals_with_bounds(self):
        """Test handling invalid intervals with bounds."""
        candles = [
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1030, open=101, high=102, low=100, close=101, volume=1),  # Invalid interval
            CandleData(timestamp_raw=1060, open=102, high=103, low=101, close=102, volume=1),
            CandleData(timestamp_raw=1120, open=103, high=104, low=102, close=103, volume=1),
            CandleData(timestamp_raw=1180, open=104, high=105, low=103, close=104, volume=1),
        ]

        result = sanitize_data(
            tuple(candles),
            interval_in_s=60,
            inclusive_bounds=(1000, 1180)
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].timestamp, 1060)
        self.assertEqual(result[-1].timestamp, 1180)

    def test_edge_cases0(self):
        """Test edge cases."""
        # Empty input
        result = sanitize_data(
            (),
            interval_in_s=60,
            inclusive_bounds=(1000, 2000)
        )
        self.assertEqual(len(result), 0)

        # Single candle
        candles = [
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1)
        ]
        result = sanitize_data(
            tuple(candles),
            interval_in_s=60,
            inclusive_bounds=(1000, 1000)
        )
        self.assertEqual(len(result), 1)

    def test_largest_valid_sequence(self):
        """Test finding largest consecutive sequence of valid intervals."""
        interval = 300

        # Valid sequence in the middle
        timestamps = [
            1700000000,  # Start (invalid gap)
            1700000900,  # Start of valid sequence
            1700001200,
            1700001500,
            1700001800,
            1700002100,  # End of valid sequence
            1700002700,  # Invalid gap starts
        ]

        candles = self.create_candles(timestamps)
        result = sanitize_data(candles, interval)

        expected_sequence = timestamps[1:6]  # The valid middle sequence
        self.assertEqual(
            [c.timestamp for c in result],
            expected_sequence
        )

    def test_multiple_valid_sequences(self):
        """Test handling multiple valid sequences of different lengths."""
        interval = 300

        # Two valid sequences, one longer than the other
        timestamps = [
            # First sequence (3 intervals)
            1700000000,
            1700000300,
            1700000600,
            # Gap
            1700001200,
            # Second sequence (4 intervals)
            1700002000,
            1700002300,
            1700002600,
            1700002900,
            # Invalid end
            1700003600,
        ]

        candles = self.create_candles(timestamps)
        result = sanitize_data(candles, interval)

        # Should return the longer sequence
        expected_sequence = timestamps[4:8]
        self.assertEqual(
            expected_sequence,
            [c.timestamp for c in result],
            "Should select the sequence 2000->2900 as it's the longest valid sequence",
        )

    def test_invalid_segments(self):
        """Test handling various invalid segments."""
        interval = 300

        # Mix of valid and invalid segments
        timestamps = [
            # Invalid start
            1700000000,
            1700000400,  # Wrong interval
            # Valid sequence
            1700001000,
            1700001300,
            1700001600,
            # Invalid middle
            1700002000,
            # Another valid sequence
            1700002500,
            1700002800,
            # Invalid end
            1700003500,
        ]

        candles = self.create_candles(timestamps)
        result = sanitize_data(candles, interval)

        # Should return the longest valid sequence
        expected_sequence = timestamps[2:5]
        self.assertEqual(
            [c.timestamp for c in result],
            expected_sequence
        )

    def test_bounds_with_sequences(self):
        """Test bounds handling with multiple sequences."""
        interval = 300

        timestamps = [
            1700000000,
            1700000300,
            1700000600,
            1700001200,  # Gap
            1700001500,
            1700001800,
            1700002100,
        ]

        # Test bounds that cut through valid sequences
        bounds = (1700000300, 1700001800)
        candles = self.create_candles(timestamps)
        result = sanitize_data(candles, interval, bounds)

        # Should return the longest valid sequence within bounds
        self.assertTrue(all(
            bounds[0] <= c.timestamp <= bounds[1]
            for c in result
        ))

    def test_edge_cases(self):
        """Test edge cases and special scenarios."""
        interval = 300

        test_cases = [
            # Single valid pair
            ([1700000000, 1700000300], [1700000000, 1700000300]),
            # All invalid intervals, 1700000400 is a valid TS with offset=0
            ([1700000000, 1700000400, 1700000900], [1700000900]),
            # All invalid intervals, 1700000900 is a valid TS with offset=0
            ([1700000000, 1700000550, 1700000900, 1700001300], [1700001300]),
            # Multiple equal-length valid sequences
            ([1700000000, 1700000300, 1700000600,
              1700001200, 1700001500, 1700001800],
             [1700001200, 1700001500, 1700001800]),  # Last sequence
        ]

        for input_ts, expected_ts in test_cases:
            candles = self.create_candles(input_ts)
            result = sanitize_data(candles, interval)

            self.assertEqual(
                expected_ts,
                [c.timestamp for c in result],
            )

    def test_equal_length_sequences(self):
        """Test handling of equal-length sequences.

        When multiple sequences have the same length, should choose
        the most recent one as older data might drop out of window.
        """
        interval = 300

        timestamps = [
            # First sequence
            1700000000,
            1700000300,
            1700000600,
            1700000900,  # End of first sequence
            1700001500,  # Gap
            # Second sequence (same length)
            1700002000,
            1700002300,
            1700002600,
            1700002900,  # End of second sequence
            1700003500,  # Gap
        ]

        candles = self.create_candles(timestamps)
        result = sanitize_data(candles, interval)

        # Find and print all valid sequences
        sequences = []
        current_seq = []
        for i in range(len(timestamps) - 1):
            if not current_seq:
                current_seq = [timestamps[i]]

            if timestamps[i + 1] - timestamps[i] == interval:
                current_seq.append(timestamps[i + 1])
            else:
                if len(current_seq) > 1:
                    sequences.append(current_seq)
                current_seq = []

        if current_seq:
            sequences.append(current_seq)

        # Should return the more recent sequence of equal length
        expected_sequence = timestamps[5:9]  # [2000, 2300, 2600, 2900]
        self.assertEqual(
            [c.timestamp for c in result],
            expected_sequence,
            "Should select the most recent sequence when lengths are equal"
        )


class TestMergeSanitizedCollections(unittest.TestCase):
    """Tests for merge_sanitized_collections function."""

    def test_merge_continuous_sequence(self):
        """Test merging when sequences are continuous."""
        existing = [
            CandleData(timestamp_raw=1120, open=102, high=103, low=101, close=102, volume=1),
            CandleData(timestamp_raw=1180, open=103, high=104, low=102, close=103, volume=1),
        ]

        new_candles = (
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1060, open=101, high=102, low=100, close=101, volume=1),
        )

        # Should merge because 1060 + 60 = 1120 (start of existing)
        result = merge_sanitized_collections(existing, new_candles, 60)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].timestamp, 1000)
        self.assertEqual(result[-1].timestamp, 1180)

    def test_merge_continuous_sequence_end(self):
        """Test merging when sequences are continuous."""
        existing = [
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1060, open=101, high=102, low=100, close=101, volume=1),
        ]

        new_candles = (
            CandleData(timestamp_raw=1120, open=102, high=103, low=101, close=102, volume=1),
            CandleData(timestamp_raw=1180, open=103, high=104, low=102, close=103, volume=1),
        )

        # Should merge because 1060 + 60 = 1120 (start of existing)
        result = merge_sanitized_collections(existing, new_candles, 60)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].timestamp, 1000)
        self.assertEqual(result[-1].timestamp, 1180)

    def test_reject_non_continuous(self):
        """Test rejecting merge when sequences aren't continuous."""
        existing = [
            CandleData(timestamp_raw=1120, open=102, high=103, low=101, close=102, volume=1),
            CandleData(timestamp_raw=1180, open=103, high=104, low=102, close=103, volume=1),
        ]

        new_candles = (
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1030, open=101, high=102, low=100, close=101, volume=1),
        )

        # Should not merge because there's a gap
        result = merge_sanitized_collections(existing, new_candles, 60)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].timestamp, 1120)  # Keeps existing sequence

    def test_empty_collections(self):
        """Test handling empty collections."""
        existing = []
        new_candles = (
            CandleData(timestamp_raw=1000, open=100, high=101, low=99, close=100, volume=1),
            CandleData(timestamp_raw=1060, open=101, high=102, low=100, close=101, volume=1),
        )

        result = merge_sanitized_collections(existing, new_candles, 60)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].timestamp, 1000)


class TestTimeAdjustment(unittest.TestCase):
    """Test suite for the adjust_start_end_to_interval function.

    Tests the alignment of start and end times where:
    - adjusted_start should always be >= original start_time
    - adjusted_end is aligned to interval
    - None values are properly handled
    """

    def test__t_to_i_offset_none(self):
        """Test timestamp to interval alignment.

        Without offset, there is no way to know how to align the timestamp.
        The function should return the timestamp as is.
        """
        interval = 300  # 5 minutes

        test_cases = [
            # (input, expected)
            (1700000100, 1700000100),
            (1700000101, 1700000101),
            (1700000299, 1700000299),
        ]

        for input_ts, expected in test_cases:
            result = _t_to_i(input_ts, interval)
            self.assertEqual(result, expected)
            self.assertLessEqual(result, input_ts)

        for input_ts, expected in test_cases:
            result = _t_to_i(input_ts, interval, _next=True)
            self.assertEqual(result, expected + interval)
            self.assertLessEqual(result, input_ts + interval)

    def test__t_to_i_offset_0(self):
        """Test timestamp to interval alignment.

        Verifies that timestamps are correctly aligned to intervals by
        truncating to the nearest interval boundary with 0 offset.
        """
        interval = 300  # 5 minutes
        offset = 0

        test_cases = [
            # (input, expected)
            (1700000100, 1700000100),  # Already aligned at start of interval
            (1700000101, 1700000100),  # Just after interval
            (1700000299, 1700000100),  # Just before next interval
            (1700000400, 1700000400),  # Aligned to start of next interval
            (1700000401, 1700000400),  # Aligned to start of next interval
        ]

        for input_ts, expected in test_cases:
            result = _t_to_i(input_ts, interval, offset=offset)
            self.assertEqual(result, expected)
            self.assertEqual(result % interval, offset)
            self.assertLessEqual(result, input_ts)

        for input_ts, expected in test_cases:
            result = _t_to_i(input_ts, interval, offset=offset, _next=True)
            self.assertEqual(result, expected + interval)
            self.assertEqual(result % interval, offset)
            self.assertGreaterEqual(result, input_ts)

    def test__t_to_i_offset_handling(self):
        """Test the basic offset handling behavior.

        When offset is provided:
        1. Subtract offset from timestamp
        2. Align to interval
        3. Add offset back
        """
        interval = 300  # 5 minutes
        offset = -100

        test_cases = [
            # (input timestamp, expected with offset)
            (1700000000, 1700000000),  # Already aligned with offset
            (1700000001, 1700000000),  # Just after offset
            (1700000299, 1700000000),  # Just before next offset
            (1700000301, 1700000300),  # At next offset
        ]

        for input_ts, expected in test_cases:
            result = _t_to_i(input_ts, interval, offset=offset)
            self.assertEqual(result, expected)
            self.assertEqual(result % interval, interval + offset)

        for input_ts, expected in test_cases:
            result = _t_to_i(input_ts, interval, offset=offset, _next=True)
            self.assertEqual(result, expected + interval)
            self.assertEqual(result % interval, interval + offset)

    def test_basic_alignment(self):
        """Test basic interval alignment."""
        interval = 300  # 5 minutes

        # Test case where start_time is already aligned
        end_time = 1700000400  # Aligned
        start_time = 1700000100  # Aligned

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time,
            interval,
            start_time=start_time,
        )

        self.assertEqual(start_time, adjusted_start, )
        self.assertEqual(end_time, adjusted_end, )
        self.assertEqual(0, adjusted_start % interval, )

        # Test case where start_time needs alignment to the end_time adjusted offset
        start_time = 1700000101  # Unaligned

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time,
            interval,
            start_time=start_time,
        )

        self.assertEqual(end_time, adjusted_end, )
        self.assertGreaterEqual(start_time, adjusted_start, )
        self.assertEqual(0, adjusted_start % interval, )

    def test_basic_offset_none_alignment(self):
        """Test basic interval alignment."""
        interval = 300  # 5 minutes
        infered_offset = 50

        # Test case where start_time is already aligned
        end_time = (1700000450, 1700000400 + infered_offset)  # Aligned to unknown offset, setting 50 internally for start
        start_time = (1700000100, 1699999800 + infered_offset)  # Misaligned, it falls in the previous interval

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time[0],
            interval,
            start_time=start_time[0],
        )

        self.assertEqual(adjusted_start, start_time[1])
        self.assertEqual(adjusted_end, end_time[1])

        # Test case where start_time needs alignment to the end_time adjusted offset
        start_time = (1700000101, 1699999850)  # Misaligned

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time[0],
            interval,
            start_time=start_time[0],
        )

        self.assertEqual(adjusted_start, start_time[1])
        self.assertEqual(adjusted_start % interval, infered_offset)

    def test_basic_offset_50_alignment(self):
        """Test basic interval alignment."""
        interval = 300  # 5 minutes
        offset = 50

        # Test case where start_time is already aligned
        end_time = (1700000450, 1700000400 + offset)  # Aligned with offset
        start_time = (1700000100, 1699999800 + offset)  # Misaligned, it falls in the previous interval

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time[0],
            interval,
            start_time=start_time[0],
            offset=offset
        )

        self.assertEqual(adjusted_start, start_time[1])
        self.assertEqual(adjusted_end, end_time[1])

        # Test case where start_time needs alignment to the end_time adjusted offset
        start_time = (1700000101, 1699999800 + offset)  # Misaligned

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time[0],
            interval,
            start_time=start_time[0],
            offset=offset
        )

        self.assertEqual(adjusted_start, start_time[1])
        self.assertEqual(adjusted_start % interval, offset)

    def test_start_time_handling(self):
        """Test that adjusted start time is never before original start time."""
        interval = 300

        test_cases = [
            (1700000001, 201),  # sets end_time with an implicit offset of 201
            (1700000299, 199),
            (1700000300, 200),
        ]

        for start_time, implicit_offset in test_cases:
            end_time = start_time + interval * 2
            adjusted_start, adjusted_end = adjust_start_end_to_interval(
                end_time,
                interval,
                start_time=start_time,
            )

            self.assertGreaterEqual(adjusted_start, start_time)
            # Adjusted start should be aligned to within the implicit offset
            self.assertEqual(adjusted_start % interval, implicit_offset)

    def test_max_lookback_enforcement(self):
        """Test enforcement of max lookback period."""
        interval = 300
        limit = 10

        end_time = 1700000000  # Aligned to implicit offset=200
        start_time = end_time - 2 * limit * interval  # 20 intervals worth of time

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time,
            interval,
            start_time=start_time,
            limit=limit,
        )

        self.assertLessEqual(adjusted_end - adjusted_start, limit * interval)
        self.assertGreaterEqual(adjusted_start, start_time)
        self.assertEqual(adjusted_start % interval, 200)

    def test_start_end_none_handling(self):
        """Test handling of None inputs."""
        interval = 300
        limit = 10

        # Test with None start_time
        end_time = 1700000400
        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time,
            interval,
            start_time=None,
            limit=limit,
        )

        self.assertEqual(adjusted_end, end_time)
        self.assertEqual(limit, (adjusted_end - adjusted_start) // interval + 1, )

        # Test with None end_time
        start_time = 1700000000
        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            None,
            interval,
            start_time=start_time,
            limit=limit,
        )

        self.assertGreaterEqual(adjusted_start, start_time)
        # With end_time=None, the current time is used, thus there is
        # an unknown implicit offset, which should be the same for adjusted_start/end
        self.assertGreaterEqual(adjusted_start % interval, 0)
        self.assertEqual(adjusted_end % interval, adjusted_start % interval)

    def test_inverted_time_range(self):
        """Test handling of start time after end time."""
        interval = 300
        end_time = 1700000400  # Aligned to an offset=0
        start_time = end_time + interval  # Start is after end

        adjusted_start, adjusted_end = adjust_start_end_to_interval(
            end_time,
            interval,
            start_time=start_time,
        )

        self.assertEqual(adjusted_start, adjusted_end)
        self.assertEqual(adjusted_end % interval, 0)
        self.assertEqual(adjusted_start % interval, 0)
