import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase
from unittest.mock import AsyncMock, patch

import numpy as np
from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.lighter_spot_candles import LighterSpotCandles, constants as CONSTANTS

PATCH_FETCH = "hummingbot.data_feed.candles_feed.lighter_spot_candles.lighter_spot_candles.LighterSpotCandles.fetch_candles"
PATCH_SLEEP = "hummingbot.data_feed.candles_feed.lighter_spot_candles.lighter_spot_candles.LighterSpotCandles._sleep"


class TestLighterSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset  # get_exchange_trading_pair returns "BTC"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = LighterSpotCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed._market_id = 1  # pre-set to skip initialize_exchange_data API call
        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    # ---- Mock data ----

    @staticmethod
    def get_candles_rest_data_mock():
        return {
            "c": [
                {"t": 1748954160000, "o": 94000.0, "h": 94150.0, "l": 93850.0, "c": 94050.0, "v": 0.50, "V": 47025.0},
                {"t": 1748954220000, "o": 94050.0, "h": 94200.0, "l": 94000.0, "c": 94180.0, "v": 0.35, "V": 32963.0},
                {"t": 1748954280000, "o": 94180.0, "h": 94300.0, "l": 94100.0, "c": 94250.0, "v": 0.62, "V": 58435.0},
                {"t": 1748954340000, "o": 94250.0, "h": 94400.0, "l": 94200.0, "c": 94350.0, "v": 0.48, "V": 45288.0},
            ]
        }

    def get_fetch_candles_data_mock(self):
        return [
            [1748954160.0, 94000.0, 94150.0, 93850.0, 94050.0, 0.50, 47025.0, 0.0, 0.0, 0.0],
            [1748954220.0, 94050.0, 94200.0, 94000.0, 94180.0, 0.35, 32963.0, 0.0, 0.0, 0.0],
            [1748954280.0, 94180.0, 94300.0, 94100.0, 94250.0, 0.62, 58435.0, 0.0, 0.0, 0.0],
            [1748954340.0, 94250.0, 94400.0, 94200.0, 94350.0, 0.48, 45288.0, 0.0, 0.0, 0.0],
        ]

    @staticmethod
    def get_candles_ws_data_mock_1():
        # Lighter uses polling, not WebSocket
        return {}

    @staticmethod
    def get_candles_ws_data_mock_2():
        return {}

    @staticmethod
    def _success_subscription_mock():
        return {}

    # ---- Property tests ----

    def test_name_property(self):
        self.assertEqual(self.data_feed.name, "lighter_BTC-USDC")

    def test_rest_url_property(self):
        self.assertEqual(self.data_feed.rest_url, CONSTANTS.MAINNET_BASE_URL)

    def test_candles_url_property(self):
        expected = f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.CANDLES_PATH_URL}"
        self.assertEqual(self.data_feed.candles_url, expected)

    def test_candles_max_result_per_rest_request(self):
        self.assertEqual(
            self.data_feed.candles_max_result_per_rest_request,
            CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST,
        )

    def test_ws_subscription_payload_is_empty(self):
        self.assertEqual(self.data_feed.ws_subscription_payload(), {})

    def test_parse_websocket_message_returns_none(self):
        self.assertIsNone(self.data_feed._parse_websocket_message({}))

    def test_rate_limits(self):
        self.assertEqual(self.data_feed.rate_limits, CONSTANTS.RATE_LIMITS)

    def test_intervals(self):
        for interval in ("1m", "5m", "15m", "30m", "1h", "4h", "12h", "1d", "1w"):
            self.assertIn(interval, self.data_feed.intervals)

    # ---- REST candles tests ----

    @aioresponses()
    async def test_fetch_candles(self, mock_api):
        # Override base test: _market_id is pre-set in setUp
        regex_url = re.compile(
            f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?")
        )
        mock_api.get(url=regex_url, body=json.dumps(self.get_candles_rest_data_mock()))
        resp = await self.data_feed.fetch_candles(
            start_time=int(self.start_time), end_time=int(self.end_time)
        )
        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    def test_parse_rest_candles(self):
        data = self.get_candles_rest_data_mock()
        result = self.data_feed._parse_rest_candles(data)
        expected = self.get_fetch_candles_data_mock()
        self.assertEqual(len(result), len(expected))
        for row, exp in zip(result, expected):
            self.assertAlmostEqual(row[0], exp[0])
            self.assertAlmostEqual(row[1], exp[1])
            self.assertAlmostEqual(row[4], exp[4])
            self.assertAlmostEqual(row[6], exp[6])

    def test_parse_rest_candles_filters_future(self):
        data = self.get_candles_rest_data_mock()
        result = self.data_feed._parse_rest_candles(data, end_time=1748954220.0)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][0], 1748954160.0)
        self.assertAlmostEqual(result[1][0], 1748954220.0)

    def test_parse_rest_candles_empty_data(self):
        self.assertEqual(self.data_feed._parse_rest_candles({}), [])
        self.assertEqual(self.data_feed._parse_rest_candles({"c": []}), [])

    def test_get_rest_candles_params(self):
        params = self.data_feed._get_rest_candles_params(
            start_time=1748954160, end_time=1748954400
        )
        self.assertEqual(params["market_id"], 1)
        self.assertEqual(params["resolution"], "1m")
        self.assertEqual(params["start_timestamp"], 1748954160000)
        self.assertEqual(params["end_timestamp"], 1748954400000)
        self.assertGreaterEqual(params["count_back"], 1)

    def test_get_rest_candles_params_count_back(self):
        # 4-hour range at 1m interval → 240 bars
        params = self.data_feed._get_rest_candles_params(
            start_time=1748940000, end_time=1748954400
        )
        self.assertEqual(params["count_back"], 240)

    def test_get_rest_candles_params_count_back_minimum_one(self):
        # Even tiny ranges give count_back >= 1
        params = self.data_feed._get_rest_candles_params(
            start_time=1748954160, end_time=1748954161
        )
        self.assertEqual(params["count_back"], 1)

    # ---- initialize_exchange_data tests ----

    @aioresponses()
    async def test_initialize_exchange_data_sets_market_id(self, mock_api):
        self.data_feed._market_id = None
        order_book_details_url = (
            f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL}"
        )
        mock_api.get(
            url=order_book_details_url,
            body=json.dumps({
                "order_book_details": [
                    {"market_id": 1, "symbol": "BTC"},
                    {"market_id": 2, "symbol": "ETH"},
                ]
            }),
        )
        await self.data_feed.initialize_exchange_data()
        self.assertEqual(self.data_feed._market_id, 1)

    @aioresponses()
    async def test_initialize_exchange_data_case_insensitive(self, mock_api):
        self.data_feed._market_id = None
        order_book_details_url = (
            f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL}"
        )
        mock_api.get(
            url=order_book_details_url,
            body=json.dumps({
                "order_book_details": [
                    {"market_id": 1, "symbol": "btc"},
                ]
            }),
        )
        await self.data_feed.initialize_exchange_data()
        self.assertEqual(self.data_feed._market_id, 1)

    async def test_initialize_exchange_data_skips_if_already_set(self):
        # _market_id already set in setUp — no API call should be made
        with patch.object(
            self.data_feed._api_factory, "get_rest_assistant", new_callable=AsyncMock
        ) as mock_rest:
            await self.data_feed.initialize_exchange_data()
            mock_rest.assert_not_called()

    @aioresponses()
    async def test_initialize_exchange_data_raises_if_market_not_found(self, mock_api):
        self.data_feed._market_id = None
        order_book_details_url = (
            f"{CONSTANTS.MAINNET_BASE_URL}{CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL}"
        )
        mock_api.get(
            url=order_book_details_url,
            body=json.dumps({"order_book_details": [{"market_id": 2, "symbol": "ETH"}]}),
        )
        with self.assertRaises(ValueError) as ctx:
            await self.data_feed.initialize_exchange_data()
        self.assertIn("BTC-USDC", str(ctx.exception))

    # ---- check_network tests ----

    @aioresponses()
    async def test_check_network_returns_connected(self, mock_api):
        mock_api.get(
            url=self.data_feed.health_check_url,
            body=json.dumps({"status": "ok"}),
        )
        status = await self.data_feed.check_network()
        self.assertEqual(status, NetworkStatus.CONNECTED)

    # ---- Polling / listen_for_subscriptions tests ----
    # Lighter uses REST polling instead of WebSocket, so all WS-based base tests are overridden.

    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_fetch):
        mock_fetch.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.data_feed.listen_for_subscriptions()

    @patch(PATCH_SLEEP, new_callable=AsyncMock)
    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_fetch, mock_sleep):
        mock_fetch.side_effect = Exception("TEST ERROR.")
        mock_sleep.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError()
        )
        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())
        await self.resume_test_event.wait()
        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error polling Lighter candles. Retrying in 5s...")
        )

    async def test_listen_for_subscriptions_subscribes_to_klines(self):
        # Override: lighter polls REST — verify first poll sets _ws_candle_available and schedules fill
        candle = np.array(
            [[1748954160.0, 94000.0, 94150.0, 93850.0, 94050.0, 0.50, 47025.0, 0.0, 0.0, 0.0]]
        )
        with patch(PATCH_FETCH, new_callable=AsyncMock) as mock_fetch, \
             patch(PATCH_SLEEP, new_callable=AsyncMock) as mock_sleep, \
             patch("hummingbot.data_feed.candles_feed.lighter_spot_candles.lighter_spot_candles.safe_ensure_future") as mock_future:
            mock_fetch.return_value = candle
            mock_sleep.side_effect = asyncio.CancelledError

            with self.assertRaises(asyncio.CancelledError):
                await self.data_feed.listen_for_subscriptions()

            self.assertTrue(self.data_feed._ws_candle_available.is_set())
            mock_future.assert_called_once()

    async def test_subscribe_channels_raises_cancel_exception(self):
        # Lighter's listen_for_subscriptions never calls _subscribe_channels; skip WS test.
        pass

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        # Lighter's listen_for_subscriptions never calls _subscribe_channels; skip WS test.
        pass

    @patch("hummingbot.data_feed.candles_feed.lighter_spot_candles.lighter_spot_candles.safe_ensure_future")
    @patch(PATCH_SLEEP, new_callable=AsyncMock)
    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_process_websocket_messages_empty_candle(self, mock_fetch, mock_sleep, mock_future):
        # Replaces WS base test: first poll with no existing candles triggers fill_historical_candles
        candle = np.array(
            [[1748954160.0, 94000.0, 94150.0, 93850.0, 94050.0, 0.50, 47025.0, 0.0, 0.0, 0.0]]
        )
        mock_fetch.return_value = candle
        mock_sleep.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_feed.listen_for_subscriptions()

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)
        mock_future.assert_called_once()

    @patch("hummingbot.data_feed.candles_feed.lighter_spot_candles.lighter_spot_candles.safe_ensure_future")
    @patch(PATCH_SLEEP, new_callable=AsyncMock)
    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_process_websocket_messages_duplicated_candle_not_included(
        self, mock_fetch, mock_sleep, mock_future
    ):
        # Same timestamp on second poll → in-place update, not append
        candle = np.array(
            [[1748954160.0, 94000.0, 94150.0, 93850.0, 94050.0, 0.50, 47025.0, 0.0, 0.0, 0.0]]
        )
        updated_candle = np.array(
            [[1748954160.0, 94000.0, 94200.0, 93800.0, 94100.0, 0.65, 61165.0, 0.0, 0.0, 0.0]]
        )
        mock_fetch.side_effect = [candle, updated_candle, asyncio.CancelledError()]
        mock_sleep.return_value = None

        with self.assertRaises(asyncio.CancelledError):
            await self.data_feed.listen_for_subscriptions()

        # Still only one candle (same timestamp → update, not append)
        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)
        # High was updated in-place
        self.assertAlmostEqual(float(self.data_feed._candles[-1][2]), 94200.0)

    @patch("hummingbot.data_feed.candles_feed.lighter_spot_candles.lighter_spot_candles.safe_ensure_future")
    @patch(PATCH_SLEEP, new_callable=AsyncMock)
    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_process_websocket_messages_with_two_valid_messages(
        self, mock_fetch, mock_sleep, mock_future
    ):
        # Second poll has a newer timestamp → appended
        candle1 = np.array(
            [[1748954160.0, 94000.0, 94150.0, 93850.0, 94050.0, 0.50, 47025.0, 0.0, 0.0, 0.0]]
        )
        candle2 = np.array(
            [[1748954220.0, 94050.0, 94200.0, 94000.0, 94180.0, 0.35, 32963.0, 0.0, 0.0, 0.0]]
        )
        mock_fetch.side_effect = [candle1, candle2, asyncio.CancelledError()]
        mock_sleep.return_value = None

        with self.assertRaises(asyncio.CancelledError):
            await self.data_feed.listen_for_subscriptions()

        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    @patch(PATCH_SLEEP, new_callable=AsyncMock)
    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_polling_empty_fetch_result_does_not_add_candle(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = np.array([]).reshape(0, 10)
        mock_sleep.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_feed.listen_for_subscriptions()

        self.assertEqual(len(self.data_feed._candles), 0)
        self.assertFalse(self.data_feed._ws_candle_available.is_set())

    @patch(PATCH_SLEEP, new_callable=AsyncMock)
    @patch(PATCH_FETCH, new_callable=AsyncMock)
    async def test_polling_retries_after_exception(self, mock_fetch, mock_sleep):
        mock_fetch.side_effect = [Exception("API error"), asyncio.CancelledError()]
        mock_sleep.return_value = None

        with self.assertRaises(asyncio.CancelledError):
            await self.data_feed.listen_for_subscriptions()

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error polling Lighter candles. Retrying in 5s...")
        )
        mock_sleep.assert_called_with(5.0)
