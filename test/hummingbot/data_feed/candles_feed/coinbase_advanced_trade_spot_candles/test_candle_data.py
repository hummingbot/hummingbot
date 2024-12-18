import unittest
from datetime import datetime, timezone

from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData


class TestCandleData(unittest.TestCase):
    """Tests for CandleData class."""

    def test_integer_timestamp(self):
        """Test with integer timestamp."""
        ts = 1699704000  # 2023-11-11 12:00:00 UTC
        candle = CandleData(
            timestamp_raw=ts,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.5
        )
        self.assertEqual(candle.timestamp, ts)

    def test_float_timestamp(self):
        """Test with float timestamp."""
        candle = CandleData(
            timestamp_raw=1699704000.123,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.5
        )
        self.assertEqual(candle.timestamp, 1699704000)

    def test_string_timestamp_numeric(self):
        """Test with numeric string timestamp."""
        candle = CandleData(
            timestamp_raw="1699704000",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.5
        )
        self.assertEqual(candle.timestamp, 1699704000)

    def test_string_timestamp_iso(self):
        """Test with ISO format string timestamp."""
        candle = CandleData(
            timestamp_raw="2023-11-11T12:00:00Z",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.5
        )
        expected_dt = datetime(2023, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(candle.timestamp, int(expected_dt.timestamp()))

    def test_datetime_timestamp(self):
        """Test with datetime object."""
        dt = datetime(2023, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        candle = CandleData(
            timestamp_raw=dt,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.5
        )
        self.assertEqual(candle.timestamp, int(dt.timestamp()))

    def test_naive_datetime_timestamp(self):
        """Test with naive datetime object."""
        dt = datetime(2023, 11, 11, 12, 0, 0)  # naive datetime
        candle = CandleData(
            timestamp_raw=dt,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.5
        )
        expected_dt = dt.replace(tzinfo=timezone.utc)
        self.assertEqual(candle.timestamp, int(expected_dt.timestamp()))

    def test_create_from_dict_standard_keys(self):
        """Test creating from dictionary with standard keys."""
        data = {
            'timestamp': '2023-11-11T12:00:00Z',
            'open': '100.0',
            'high': '101.0',
            'low': '99.0',
            'close': '100.5',
            'volume': '1.5'
        }
        candle = CandleData.create(data)
        expected_dt = datetime(2023, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(candle.timestamp, int(expected_dt.timestamp()))
        self.assertEqual(candle.open, 100.0)
        self.assertEqual(candle.volume, 1.5)

    def test_create_from_dict_alternative_keys(self):
        """Test creating from dictionary with alternative keys."""
        data = {
            't': 1699704000,
            'o': '100.0',
            'h': '101.0',
            'l': '99.0',
            'c': '100.5',
            'v': '1.5'
        }
        candle = CandleData.create(data)
        self.assertEqual(candle.timestamp, 1699704000)
        self.assertEqual(candle.open, 100.0)
        self.assertEqual(candle.volume, 1.5)

    def test_invalid_timestamp(self):
        """Test with invalid timestamp."""
        with self.assertRaises(ValueError):
            CandleData(
                timestamp_raw="invalid",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1.5
            )

    def test_create_missing_required_field(self):
        """Test creating with missing required field."""
        data = {
            'timestamp': '1699704000',
            'open': '100.0',
            # missing 'high'
            'low': '99.0',
            'close': '100.5',
            'volume': '1.5'
        }
        with self.assertRaises(ValueError):
            CandleData.create(data)

    def test_create_invalid_numeric_field(self):
        """Test creating with invalid numeric field."""
        data = {
            'timestamp': '1699704000',
            'open': 'invalid',
            'high': '101.0',
            'low': '99.0',
            'close': '100.5',
            'volume': '1.5'
        }
        with self.assertRaises(ValueError):
            CandleData.create(data)
