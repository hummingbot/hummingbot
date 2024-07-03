import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.kucoin_spot_candles import KucoinSpotCandles, constants as CONSTANTS


class TestKucoinSpotCandles(unittest.TestCase):
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
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = KucoinSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

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

    def get_candles_rest_data_mock(self):
        data = [
            [
                1672981200,
                "16823.24000000",
                "16823.63000000",
                "16792.12000000",
                "16810.18000000",
                "6230.44034000",
                1672984799999,
            ],
            [
                1672984800,
                "16809.74000000",
                "16816.45000000",
                "16779.96000000",
                "16786.86000000",
                "6529.22759000",
                1672988399999,
            ],
            [
                1672988400,
                "16786.60000000",
                "16802.87000000",
                "16780.15000000",
                "16794.06000000",
                "5763.44917000",
                1672991999999,
            ],
            [
                1672992000,
                "16794.33000000",
                "16812.22000000",
                "16791.47000000",
                "16802.11000000",
                "5475.13940000",
                1672995599999,
            ],
        ]
        return {"data": data}

    def get_candles_ws_data_mock_1(self):
        data = {
            "type": "message",
            "topic": "/market/candles:BTC-USDT_1hour",
            "subject": "trade.candles.update",
            "data": {
                "symbol": "BTC-USDT",  # symbol
                "candles": [
                    "1589968800",  # Start time of the candle cycle
                    "9786.9",  # open price
                    "9740.8",  # close price
                    "9806.1",  # high price
                    "9732",  # low price
                    "27.45649579",  # Transaction volume
                    "268280.09830877"  # Transaction amount
                ],
                "time": 1589970010253893337  # now（us）
            }
        }
        return data

    def get_candles_ws_data_mock_2(self):
        data = {
            "type": "message",
            "topic": "/market/candles:BTC-USDT_1hour",
            "subject": "trade.candles.update",
            "data": {
                "symbol": "BTC-USDT",  # symbol
                "candles": [
                    "1589972400",  # Start time of the candle cycle
                    "9786.9",  # open price
                    "9740.8",  # close price
                    "9806.1",  # high price
                    "9732",  # low price
                    "27.45649579",  # Transaction volume
                    "268280.09830877"  # Transaction amount
                ],
                "time": 1589970010253893337  # now（us）
            }
        }
        return data

    @aioresponses()
    def test_fetch_candles(self, mock_api: aioresponses):
        start_time = 1672981200
        end_time = 1672992000
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.CANDLES_ENDPOINT}?endAt={end_time}&startAt={start_time}" \
              f"&symbol={self.ex_trading_pair}&type={CONSTANTS.INTERVALS[self.interval]}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        resp = self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=start_time * 1000, end_time=end_time * 1000))

        self.assertEqual(resp.shape[0], len(data_mock["data"]))
        self.assertEqual(resp.shape[1], 10)

    def test_candles_empty(self):
        self.assertTrue(self.data_feed.candles_df.empty)

    @staticmethod
    def _token_generation_for_ws_subscription_mock_response():
        return {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_klines(self, mock_api, ws_connect_mock):
        url = self.data_feed.public_ws_url

        resp = self._token_generation_for_ws_subscription_mock_response()

        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_klines = {
            "id": "hQvf8jkno",
            "type": "welcome"
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_klines))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_topic = f"/market/candles:{self.ex_trading_pair.upper()}_{CONSTANTS.INTERVALS[self.interval]}"
        self.assertEqual(expected_topic, sent_subscription_messages[0]["topic"])
        self.assertTrue(self.is_logged(
            "INFO",
            "Subscribed to public klines..."
        ))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_api, ws_connect_mock):
        url = self.data_feed.public_ws_url

        resp = self._token_generation_for_ws_subscription_mock_response()
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.data_feed.candles_feed.kucoin_spot_candles.KucoinSpotCandles._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock: AsyncMock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait(), timeout=1)

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

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.kucoin_spot_candles.KucoinSpotCandles.fill_historical_candles", new_callable=AsyncMock)
    def test_process_websocket_messages_empty_candle(self, mock_api, fill_historical_candles_mock, ws_connect_mock):
        url = self.data_feed.public_ws_url

        resp = self._token_generation_for_ws_subscription_mock_response()
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)
        fill_historical_candles_mock.assert_called_once()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.data_feed.candles_feed.kucoin_spot_candles.KucoinSpotCandles.fill_historical_candles",
           new_callable=AsyncMock)
    def test_process_websocket_messages_duplicated_candle_not_included(self, mock_api, fill_historical_candles, ws_connect_mock):
        url = self.data_feed.public_ws_url

        resp = self._token_generation_for_ws_subscription_mock_response()
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        fill_historical_candles.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.data_feed._time = MagicMock(return_value=5)

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(self.data_feed.candles_df.shape[0], 1)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_websocket_messages_with_two_valid_messages(self, mock_api, ws_connect_mock):
        url = self.data_feed.public_ws_url

        resp = self._token_generation_for_ws_subscription_mock_response()
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_2()))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=2)

        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception
