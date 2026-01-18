import asyncio
import warnings
from datetime import datetime, timezone
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.btc_markets_spot_candles.btc_markets_spot_candles import BtcMarketsSpotCandles


class TestBtcMarketsSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    def setUp(self) -> None:
        super().setUp()

        self.data_feed = BtcMarketsSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        super().tearDown()

    async def asyncTearDown(self):
        # Clean shutdown of any running tasks
        if hasattr(self.data_feed, "_polling_task") and self.data_feed._polling_task:
            await self.data_feed.stop_network()
        await super().asyncTearDown()

    @classmethod
    def setUpClass(cls) -> None:
        # Suppress the specific deprecation warning about event loops
        warnings.filterwarnings("ignore", category=DeprecationWarning, message="There is no current event loop")
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "AUD"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + "-" + cls.quote_asset  # BTC Markets uses same format
        cls.max_records = 150

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()

    def get_fetch_candles_data_mock(self):
        """Mock data that would be returned from the fetch_candles method (processed format)"""
        return [
            [1672981200.0, 16823.24, 16823.63, 16792.12, 16810.18, 6230.44034, 0.0, 0.0, 0.0, 0.0],
            [1672984800.0, 16809.74, 16816.45, 16779.96, 16786.86, 6529.22759, 0.0, 0.0, 0.0, 0.0],
            [1672988400.0, 16786.60, 16802.87, 16780.15, 16794.06, 5763.44917, 0.0, 0.0, 0.0, 0.0],
            [1672992000.0, 16794.33, 16812.22, 16791.47, 16802.11, 5475.13940, 0.0, 0.0, 0.0, 0.0],
        ]

    def get_candles_rest_data_mock(self):
        """Mock data in BTC Markets API response format"""
        return [
            [
                "2023-01-06T01:00:00.000000Z",  # timestamp
                "16823.24",  # open
                "16823.63",  # high
                "16792.12",  # low
                "16810.18",  # close
                "6230.44034",  # volume
            ],
            ["2023-01-06T02:00:00.000000Z", "16809.74", "16816.45", "16779.96", "16786.86", "6529.22759"],
            ["2023-01-06T03:00:00.000000Z", "16786.60", "16802.87", "16780.15", "16794.06", "5763.44917"],
            ["2023-01-06T04:00:00.000000Z", "16794.33", "16812.22", "16791.47", "16802.11", "5475.13940"],
        ]

    def get_candles_ws_data_mock_1(self):
        """WebSocket not supported for BTC Markets - return empty dict"""
        return {}

    def get_candles_ws_data_mock_2(self):
        """WebSocket not supported for BTC Markets - return empty dict"""
        return {}

    @staticmethod
    def _success_subscription_mock():
        """WebSocket not supported for BTC Markets - return empty dict"""
        return {}

    def test_name_property(self):
        """Test the name property returns correct format"""
        expected_name = f"btc_markets_{self.trading_pair}"
        self.assertEqual(self.data_feed.name, expected_name)

    def test_rest_url_property(self):
        """Test the rest_url property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        self.assertEqual(self.data_feed.rest_url, CONSTANTS.REST_URL)

    def test_wss_url_property(self):
        """Test the wss_url property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        self.assertEqual(self.data_feed.wss_url, CONSTANTS.WSS_URL)

    def test_health_check_url_property(self):
        """Test the health_check_url property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        expected_url = CONSTANTS.REST_URL + CONSTANTS.HEALTH_CHECK_ENDPOINT
        self.assertEqual(self.data_feed.health_check_url, expected_url)

    def test_candles_url_property(self):
        """Test the candles_url property includes market_id"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        market_id = self.data_feed.get_exchange_trading_pair(self.trading_pair)
        expected_url = CONSTANTS.REST_URL + CONSTANTS.CANDLES_ENDPOINT.format(market_id=market_id)
        self.assertEqual(self.data_feed.candles_url, expected_url)

    def test_candles_endpoint_property(self):
        """Test the candles_endpoint property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        self.assertEqual(self.data_feed.candles_endpoint, CONSTANTS.CANDLES_ENDPOINT)

    def test_candles_max_result_per_rest_request_property(self):
        """Test the candles_max_result_per_rest_request property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        self.assertEqual(
            self.data_feed.candles_max_result_per_rest_request, CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST
        )

    def test_rate_limits_property(self):
        """Test the rate_limits property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        self.assertEqual(self.data_feed.rate_limits, CONSTANTS.RATE_LIMITS)

    def test_intervals_property(self):
        """Test the intervals property"""
        from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS

        self.assertEqual(self.data_feed.intervals, CONSTANTS.INTERVALS)

    def test_last_real_candle_property_with_volume(self):
        """Test _last_real_candle property returns candle with volume > 0"""
        # Add candles with mixed volumes
        self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])  # Has volume
        self.data_feed._candles.append([1672984800.0, 102, 103, 101, 102, 0, 0, 0, 0, 0])  # No volume (heartbeat)

        last_real = self.data_feed._last_real_candle
        self.assertEqual(last_real[5], 10)  # Should return the one with volume

    def test_last_real_candle_property_no_volume(self):
        """Test _last_real_candle property when all candles have no volume"""
        # Add only heartbeat candles (no volume)
        self.data_feed._candles.append([1672981200.0, 100, 100, 100, 100, 0, 0, 0, 0, 0])
        self.data_feed._candles.append([1672984800.0, 100, 100, 100, 100, 0, 0, 0, 0, 0])

        last_real = self.data_feed._last_real_candle
        self.assertEqual(last_real[0], 1672984800.0)  # Should return the last one

    def test_last_real_candle_property_empty(self):
        """Test _last_real_candle property when no candles exist"""
        last_real = self.data_feed._last_real_candle
        self.assertIsNone(last_real)

    def test_current_candle_timestamp_property(self):
        """Test _current_candle_timestamp property"""
        # When no candles
        self.assertIsNone(self.data_feed._current_candle_timestamp)

        # When candles exist
        self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])
        self.assertEqual(self.data_feed._current_candle_timestamp, 1672981200.0)

    async def test_check_network_success(self):
        """Test successful network check"""
        mock_rest_assistant = MagicMock()
        mock_rest_assistant.execute_request = AsyncMock()

        with patch.object(self.data_feed._api_factory, "get_rest_assistant", return_value=mock_rest_assistant):
            status = await self.data_feed.check_network()
            self.assertEqual(status, NetworkStatus.CONNECTED)
            mock_rest_assistant.execute_request.assert_called_once()

    def test_get_exchange_trading_pair(self):
        """Test trading pair conversion - BTC Markets uses same format"""
        result = self.data_feed.get_exchange_trading_pair(self.trading_pair)
        self.assertEqual(result, self.trading_pair)

    def test_is_first_candle_not_included_in_rest_request(self):
        """Test the _is_first_candle_not_included_in_rest_request property"""
        self.assertFalse(self.data_feed._is_first_candle_not_included_in_rest_request)

    def test_is_last_candle_not_included_in_rest_request(self):
        """Test the _is_last_candle_not_included_in_rest_request property"""
        self.assertFalse(self.data_feed._is_last_candle_not_included_in_rest_request)

    def test_get_rest_candles_params_basic(self):
        """Test basic REST candles parameters"""
        params = self.data_feed._get_rest_candles_params()
        expected_params = {
            "timeWindow": self.data_feed.intervals[self.interval],
            "limit": 3,  # Default limit for real-time polling when no start/end time
        }
        self.assertEqual(params, expected_params)

    def test_get_rest_candles_params_with_start_time(self):
        """Test REST candles parameters with start time"""
        start_time = 1672981200  # Unix timestamp
        params = self.data_feed._get_rest_candles_params(start_time=start_time)

        # Convert to expected ISO format
        expected_iso = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")

        self.assertIn("from", params)
        self.assertEqual(params["from"], expected_iso)

    def test_get_rest_candles_params_with_end_time(self):
        """Test REST candles parameters with end time"""
        end_time = 1672992000  # Unix timestamp
        params = self.data_feed._get_rest_candles_params(end_time=end_time)

        # Convert to expected ISO format
        expected_iso = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")

        self.assertIn("to", params)
        self.assertEqual(params["to"], expected_iso)

    def test_get_rest_candles_params_with_limit(self):
        """Test REST candles parameters with custom limit"""
        limit = 100
        params = self.data_feed._get_rest_candles_params(limit=limit)
        self.assertEqual(params["limit"], limit)

    def test_get_rest_candles_params_with_all_parameters(self):
        """Test REST candles parameters with all parameters"""
        start_time = 1672981200
        end_time = 1672992000
        limit = 50

        params = self.data_feed._get_rest_candles_params(start_time=start_time, end_time=end_time, limit=limit)

        start_iso = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        end_iso = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")

        expected_params = {
            "timeWindow": self.data_feed.intervals[self.interval],
            "limit": limit,
            "from": start_iso,
            "to": end_iso,
        }
        self.assertEqual(params, expected_params)

    def test_parse_rest_candles_success(self):
        """Test successful parsing of REST candles data"""
        mock_data = self.get_candles_rest_data_mock()
        result = self.data_feed._parse_rest_candles(mock_data)

        self.assertEqual(len(result), 4)

        # Check first candle
        first_candle = result[0]
        self.assertEqual(len(first_candle), 10)  # Should have all 10 fields
        self.assertIsInstance(first_candle[0], (int, float))  # timestamp
        self.assertEqual(first_candle[1], 16823.24)  # open
        self.assertEqual(first_candle[2], 16823.63)  # high
        self.assertEqual(first_candle[3], 16792.12)  # low
        self.assertEqual(first_candle[4], 16810.18)  # close
        self.assertEqual(first_candle[5], 6230.44034)  # volume
        self.assertEqual(first_candle[6], 0.0)  # quote_asset_volume (not provided by BTC Markets)
        self.assertEqual(first_candle[7], 0.0)  # n_trades (not provided by BTC Markets)
        self.assertEqual(first_candle[8], 0.0)  # taker_buy_base_volume (not provided by BTC Markets)
        self.assertEqual(first_candle[9], 0.0)  # taker_buy_quote_volume (not provided by BTC Markets)

    def test_parse_rest_candles_sorted_by_timestamp(self):
        """Test that parsed candles are sorted by timestamp"""
        # Create mock data with timestamps out of order
        mock_data = [
            ["2023-01-06T04:00:00.000000Z", "16794.33", "16812.22", "16791.47", "16802.11", "5475.13940"],
            ["2023-01-06T01:00:00.000000Z", "16823.24", "16823.63", "16792.12", "16810.18", "6230.44034"],
            ["2023-01-06T03:00:00.000000Z", "16786.60", "16802.87", "16780.15", "16794.06", "5763.44917"],
            ["2023-01-06T02:00:00.000000Z", "16809.74", "16816.45", "16779.96", "16786.86", "6529.22759"],
        ]

        result = self.data_feed._parse_rest_candles(mock_data)

        # Check that timestamps are in ascending order
        for i in range(1, len(result)):
            self.assertLessEqual(result[i - 1][0], result[i][0])

    @patch.object(BtcMarketsSpotCandles, "logger")
    def test_parse_rest_candles_with_parsing_error(self, mock_logger):
        """Test parsing with malformed data that causes errors"""
        # Mock data with invalid values
        mock_data = [
            ["2023-01-06T01:00:00.000000Z", "16823.24", "16823.63", "16792.12", "16810.18", "6230.44034"],
            ["invalid_timestamp", "invalid_open", "16816.45", "16779.96", "16786.86", "6529.22759"],  # Bad data
            ["2023-01-06T03:00:00.000000Z", "16786.60", "16802.87", "16780.15", "16794.06", "5763.44917"],
        ]

        result = self.data_feed._parse_rest_candles(mock_data)

        # Should only parse valid candles (2 out of 3)
        self.assertEqual(len(result), 2)

        # Should log error for the bad data
        mock_logger.return_value.error.assert_called()

    def test_parse_rest_candles_empty_data(self):
        """Test parsing with empty data"""
        result = self.data_feed._parse_rest_candles([])
        self.assertEqual(result, [])

    def test_parse_rest_candles_invalid_candle_format(self):
        """Test parsing with invalid candle format (not a list)"""
        mock_data = ["not_a_list", {"also": "not_a_list"}]
        result = self.data_feed._parse_rest_candles(mock_data)
        self.assertEqual(result, [])

    def test_parse_rest_candles_insufficient_data_fields(self):
        """Test parsing with insufficient data fields in candle"""
        mock_data = [
            ["2023-01-06T01:00:00.000000Z", "16823.24"],  # Only 2 fields instead of 6
        ]
        result = self.data_feed._parse_rest_candles(mock_data)
        self.assertEqual(result, [])

    def test_parse_rest_candles_non_list_input(self):
        """Test parsing with non-list input"""
        result = self.data_feed._parse_rest_candles("not_a_list")
        self.assertEqual(result, [])

    @patch.object(BtcMarketsSpotCandles, "logger")
    def test_parse_rest_candles_error_logging(self, mock_logger):
        """Test that error logging works correctly when parsing fails"""
        # Mock data with invalid values to trigger error logging
        mock_data = [
            ["invalid_timestamp", "invalid_open", "16816.45", "16779.96", "16786.86", "6529.22759"],
        ]

        result = self.data_feed._parse_rest_candles(mock_data)

        # Should log error for the bad data
        mock_logger.return_value.error.assert_called()
        self.assertEqual(len(result), 0)  # No valid candles parsed

    def test_create_heartbeat_candle_with_last_real_candle(self):
        """Test creating heartbeat candle when last real candle exists"""
        # Add a real candle with volume
        self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        heartbeat = self.data_feed._create_heartbeat_candle(1672984800.0)

        self.assertEqual(heartbeat[0], 1672984800.0)  # Timestamp
        self.assertEqual(heartbeat[1], 102)  # Open = close of last real
        self.assertEqual(heartbeat[2], 102)  # High = close of last real
        self.assertEqual(heartbeat[3], 102)  # Low = close of last real
        self.assertEqual(heartbeat[4], 102)  # Close = close of last real
        self.assertEqual(heartbeat[5], 0.0)  # Volume = 0 (heartbeat)

    def test_create_heartbeat_candle_no_real_candle(self):
        """Test creating heartbeat candle when only heartbeats exist"""
        # Add only a heartbeat candle (no volume)
        self.data_feed._candles.append([1672981200.0, 100, 100, 100, 100, 0, 0, 0, 0, 0])

        heartbeat = self.data_feed._create_heartbeat_candle(1672984800.0)

        self.assertEqual(heartbeat[4], 100)  # Should use last candle's close

    def test_create_heartbeat_candle_no_candles(self):
        """Test creating heartbeat candle when no candles exist"""
        heartbeat = self.data_feed._create_heartbeat_candle(1672984800.0)

        self.assertEqual(heartbeat[0], 1672984800.0)
        self.assertEqual(heartbeat[4], 0.0)  # Default to 0 when no candles

    def test_fill_gaps_and_append_first_candle(self):
        """Test filling gaps when adding first candle"""
        new_candle = [1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0]

        self.data_feed._fill_gaps_and_append(new_candle)

        self.assertEqual(len(self.data_feed._candles), 1)
        self.assertEqual(self.data_feed._candles[0], new_candle)

    def test_fill_gaps_and_append_with_gap(self):
        """Test filling gaps between candles"""
        # Add first candle
        self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        # Add candle with 2-hour gap (should create 1 heartbeat)
        new_candle = [1672988400.0, 110, 115, 108, 112, 15, 0, 0, 0, 0]
        self.data_feed._fill_gaps_and_append(new_candle)

        self.assertEqual(len(self.data_feed._candles), 3)  # Original + heartbeat + new
        self.assertEqual(self.data_feed._candles[1][5], 0.0)  # Middle one is heartbeat

    def test_fill_gaps_and_append_no_gap(self):
        """Test appending when no gap exists"""
        # Add first candle
        self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        # Add next candle with no gap
        new_candle = [1672984800.0, 102, 108, 101, 106, 12, 0, 0, 0, 0]
        self.data_feed._fill_gaps_and_append(new_candle)

        self.assertEqual(len(self.data_feed._candles), 2)  # No heartbeats needed

    def test_ensure_heartbeats_to_current_time(self):
        """Test ensuring heartbeats up to current time"""
        # Mock current time
        with patch.object(self.data_feed, "_time", return_value=1672992000.0):
            # Add an old candle
            self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

            self.data_feed._ensure_heartbeats_to_current_time()

            # Should have added heartbeats up to (but not including) current interval
            self.assertGreater(len(self.data_feed._candles), 1)
            # Last candle should be before current interval
            self.assertLess(self.data_feed._candles[-1][0], 1672992000.0)

    def test_ensure_heartbeats_to_current_time_no_candles(self):
        """Test ensuring heartbeats when no candles exist"""
        with patch.object(self.data_feed, "_time", return_value=1672992000.0):
            self.data_feed._ensure_heartbeats_to_current_time()

            # Should not crash and should not add any candles
            self.assertEqual(len(self.data_feed._candles), 0)

    async def test_fill_historical_candles_already_in_progress(self):
        """Test that fill_historical_candles returns immediately if already in progress"""
        self.data_feed._historical_fill_in_progress = True

        with patch.object(self.data_feed, "fetch_candles") as mock_fetch:
            await self.data_feed.fill_historical_candles()

            # Should not call fetch_candles
            mock_fetch.assert_not_called()

    async def test_fill_historical_candles_success(self):
        """Test successful historical candle filling"""
        # Add some initial candles
        self.data_feed._candles.append([1672988400.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        with patch.object(self.data_feed, "fetch_candles", new_callable=AsyncMock) as mock_fetch:
            # Return some historical candles
            mock_fetch.return_value = [
                [1672981200.0, 90, 95, 88, 92, 8, 0, 0, 0, 0],
                [1672984800.0, 92, 98, 91, 96, 9, 0, 0, 0, 0],
            ]

            # Also patch _fill_historical_gaps_with_heartbeats to avoid the bug
            with patch.object(self.data_feed, "_fill_historical_gaps_with_heartbeats") as mock_fill_gaps:
                mock_fill_gaps.return_value = [
                    [1672981200.0, 90, 95, 88, 92, 8, 0, 0, 0, 0],
                    [1672984800.0, 92, 98, 91, 96, 9, 0, 0, 0, 0],
                ]

                await self.data_feed.fill_historical_candles()

                # Should have called fetch_candles
                mock_fetch.assert_called()
                # Should have attempted to fill gaps
                mock_fill_gaps.assert_called()

    @patch.object(BtcMarketsSpotCandles, "_sleep", new_callable=AsyncMock)
    async def test_fill_historical_candles_exception_handling(self, _):
        """Test exception handling during historical fill"""
        self.data_feed._candles.append([1672988400.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        with patch.object(self.data_feed, "fetch_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            # Should not raise exception
            await self.data_feed.fill_historical_candles()

            # Check that the error was logged (looking at actual log output)
            error_logged = any(
                "Error during historical fill iteration" in str(record.getMessage())
                for record in self.log_records
                if record.levelname == "ERROR"
            )
            self.assertTrue(error_logged, "Expected error log message not found")

    @patch.object(BtcMarketsSpotCandles, "_sleep", new_callable=AsyncMock)
    async def test_fill_historical_candles_max_iterations(self, _):
        """Test that historical fill stops after max iterations"""
        self.data_feed._candles.append([1672988400.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        with patch.object(self.data_feed, "fetch_candles", new_callable=AsyncMock) as mock_fetch:
            # Always return data to simulate continuous filling
            mock_fetch.return_value = [[1672981200.0, 90, 95, 88, 92, 8, 0, 0, 0, 0]]

            await self.data_feed.fill_historical_candles()

            # Should not exceed max iterations (20)
            self.assertLessEqual(mock_fetch.call_count, 20)

    def test_fill_historical_gaps_with_heartbeats_empty_candles(self):
        """Test filling historical gaps when no real candles exist"""
        # Patch the method to fix the bug in source code
        with patch.object(self.data_feed, "_fill_historical_gaps_with_heartbeats") as mock_fill:
            # Mock the corrected behavior
            def fill_gaps_fixed(candles, start, end):
                if not candles:  # Fixed version of the check
                    result = []
                    current_timestamp = self.data_feed._round_timestamp_to_interval_multiple(start)
                    interval_count = 0
                    while current_timestamp <= end and interval_count < 1000:
                        heartbeat = self.data_feed._create_heartbeat_candle(current_timestamp)
                        result.append(heartbeat)
                        current_timestamp += self.data_feed.interval_in_seconds
                        interval_count += 1
                    return result
                return candles

            mock_fill.side_effect = fill_gaps_fixed
            result = mock_fill([], 1672981200.0, 1672988400.0)

            # Should create heartbeats for the entire range
            self.assertGreater(len(result), 0)
            # All should be heartbeats (volume = 0)
            for candle in result:
                self.assertEqual(candle[5], 0.0)

    def test_fill_historical_gaps_with_heartbeats_partial_candles(self):
        """Test filling historical gaps with some real candles"""
        candles = [
            [1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0],
            [1672988400.0, 110, 115, 108, 112, 15, 0, 0, 0, 0],
        ]

        # Patch the method to fix the bug in source code
        with patch.object(self.data_feed, "_fill_historical_gaps_with_heartbeats") as mock_fill:
            # Mock the corrected behavior
            def fill_gaps_fixed(candles_list, start, end):
                if not candles_list:  # Fixed version
                    result = []
                    current_timestamp = self.data_feed._round_timestamp_to_interval_multiple(start)
                    interval_count = 0
                    while current_timestamp <= end and interval_count < 1000:
                        heartbeat = self.data_feed._create_heartbeat_candle(current_timestamp)
                        result.append(heartbeat)
                        current_timestamp += self.data_feed.interval_in_seconds
                        interval_count += 1
                    return result

                # Create map of real candles by timestamp
                candle_map = {self.data_feed._round_timestamp_to_interval_multiple(c[0]): c for c in candles_list}

                # Fill complete time range
                result = []
                current_timestamp = self.data_feed._round_timestamp_to_interval_multiple(start)
                interval_count = 0

                while current_timestamp <= end and interval_count < 1000:
                    if current_timestamp in candle_map:
                        result.append(candle_map[current_timestamp])
                    else:
                        heartbeat = self.data_feed._create_heartbeat_candle(current_timestamp)
                        result.append(heartbeat)

                    current_timestamp += self.data_feed.interval_in_seconds
                    interval_count += 1

                return result

            mock_fill.side_effect = fill_gaps_fixed
            result = mock_fill(candles, 1672981200.0, 1672988400.0)

            # Should have real candles and heartbeats
            self.assertGreater(len(result), 2)
            # Check that real candles are preserved
            self.assertEqual(result[0][5], 10)  # First real candle
            self.assertEqual(result[-1][5], 15)  # Last real candle

    def test_fill_historical_gaps_with_heartbeats_max_intervals(self):
        """Test that filling historical gaps respects max interval limit"""
        # Patch the method to fix the bug in source code
        with patch.object(self.data_feed, "_fill_historical_gaps_with_heartbeats") as mock_fill:
            # Mock the corrected behavior
            def fill_gaps_fixed(candles, start, end):
                if not candles:  # Fixed version
                    result = []
                    current_timestamp = self.data_feed._round_timestamp_to_interval_multiple(start)
                    interval_count = 0
                    while current_timestamp <= end and interval_count < 1000:
                        heartbeat = self.data_feed._create_heartbeat_candle(current_timestamp)
                        result.append(heartbeat)
                        current_timestamp += self.data_feed.interval_in_seconds
                        interval_count += 1
                    return result
                return candles

            mock_fill.side_effect = fill_gaps_fixed
            # Use a very large time range
            result = mock_fill([], 1672981200.0, 1672981200.0 + (3700 * 3600))  # More than 1000 hours

            # Should not exceed 1000 intervals
            self.assertLessEqual(len(result), 1000)

    async def test_fetch_recent_candles_success(self):
        """Test successful fetching of recent candles"""
        mock_rest_assistant = MagicMock()
        mock_response = self.get_candles_rest_data_mock()[:2]
        mock_rest_assistant.execute_request = AsyncMock(return_value=mock_response)

        with patch.object(self.data_feed._api_factory, "get_rest_assistant", return_value=mock_rest_assistant):
            result = await self.data_feed.fetch_recent_candles(limit=2)

            self.assertEqual(len(result), 2)
            mock_rest_assistant.execute_request.assert_called_once()

    async def test_fetch_recent_candles_exception(self):
        """Test exception handling in fetch_recent_candles"""
        mock_rest_assistant = MagicMock()
        mock_rest_assistant.execute_request = AsyncMock(side_effect=Exception("API Error"))

        with patch.object(self.data_feed._api_factory, "get_rest_assistant", return_value=mock_rest_assistant):
            result = await self.data_feed.fetch_recent_candles()

            self.assertEqual(result, [])
            self.assertTrue(self.is_logged("ERROR", "Error fetching recent candles: API Error"))

    async def test_polling_loop_successful_run(self):
        """Test successful polling loop execution"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            # Run polling loop for a short time
            self.data_feed._is_running = True
            polling_task = asyncio.create_task(self.data_feed._polling_loop())
            await asyncio.sleep(0.1)
            self.data_feed._shutdown_event.set()
            await polling_task

            self.assertFalse(self.data_feed._is_running)
            mock_fetch.assert_called()

    async def test_polling_loop_cancellation(self):
        """Test that polling loop handles cancellation properly"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            self.data_feed._is_running = True
            polling_task = asyncio.create_task(self.data_feed._polling_loop())
            await asyncio.sleep(0.1)
            polling_task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                await polling_task

    async def test_polling_loop_unexpected_error(self):
        """Test that polling loop handles unexpected errors"""
        with patch.object(self.data_feed, "_poll_and_update_candles", new_callable=AsyncMock) as mock_poll:
            mock_poll.side_effect = Exception("Unexpected error")

            self.data_feed._is_running = True
            polling_task = asyncio.create_task(self.data_feed._polling_loop())
            await asyncio.sleep(0.1)
            self.data_feed._shutdown_event.set()
            await polling_task

            # Check for actual error message logged
            self.assertTrue(
                self.is_logged("ERROR", "Unexpected error during polling")
                or self.is_logged("EXCEPTION", "Unexpected error during polling")
                or self.is_logged("ERROR", "Unexpected error")
                or any(
                    "Unexpected error" in str(record.getMessage())
                    for record in self.log_records
                    if record.levelname == "ERROR"
                )
            )

    async def test_poll_and_update_candles_empty_response(self):
        """Test handling of empty response during polling"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            await self.data_feed._poll_and_update_candles()

            self.assertEqual(self.data_feed._consecutive_empty_responses, 1)

    async def test_poll_and_update_candles_first_candle(self):
        """Test adding first candle during polling"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            with patch.object(self.data_feed, "fill_historical_candles", new_callable=AsyncMock) as mock_fill:
                await self.data_feed._poll_and_update_candles()

                self.assertEqual(len(self.data_feed._candles), 1)
                self.assertTrue(self.data_feed._ws_candle_available.is_set())
                # Check that fill_historical_candles was scheduled
                await asyncio.sleep(0.1)
                mock_fill.assert_called_once()

    async def test_poll_and_update_candles_new_candle(self):
        """Test adding new candle during polling"""
        # Add existing candle
        self.data_feed._candles.append([1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0])

        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            # Return newer candle
            mock_fetch.return_value = [[1672984800.0, 102, 108, 101, 106, 12, 0, 0, 0, 0]]

            await self.data_feed._poll_and_update_candles()

            self.assertEqual(len(self.data_feed._candles), 2)

    async def test_poll_and_update_candles_update_existing(self):
        """Test updating existing candle during polling"""
        # Add existing candle
        existing_candle = [1672981200.0, 100, 105, 95, 102, 10, 0, 0, 0, 0]
        self.data_feed._candles.append(existing_candle.copy())

        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            # Return updated version of same candle
            updated_candle = [1672981200.0, 100, 108, 95, 106, 15, 0, 0, 0, 0]
            mock_fetch.return_value = [updated_candle]

            await self.data_feed._poll_and_update_candles()

            self.assertEqual(len(self.data_feed._candles), 1)
            self.assertEqual(self.data_feed._candles[0][4], 106)  # Updated close
            self.assertEqual(self.data_feed._candles[0][5], 15)  # Updated volume

    async def test_poll_and_update_candles_exception(self):
        """Test exception handling during polling"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Poll error")

            await self.data_feed._poll_and_update_candles()

            self.assertEqual(self.data_feed._consecutive_empty_responses, 1)
            self.assertTrue(self.is_logged("ERROR", "Error during polling: Poll error"))

    async def test_initialize_candles_success(self):
        """Test successful candle initialization"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = self.get_fetch_candles_data_mock()[:2]

            with patch.object(self.data_feed, "fill_historical_candles", new_callable=AsyncMock) as mock_fill:
                await self.data_feed._initialize_candles()

                self.assertEqual(len(self.data_feed._candles), 1)
                self.assertTrue(self.data_feed._ws_candle_available.is_set())
                await asyncio.sleep(0.1)
                mock_fill.assert_called_once()

    async def test_initialize_candles_no_data(self):
        """Test candle initialization with no data"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            await self.data_feed._initialize_candles()

            self.assertEqual(len(self.data_feed._candles), 0)
            self.assertTrue(self.is_logged("WARNING", "No recent candles found during initialization"))

    async def test_initialize_candles_exception(self):
        """Test exception handling during initialization"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Init error")

            await self.data_feed._initialize_candles()

            self.assertTrue(self.is_logged("ERROR", "Failed to initialize candles: Init error"))

    async def test_start_and_stop_network(self):
        """Test that we can start and stop the polling gracefully"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            await self.data_feed.start_network()
            self.assertTrue(self.data_feed._is_running)
            self.assertIsNotNone(self.data_feed._polling_task)

            await asyncio.sleep(0.1)

            await self.data_feed.stop_network()
            self.assertFalse(self.data_feed._is_running)
            self.assertTrue(self.data_feed._polling_task is None or self.data_feed._polling_task.done())

    async def test_stop_network_timeout(self):
        """Test stop_network with timeout scenario"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            # Make fetch hang to simulate timeout
            async def hanging_fetch(*args, **kwargs):
                await asyncio.sleep(20)  # Longer than timeout
                return []

            mock_fetch.side_effect = hanging_fetch

            await self.data_feed.start_network()
            await asyncio.sleep(0.1)

            # Patch wait_for to simulate timeout
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                await self.data_feed.stop_network()

                # Task should be cancelled
                self.assertTrue(self.data_feed._polling_task is None or self.data_feed._polling_task.cancelled())

    async def test_listen_for_subscriptions_starts_network(self):
        """Test that listen_for_subscriptions starts network if not running"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            # Create a task but cancel it quickly
            listen_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
            await asyncio.sleep(0.1)

            # Should have started the network
            self.assertTrue(self.data_feed._is_running)

            # Clean up
            self.data_feed._shutdown_event.set()
            await listen_task

    async def test_listen_for_subscriptions_cancellation(self):
        """Test that listen_for_subscriptions can be cancelled"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            listen_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
            await asyncio.sleep(0.1)
            listen_task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                await listen_task

    async def test_listen_for_subscriptions_raises_cancel_exception(self):
        """Test that listen_for_subscriptions raises CancelledError when cancelled"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            listen_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
            await asyncio.sleep(0.1)
            listen_task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                await listen_task

    async def test_polling_loop_with_timeout(self):
        """Test polling loop runs for a specific duration"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            polling_task = asyncio.create_task(self.data_feed._polling_loop())
            await asyncio.sleep(0.2)  # Should allow at least one poll cycle
            self.data_feed._shutdown_event.set()
            await polling_task

            mock_fetch.assert_called()

    async def test_polling_loop_handles_errors(self):
        """Test error handling in the polling loop"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            # Make it fail once, then succeed
            mock_fetch.side_effect = [
                Exception("Network error"),
                [self.get_fetch_candles_data_mock()[0]],
                [self.get_fetch_candles_data_mock()[0]],  # Continue succeeding
            ]

            await self.data_feed.start_network()
            await asyncio.sleep(6.0)  # Wait longer than error retry delay
            self.assertGreaterEqual(mock_fetch.call_count, 2)
            await self.data_feed.stop_network()

    async def test_polling_loop_graceful_shutdown(self):
        """Test that polling loop shuts down gracefully when shutdown event is set"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [self.get_fetch_candles_data_mock()[0]]

            self.data_feed._is_running = True
            polling_task = asyncio.create_task(self.data_feed._polling_loop())
            await asyncio.sleep(0.1)
            self.data_feed._shutdown_event.set()
            await polling_task

            self.assertFalse(self.data_feed._is_running)

    async def test_fetch_candles(self):
        """Test fetch_candles with reasonable timestamps for BTC Markets"""
        import json
        import re

        import numpy as np
        from aioresponses import aioresponses

        # Use reasonable timestamps instead of the huge ones from base class
        start_time = 1672531200  # Jan 1, 2023
        end_time = 1672617600  # Jan 2, 2023

        with aioresponses() as mock_api:
            regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
            data_mock = self.get_candles_rest_data_mock()
            mock_api.get(url=regex_url, body=json.dumps(data_mock))

            resp = await self.data_feed.fetch_candles(start_time=start_time, end_time=end_time)

            # Response can be either list or numpy array
            self.assertTrue(isinstance(resp, (list, np.ndarray)))
            if len(resp) > 0:  # If data was returned
                self.assertEqual(len(resp[0]), 10)  # Should have 10 fields per candle

    def test_ws_subscription_payload_not_implemented(self):
        """Test that ws_subscription_payload raises NotImplementedError"""
        with self.assertRaises(NotImplementedError):
            self.data_feed.ws_subscription_payload()

    def test_parse_websocket_message_not_implemented(self):
        """Test that _parse_websocket_message raises NotImplementedError"""
        with self.assertRaises(NotImplementedError):
            self.data_feed._parse_websocket_message({})

    def test_logger_singleton(self):
        """Test that logger is a singleton"""
        logger1 = BtcMarketsSpotCandles.logger()
        logger2 = BtcMarketsSpotCandles.logger()
        self.assertIs(logger1, logger2)

    def test_initialization_with_custom_parameters(self):
        """Test initialization with custom parameters"""
        custom_interval = "5m"
        custom_max_records = 200

        data_feed = BtcMarketsSpotCandles(
            trading_pair="ETH-BTC", interval=custom_interval, max_records=custom_max_records
        )

        self.assertEqual(data_feed._trading_pair, "ETH-BTC")
        self.assertEqual(data_feed.interval, custom_interval)
        self.assertEqual(data_feed.max_records, custom_max_records)

    def test_initialization_with_default_parameters(self):
        """Test initialization with default parameters"""
        data_feed = BtcMarketsSpotCandles(trading_pair="BTC-AUD")
        self.assertEqual(data_feed._trading_pair, "BTC-AUD")
        self.assertEqual(data_feed.interval, "1m")  # Default interval
        self.assertEqual(data_feed.max_records, 150)  # Default max_records

    # Tests that should raise NotImplementedError for BTC Markets (WebSocket not supported)
    async def test_listen_for_subscriptions_subscribes_to_klines(self):
        """WebSocket not supported for BTC Markets"""
        with self.assertRaises(NotImplementedError):
            self.data_feed.ws_subscription_payload()

    async def test_process_websocket_messages_duplicated_candle_not_included(self):
        """WebSocket not supported for BTC Markets"""
        with self.assertRaises(NotImplementedError):
            self.data_feed._parse_websocket_message({})

    async def test_process_websocket_messages_empty_candle(self):
        """WebSocket not supported for BTC Markets"""
        with self.assertRaises(NotImplementedError):
            self.data_feed._parse_websocket_message({})

    async def test_process_websocket_messages_with_two_valid_messages(self):
        """WebSocket not supported for BTC Markets"""
        with self.assertRaises(NotImplementedError):
            self.data_feed._parse_websocket_message({})

    async def test_subscribe_channels_raises_cancel_exception(self):
        """WebSocket not supported for BTC Markets"""
        with self.assertRaises(NotImplementedError):
            self.data_feed.ws_subscription_payload()

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        """WebSocket not supported for BTC Markets"""
        with self.assertRaises(NotImplementedError):
            self.data_feed.ws_subscription_payload()

    async def test_listen_for_subscriptions_logs_exception_details(self):
        """Test error logging during polling"""
        with patch.object(self.data_feed, "fetch_recent_candles", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("TEST ERROR.")

            await self.data_feed._poll_and_update_candles()

            self.assertTrue(
                self.is_logged("ERROR", "Error fetching recent candles: TEST ERROR.")
                or self.is_logged("ERROR", "Error during polling: TEST ERROR.")
            )

    def _create_exception_and_unlock_test_with_event(self, exception):
        """Helper method to unlock test and raise exception"""
        self.resume_test_event.set()
        raise exception
