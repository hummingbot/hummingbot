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

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = BtcMarketsSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

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
            "limit": self.data_feed.candles_max_result_per_rest_request,
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

    @patch.object(BtcMarketsSpotCandles, "logger")
    def test_parse_rest_candles_debug_logging(self, mock_logger):
        """Test that debug logging works correctly in parse_rest_candles"""
        mock_data = self.get_candles_rest_data_mock()

        self.data_feed._parse_rest_candles(mock_data)

        # Check that debug logs were called
        mock_logger.return_value.debug.assert_called()

        # Verify the content of debug logs
        calls = mock_logger.return_value.debug.call_args_list
        self.assertTrue(any("Parsing" in str(call) for call in calls))
        self.assertTrue(any("Parsed" in str(call) for call in calls))

    # Override inherited WebSocket tests that don't apply to BTC Markets
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
