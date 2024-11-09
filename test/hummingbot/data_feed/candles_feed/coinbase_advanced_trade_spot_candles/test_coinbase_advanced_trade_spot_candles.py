import asyncio
import json
import re
from collections import deque
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from time import time
from unittest.mock import AsyncMock, call, patch

import numpy as np
from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    REST_URL,
    SERVER_TIME_EP,
    WSS_URL,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles import (
    CoinbaseAdvancedTradeSpotCandles,
    constants as CONSTANTS,
)


def get_candles_rest_data_mock():
    return {
        "candles": [
            {
                "start": "150",
                "low": "140.21",
                "high": "140.21",
                "open": "140.21",
                "close": "140.21",
                "volume": "06437345",
            },
            {
                "start": "170",
                "low": "141.21",
                "high": "141.21",
                "open": "141.21",
                "close": "141.21",
                "volume": "16437345",
            },
            {
                "start": "190",
                "low": "142.21",
                "high": "142.21",
                "open": "142.21",
                "close": "142.21",
                "volume": "26437345",
            },
        ]
    }


def get_candles_ws_data_mock_1():
    return {
        "channel": "candles",
        "client_id": "",
        "timestamp": "2023-06-09T20:19:35.39625135Z",
        "sequence_num": 0,
        "events": [
            {
                "type": "snapshot",
                "candles": [
                    {
                        "start": "200",
                        "high": "1867.72",
                        "low": "1865.63",
                        "open": "1867.38",
                        "close": "1866.81",
                        "volume": "0.20269406",
                        "product_id": "ETH-USD",
                    },
                    {
                        "start": "260",
                        "high": "1867.72",
                        "low": "1865.63",
                        "open": "1867.38",
                        "close": "1866.81",
                        "volume": "0.20269406",
                        "product_id": "ETH-USD",
                    },
                ],
            }
        ],
    }


def get_candles_ws_data_mock_2():
    return {
        "channel": "candles",
        "client_id": "",
        "timestamp": "2023-06-09T20:19:35.39625135Z",
        "sequence_num": 0,
        "events": [
            {
                "type": "snapshot",
                "candles": [
                    {
                        "start": "260",
                        "high": "2000.72",
                        "low": "1865.63",
                        "open": "1867.38",
                        "close": "1866.81",
                        "volume": "0.20269406",
                        "product_id": "ETH-USD",
                    },
                    {
                        "start": "320",
                        "high": "1867.72",
                        "low": "1865.63",
                        "open": "1867.38",
                        "close": "1866.81",
                        "volume": "0.20269406",
                        "product_id": "ETH-USD",
                    },
                ],
            }
        ],
    }


class TestCoinbaseAdvancedTradeSpotCandles(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    trading_pair = None
    quote_asset = "USDT"
    base_asset = "BTC"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.trading_pair

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = CoinbaseAdvancedTradeSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.set_loggers([self.data_feed.logger()])
        self.resume_test_event = asyncio.Event()

    def assertDequeEqual(self, deque1, deque2):
        self.assertEqual(len(deque1), len(deque2))
        self.assertEqual(deque1.maxlen, deque2.maxlen)

        for arr1, arr2 in zip(deque1, deque2):
            np.testing.assert_array_equal(arr1, arr2)

    def test_properties(self):
        self.assertEqual(self.data_feed.rest_url, REST_URL.format(domain="com"))
        self.assertEqual(self.data_feed.wss_url, WSS_URL.format(domain="com"))
        # v3 (REST_URL) added non-authenticated server time endpoint on Feb 22nd 24
        self.assertEqual(self.data_feed.health_check_url, REST_URL.format(domain="com") + SERVER_TIME_EP)
        self.assertEqual(self.data_feed.candles_url,
                         self.data_feed.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(product_id=self.ex_trading_pair))
        self.assertEqual(self.data_feed.rate_limits, CONSTANTS.RATE_LIMITS)
        self.assertEqual(self.data_feed.intervals, CONSTANTS.INTERVALS)
        self.assertEqual(self.data_feed.candle_keys_order, ("start", "open", "high", "low", "close", "volume"))

    def test_intervals(self):
        self.assertEqual("ONE_MINUTE", self.data_feed.intervals["1m"])

    def test_get_exchange_trading_pair(self):
        self.assertEqual(self.data_feed.get_exchange_trading_pair("BTC-USDT"), "BTC-USDT")

    @patch.object(CoinbaseAdvancedTradeSpotCandles, "fetch_candles")
    async def test_fill_historical_sufficient_candles(self, mock_fetch_candles):
        self.interval = "1m"
        mock_fetch_candles.return_value = np.array(
            [
                [(1697498000 + 0), 1, 1, 1, 1, 1],
                [(1697498000 + 60), 2, 2, 2, 2, 2],
                [(1697498000 + 120), 3, 3, 3, 3, 3]
            ])
        self.data_feed._candles = deque(
            np.array([[(1697498000 + 180), 4, 4, 4, 4, 4]]),
            maxlen=3
        )

        await self.data_feed.fill_historical_candles()
        mock_fetch_candles.assert_called_once()
        self.assertEqual(3, self.data_feed.candles_df.shape[0])
        self.assertEqual(10, self.data_feed.candles_df.shape[1])
        self.assertDequeEqual(deque(
            np.array([
                [(1697498000 + 60), 2, 2, 2, 2, 2],
                [(1697498000 + 120), 3, 3, 3, 3, 3],
                [(1697498000 + 180), 4, 4, 4, 4, 4],
            ]),
            maxlen=3
        ), self.data_feed._candles)

    @patch.object(CoinbaseAdvancedTradeSpotCandles, "fetch_candles")
    async def test_fill_historical_insufficient_candles(self, mock_fetch_candles):
        self.interval = "1m"
        mock_fetch_candles.side_effect = [
            np.array([
                [(1697498000 + 0), 1, 1, 1, 1, 1],
                [(1697498000 + 60), 2, 2, 2, 2, 2],
                [(1697498000 + 120), 3, 3, 3, 3, 3],
                [(1697498000 + 180), 4, 4, 4, 4, 4],
                [(1697498000 + 240), 5, 5, 5, 5, 5],
                [(1697498000 + 300), 5, 5, 5, 5, 5]  # This should not be in the final deque
            ]),
            np.array([])]
        self.data_feed._candles = deque(
            np.array([[(1697498000 + 300), 6, 6, 6, 6, 6]]),
            maxlen=9
        )

        await self.data_feed.fill_historical_candles()

        mock_fetch_candles.assert_has_calls([
            call(end_time=1697498300, limit=150),  # 8 intervals: 8 * 60 = 480 seconds -> 1697497760
            call(end_time=1697498000, limit=150)])  # Verifying that the start_time is not too short
        self.assertEqual(6, self.data_feed.candles_df.shape[0])
        self.assertEqual(10, self.data_feed.candles_df.shape[1])
        self.assertDequeEqual(deque(
            np.array([
                [(1697498000 + 0), 1, 1, 1, 1, 1],
                [(1697498000 + 60), 2, 2, 2, 2, 2],
                [(1697498000 + 120), 3, 3, 3, 3, 3],
                [(1697498000 + 180), 4, 4, 4, 4, 4],
                [(1697498000 + 240), 5, 5, 5, 5, 5],
                [(1697498000 + 300), 6, 6, 6, 6, 6],
            ]),
            maxlen=9
        ), self.data_feed._candles)

    @patch.object(CoinbaseAdvancedTradeSpotCandles, "fetch_candles", new_callable=AsyncMock)
    async def test_fill_historical_candles_empty_data(self, mock_fetch_candles):
        # Mock to return an empty array
        self.data_feed._candles = deque(np.array([[1, 2, 3, 4, 5, 6]]), maxlen=2)
        mock_fetch_candles.return_value = np.array([])

        await self.data_feed.fill_historical_candles()
        self.assertTrue(
            self.is_partially_logged("ERROR", "There is not enough data available to fill historical candles for "))

    @patch.object(CoinbaseAdvancedTradeSpotCandles, "_sleep", new_callable=AsyncMock)
    @patch.object(CoinbaseAdvancedTradeSpotCandles, "fetch_candles", new_callable=AsyncMock)
    async def test_fill_historical_candles_unexpected_exception(self, mock_fetch_candles, mock_sleep):
        # Mock to raise an unexpected exception
        self.data_feed._candles = deque(np.array([[1, 2, 3, 4, 5, 6]]), maxlen=2)
        mock_fetch_candles.side_effect = [Exception("Something went wrong")]

        await self.data_feed.fill_historical_candles()

        # Verify that sleep was called, implying a retry attempt
        mock_sleep.assert_called_once_with(1.0)
        self.assertTrue(self.is_partially_logged(
            "ERROR",
            "Unexpected error occurred when getting historical candles Something went wrong"))

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.constants.MAX_CANDLES_SIZE", 100)
    @patch.object(CoinbaseAdvancedTradeSpotCandles, "get_seconds_from_interval")
    def test_get_valid_start_time_with_start_time(self, mock_interval):
        end_time = 200000
        mock_interval.return_value = 60
        start_time = 150000
        result = self.data_feed._get_valid_start_time(end_time, start_time, limit=500)
        self.assertEqual(200000 - 100 * mock_interval.return_value, result)

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.constants.MAX_CANDLES_SIZE", 100)
    @patch.object(CoinbaseAdvancedTradeSpotCandles, "get_seconds_from_interval")
    def test_get_valid_start_time_without_start_time(self, mock_interval):
        end_time = 200000
        mock_interval.return_value = 60
        result = self.data_feed._get_valid_start_time(end_time, start_time=None, limit=500)
        expected_start_time = end_time - (mock_interval.return_value * 100)
        self.assertEqual(result, expected_start_time)

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.constants.MAX_CANDLES_SIZE", 100)
    @patch.object(CoinbaseAdvancedTradeSpotCandles, "get_seconds_from_interval")
    def test_get_valid_start_time_with_candles_maxlen_greater_than_constant(self, mock_interval):
        data_feed = CoinbaseAdvancedTradeSpotCandles(
            trading_pair=self.trading_pair,
            interval=self.interval,
            max_records=150
        )
        end_time = 200000
        mock_interval.return_value = 60
        result = data_feed._get_valid_start_time(end_time, start_time=None, limit=500)
        expected_start_time = end_time - (mock_interval.return_value * 100)
        self.assertEqual(result, expected_start_time)

    @patch.object(CoinbaseAdvancedTradeSpotCandles, "get_seconds_from_interval")
    def test_get_valid_start_time_with_candles_maxlen_less_than_constant(self, mock_interval):
        data_feed = CoinbaseAdvancedTradeSpotCandles(
            trading_pair=self.trading_pair,
            interval=self.interval,
            max_records=50
        )
        mock_interval.return_value = 60
        end_time = 200000
        result = data_feed._get_valid_start_time(end_time, start_time=None, limit=data_feed.max_records)
        expected_start_time = end_time - (mock_interval.return_value * 50)
        self.assertEqual(expected_start_time, result)

    @aioresponses()  # This does not seem to work
    @patch.object(CoinbaseAdvancedTradeSpotCandles, "get_seconds_from_interval")
    async def test_fetch_candles(self, mock_interval, mock_api):
        end_time = int(time()) + 60
        mock_interval.return_value = 60
        # self.data_feed._build_auth_api_factory = AsyncMock()
        # self.data_feed._build_auth_api_factory.return_value = self.data_feed._public_api_factory
        self.data_feed._public_api_factory.get_rest_assistant = AsyncMock()
        self.data_feed._public_api_factory.get_rest_assistant.return_value.execute_request = AsyncMock()
        start_time = self.data_feed._get_valid_start_time(end_time=end_time, start_time=None, limit=500)

        url = (f"{REST_URL.format(domain='com')}{CONSTANTS.CANDLES_ENDPOINT.format(product_id=self.ex_trading_pair)}?"
               f"end={end_time}&granularity=ONE_MINUTE&start={start_time}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))
        self.data_feed._public_api_factory.get_rest_assistant.return_value.execute_request.return_value = data_mock

        resp = await self.data_feed.fetch_candles(start_time=start_time, end_time=end_time)

        self.assertEqual(resp.shape[1], 6)
        self.assertEqual(resp.shape[0], len(data_mock.get("candles")))

    def test_candles_empty(self):
        self.assertTrue(self.data_feed.candles_df.empty)

#    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
#    async def test_listen_for_subscriptions_subscribes_to_candles(self, ws_connect_mock):
#        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
#
#        result_subscribe_klines = {
#            "result": None,
#            "id": 1
#        }
#
#        self.mocking_assistant.add_websocket_aiohttp_message(
#            websocket_mock=ws_connect_mock.return_value,
#            message=json.dumps(result_subscribe_klines))
#
#        self.data_feed._api_factory = self.data_feed._public_api_factory
#        self.listening_task = asyncio.create_task(self.data_feed._listen_for_subscriptions())
#
#        # Man, this thing is annoying!
#        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
#        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
#            ws_connect_mock.return_value]
#        await asyncio.wait_for(all_delivered.wait(), 1)
#
#        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
#            websocket_mock=ws_connect_mock.return_value)
#
#        self.assertEqual(1, len(sent_subscription_messages))
#        expected_kline_subscription = {
#            "type": "subscribe",
#            "product_ids": [f"{self.ex_trading_pair}"],
#            "channel": "candles"}
#
#        self.assertEqual(expected_kline_subscription, sent_subscription_messages[0])
#
#        self.assertTrue(self.is_logged(
#            "INFO",
#            "Subscribed to public candles..."),
#            self.log_records
#        )

#    @patch(
#        "hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles._sleep")
#    @patch("aiohttp.ClientSession.ws_connect")
#    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
#        mock_ws.side_effect = asyncio.CancelledError
#
#        with self.assertRaises(asyncio.CancelledError):
#            self.data_feed._api_factory = self.data_feed._public_api_factory
#            self.listening_task = asyncio.create_task(self.data_feed._listen_for_subscriptions())
#            await asyncio.wait_for(self.listening_task, 1)

#    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
#           "._sleep")
#    @patch.object(CoinbaseAdvancedTradeSpotCandles, "_connected_websocket_assistant", new_callable=AsyncMock)
#    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock: AsyncMock):
#        mock_ws.side_effect = Exception("TEST ERROR.")
#        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(
#            asyncio.CancelledError())
#
#        asyncio.create_task(self.data_feed._listen_for_subscriptions())
#        await asyncio.sleep(0.1)
#        await self.resume_test_event.wait()
#
#        self.assertTrue(
#            self.is_partially_logged(
#                "ERROR",
#                "Unexpected error occurred when listening to public klines"),
#            self.log_records
#        )

#    async def test_subscribe_channels_raises_cancel_exception(self):
#        mock_ws = MagicMock()
#        mock_ws.send.side_effect = asyncio.CancelledError
#
#        self.data_feed._ws_subscriptions = {}
#        with self.assertRaises(asyncio.CancelledError):
#            listening_task = asyncio.create_task(self.data_feed._subscribe_channels(mock_ws))
#            await asyncio.wait_for(listening_task, 1)

#    async def test_subscribe_channels_raises_exception_and_logs_error(self):
#        mock_ws = MagicMock()
#        mock_ws.send.side_effect = Exception("Test Error")
#
#        self.data_feed._ws_subscriptions = {}
#        with self.assertRaises(Exception):
#            listening_task = asyncio.create_task(self.data_feed._subscribe_channels(mock_ws))
#            await asyncio.wait_for(listening_task, 1)
#
#        self.assertTrue(
#            self.is_logged("ERROR", "Unexpected error occurred subscribing to public candles..."),
#            self.log_records
#        )

#    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
#           ".fill_historical_candles",
#           new_callable=AsyncMock)
#    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
#    async def test_process_websocket_messages_empty_candle(self, ws_connect_mock, fill_historical_candles_mock):
#        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
#
#        self.mocking_assistant.add_websocket_aiohttp_message(
#            websocket_mock=ws_connect_mock.return_value,
#            message=json.dumps(get_candles_ws_data_mock_1()))
#
#        self.data_feed._api_factory = self.data_feed._public_api_factory
#        self.listening_task = asyncio.create_task(self.data_feed._listen_for_subscriptions())
#
#        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
#            ws_connect_mock.return_value]
#        await asyncio.wait_for(all_delivered.wait(), 1)
#
#        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
#        self.assertEqual(self.data_feed.candles_df.shape[1], 10)
#        fill_historical_candles_mock.assert_called_once()

#    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
#           ".fill_historical_candles",
#           new_callable=AsyncMock)
#    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
#    async def test_process_websocket_messages_duplicated_candle_not_included(self, ws_connect_mock,
#                                                                             fill_historical_candles):
#        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
#        fill_historical_candles.return_value = None
#
#        self.mocking_assistant.add_websocket_aiohttp_message(
#            websocket_mock=ws_connect_mock.return_value,
#            message=json.dumps(get_candles_ws_data_mock_1()))
#
#        self.mocking_assistant.add_websocket_aiohttp_message(
#            websocket_mock=ws_connect_mock.return_value,
#            message=json.dumps(get_candles_ws_data_mock_1()))
#
#        self.data_feed._api_factory = self.data_feed._public_api_factory
#        self.listening_task = asyncio.create_task(self.data_feed._listen_for_subscriptions())
#
#        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
#            ws_connect_mock.return_value]
#        await asyncio.wait_for(all_delivered.wait(), 2)
#
#        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
#        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

#    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
#           ".fill_historical_candles")
#    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
#    async def test_process_websocket_messages_with_two_valid_messages(self, ws_connect_mock, _):
#        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
#
#        self.mocking_assistant.add_websocket_aiohttp_message(
#            websocket_mock=ws_connect_mock.return_value,
#            message=json.dumps(get_candles_ws_data_mock_1()))
#
#        self.mocking_assistant.add_websocket_aiohttp_message(
#            websocket_mock=ws_connect_mock.return_value,
#            message=json.dumps(get_candles_ws_data_mock_2()))
#
#        self.data_feed._api_factory = self.data_feed._public_api_factory
#        self.listening_task = asyncio.create_task(self.data_feed._listen_for_subscriptions())
#
#        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=2)
#        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
#            ws_connect_mock.return_value]
#        await asyncio.wait_for(all_delivered.wait(), 2)
#
#        self.assertEqual(self.data_feed.candles_df.shape[0], 3, self.data_feed.candles_df.shape)
#        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    async def test_check_network_happy_path(self):
        with patch.object(self.data_feed, "_api_factory") as mock_api_factory:
            mock_rest_assistant = AsyncMock()
            mock_rest_assistant.execute_request.return_value = {"status": 200}
            mock_api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)
            result = await self.data_feed.check_network()
            self.assertEqual(result, NetworkStatus.CONNECTED)

    async def test_check_network_edge_case_non_200_status(self):
        with patch.object(self.data_feed, "_api_factory") as mock_api_factory:
            mock_rest_assistant = AsyncMock()
            mock_rest_assistant.execute_request.return_value = {"status": 500}
            mock_api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)
            result = await self.data_feed.check_network()
            self.assertEqual(result, NetworkStatus.NOT_CONNECTED)

    async def test_check_network_error_case_exception_raised(self):
        with patch.object(self.data_feed, "_api_factory") as mock_api_factory:
            mock_rest_assistant = AsyncMock()
            mock_rest_assistant.execute_request.side_effect = Exception("Test Error")
            mock_api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)
            result = await self.data_feed.check_network()
            self.assertEqual(result, NetworkStatus.NOT_CONNECTED)
