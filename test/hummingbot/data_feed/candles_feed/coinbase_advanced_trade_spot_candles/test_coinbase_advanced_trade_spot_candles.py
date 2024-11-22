import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

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
                        "start": "500",  # 300/5m WS interval
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
                        "start": "500",
                        "high": "2000.72",
                        "low": "1865.63",
                        "open": "1867.38",
                        "close": "1866.81",
                        "volume": "0.20269406",
                        "product_id": "ETH-USD",
                    },
                    {
                        "start": "800",  # 300/5m WS interval
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
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.trading_pair

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = CoinbaseAdvancedTradeSpotCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.set_loggers([self.data_feed.logger()])

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

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
        self.assertEqual(self.data_feed.rate_limits, [])
        self.assertEqual(self.data_feed.intervals, CONSTANTS.INTERVALS)

    def test_intervals(self):
        self.assertEqual("ONE_MINUTE", self.data_feed.intervals["1m"])

    def test_get_exchange_trading_pair(self):
        self.assertEqual(self.data_feed.get_exchange_trading_pair("BTC-USDT"), "BTC-USDT")

    def test_candles_empty(self):
        self.assertTrue(self.data_feed.candles_df.empty)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_candles(self, ws_connect_mock):
        self.data_feed = CoinbaseAdvancedTradeSpotCandles(
            trading_pair=self.trading_pair,
            interval="5m"
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_klines = {
            "result": None,
            "id": 1
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_klines))

        self.listening_task = asyncio.create_task(self.data_feed.listen_for_subscriptions())

        # Man, this thing is annoying!
        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 1)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_kline_subscription = {
            "type": "subscribe",
            "product_ids": [f"{self.ex_trading_pair}"],
            "channel": "candles"}

        self.assertEqual(expected_kline_subscription, sent_subscription_messages[0])

        self.assertTrue(self.is_logged(
            "INFO",
            "Subscribed to public klines..."),
            self.log_records
        )

    @patch(
        "hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.data_feed._api_factory = self.data_feed._api_factory
            self.listening_task = asyncio.create_task(self.data_feed._catsc_listen_for_websocket())
            await asyncio.wait_for(self.listening_task, 1)

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
           "._sleep")
    @patch.object(CoinbaseAdvancedTradeSpotCandles, "_connected_websocket_assistant", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock: AsyncMock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError())

        asyncio.create_task(self.data_feed._catsc_listen_for_websocket())
        await asyncio.sleep(0.1)
        await self.resume_test_event.wait()

        self.assertTrue(
            self.is_partially_logged(
                "ERROR",
                "Unexpected error occurred when listening to public klines"),
            self.log_records
        )

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        self.data_feed._ws_subscriptions = {}
        with self.assertRaises(asyncio.CancelledError):
            listening_task = asyncio.create_task(self.data_feed._subscribe_channels(mock_ws))
            await asyncio.wait_for(listening_task, 1)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        self.data_feed._ws_subscriptions = {}
        with self.assertRaises(Exception):
            listening_task = asyncio.create_task(self.data_feed._subscribe_channels(mock_ws))
            await asyncio.wait_for(listening_task, 1)

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error occurred subscribing to public klines..."),
            self.log_records
        )

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
           "._catsc_fill_historical_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_empty_candle(self, ws_connect_mock, fill_historical_candles_mock):
        self.data_feed = CoinbaseAdvancedTradeSpotCandles(
            trading_pair=self.trading_pair,
            interval="5m"
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(get_candles_ws_data_mock_1()))

        self.data_feed._api_factory = self.data_feed._api_factory
        self.listening_task = asyncio.create_task(self.data_feed._catsc_listen_for_websocket())

        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 1)

        fill_historical_candles_mock.assert_called_once()
        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
           "._catsc_fill_historical_candles",
           new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_duplicated_candle_not_included(self, ws_connect_mock,
                                                                             fill_historical_candles):
        self.data_feed = CoinbaseAdvancedTradeSpotCandles(
            trading_pair=self.trading_pair,
            interval="5m"
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        fill_historical_candles.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(get_candles_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(get_candles_ws_data_mock_1()))

        self.data_feed._api_factory = self.data_feed._api_factory
        self.listening_task = asyncio.create_task(self.data_feed._catsc_listen_for_websocket())

        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 2)

        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.CoinbaseAdvancedTradeSpotCandles"
           "._catsc_fill_historical_candles")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_process_websocket_messages_with_two_valid_messages(self, ws_connect_mock, fill_historical_mock):
        self.data_feed = CoinbaseAdvancedTradeSpotCandles(
            trading_pair=self.trading_pair,
            interval="5m"
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(get_candles_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(get_candles_ws_data_mock_2()))

        self.data_feed._api_factory = self.data_feed._api_factory
        self.listening_task = asyncio.create_task(self.data_feed._catsc_listen_for_websocket())

        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=2)
        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 2)

        fill_historical_mock.assert_called_once()
        self.assertEqual(self.data_feed.candles_df.shape[0], 3, self.data_feed.candles_df.shape)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

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
            mock_rest_assistant.execute_request.return_value = None
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
