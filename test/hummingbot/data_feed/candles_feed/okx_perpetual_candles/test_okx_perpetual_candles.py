import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig
from hummingbot.data_feed.candles_feed.okx_perpetual_candles import OKXPerpetualCandles, constants as CONSTANTS


class TestOKXPerpetualCandles(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}-SWAP"

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = OKXPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_fetched_candles_data_mock(self):
        candles = self.get_candles_rest_data_mock()
        arr = [[row[0], row[1], row[2], row[3], row[4], row[6], row[7], 0., 0., 0.] for row in candles["data"][::-1]]
        return np.array(arr).astype(float)

    def get_candles_rest_data_mock(self):
        data = {
            "code": "0",
            "msg": "",
            "data": [
                ["1705431600000",
                 "43016",
                 "43183.8",
                 "42946",
                 "43169.7",
                 "404.74017381",
                 "17447600.212916623",
                 "17447600.212916623",
                 "1"],
                ["1705428000000",
                 "43053.3",
                 "43157.4",
                 "42836.5",
                 "43016",
                 "385.88107189",
                 "16589516.212133739",
                 "16589516.212133739",
                 "1"],
                ["1705424400000",
                 "43250.9",
                 "43250.9",
                 "43035.1",
                 "43048.1",
                 "333.55276206",
                 "14383538.301882162",
                 "14383538.301882162",
                 "1"],
                ["1705420800000",
                 "43253.6",
                 "43440.2",
                 "43000",
                 "43250.9",
                 "942.87870026",
                 "40743115.773175484",
                 "40743115.773175484",
                 "1"],
            ]
        }
        return data

    def get_candles_ws_data_mock_1(self):
        data = {
            "arg": {
                "channel": "candle1H",
                "instId": "BTC-USDT"},
            "data": [
                ["1705420800000",
                 "43253.6",
                 "43440.2",
                 "43000",
                 "43250.9",
                 "942.87870026",
                 "40743115.773175484",
                 "40743115.773175484",
                 "1"]]}
        return data

    def get_candles_ws_data_mock_2(self):
        data = {
            "arg": {
                "channel": "candle1H",
                "instId": "BTC-USDT"},
            "data": [
                ["1705435200000",
                 "43169.8",
                 "43370",
                 "43168",
                 "43239",
                 "297.60067612",
                 "12874025.740848533",
                 "12874025.740848533",
                 "0"]]}
        return data

    @aioresponses()
    def test_fetch_candles(self, mock_api: aioresponses):
        # Fill manual params
        start_time = 1705420800000
        end_time = 1705431600000

        # Generate url and regex_url. Last one is used for best practices
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.CANDLES_ENDPOINT}?after={end_time}&bar={CONSTANTS.INTERVALS[self.interval]}&before={start_time}&instId={self.ex_trading_pair}&limit=100"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # Mock the response
        data_mock = self.get_candles_rest_data_mock()

        # Add the mock to the aioresponse mock
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        # Run the test
        resp = self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=start_time, end_time=end_time))

        # Check the response
        self.assertEqual(resp.shape[0], len(data_mock["data"]))
        self.assertEqual(resp.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.okx_perpetual_candles.OKXPerpetualCandles.fetch_candles", new_callable=AsyncMock)
    def test_get_historical_candles(self, fetched_candles_mock):
        config = HistoricalCandlesConfig(connector_name="okx_perpetual",
                                         trading_pair=self.ex_trading_pair,
                                         interval=self.interval,
                                         start_time=1705420800000,
                                         end_time=1705431600000)
        resp_1 = self.get_fetched_candles_data_mock()
        resp_2 = np.array([])
        fetched_candles_mock.side_effect = [resp_1, resp_2]
        candles_df = self.async_run_with_timeout(self.data_feed.get_historical_candles(config))

        # Check the response
        self.assertEqual(candles_df.shape[0], len(resp_1))
        self.assertEqual(candles_df.shape[1], 10)

        # Check candles integrity. Diff should always be interval in milliseconds and keep sign constant
        self.assertEqual(len(candles_df["timestamp"].diff()[1:].unique()), 1, "Timestamp diff should be constant")

    def test_candles_empty(self):
        self.assertTrue(self.data_feed.candles_df.empty)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_klines(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_klines = {
            "event": "subscribe",
            "arg": {
                "channel": "candle1H",
                "instId": "BTC-USDT-SWAP"
            },
            "connId": "a4d3ae55"
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_klines))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_kline_subscription = {
            "op": "subscribe",
            "args": [{
                "channel": f"candle{CONSTANTS.INTERVALS[self.interval]}",
                "instId": self.ex_trading_pair}]
        }

        self.assertEqual(expected_kline_subscription, sent_subscription_messages[0])

        self.assertTrue(self.is_logged(
            log_level="INFO",
            message="Subscribed to public klines..."
        ))

    @patch("hummingbot.data_feed.candles_feed.okx_perpetual_candles.OKXPerpetualCandles._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.data_feed.candles_feed.okx_perpetual_candles.OKXPerpetualCandles._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock: AsyncMock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error occurred when listening to public klines. Retrying in 1 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_feed._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_feed._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error occurred subscribing to public klines...")
        )

    @patch("hummingbot.data_feed.candles_feed.okx_perpetual_candles.OKXPerpetualCandles.fill_historical_candles", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_websocket_messages_empty_candle(self, ws_connect_mock, fill_historical_candles_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)
        fill_historical_candles_mock.assert_called_once()

    @patch("hummingbot.data_feed.candles_feed.okx_perpetual_candles.OKXPerpetualCandles.fill_historical_candles", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_websocket_messages_duplicated_candle_not_included(self, ws_connect_mock, fill_historical_candles):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        fill_historical_candles.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=2)

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    @patch("hummingbot.data_feed.candles_feed.okx_perpetual_candles.OKXPerpetualCandles.fill_historical_candles")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_websocket_messages_with_two_valid_messages(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        msg_1 = json.dumps(self.get_candles_ws_data_mock_1())
        msg_2 = json.dumps(self.get_candles_ws_data_mock_2())

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=msg_1)

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=msg_2)

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception
