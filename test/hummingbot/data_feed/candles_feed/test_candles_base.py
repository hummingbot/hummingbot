import asyncio
import json
import os
import re
import unittest
from abc import ABC
from collections import deque
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase


class TestCandlesBase(unittest.TestCase, ABC):
    __test__ = False
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pair: str = None
        cls.interval: str = None
        cls.ex_trading_pair: str = None
        cls.max_records: int = None

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant: NetworkMockingAssistant = None
        self.data_feed: CandlesBase = None
        self.start_time = 10e6
        self.end_time = 10e17

        self.log_records = []
        self.resume_test_event = asyncio.Event()

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _candles_data_mock(self):
        return deque(self.get_fetch_candles_data_mock()[-4:])

    @staticmethod
    def get_candles_rest_data_mock():
        """
        Returns a mock response from the exchange REST API endpoint. At least it must contain four candles.
        """
        raise NotImplementedError

    def get_fetch_candles_data_mock(self):
        raise NotImplementedError

    @staticmethod
    def get_candles_ws_data_mock_1():
        raise NotImplementedError

    @staticmethod
    def get_candles_ws_data_mock_2():
        raise NotImplementedError

    @staticmethod
    def _success_subscription_mock():
        raise NotImplementedError

    def test_initialization(self):
        self.assertEqual(self.data_feed._trading_pair, self.trading_pair)
        self.assertEqual(self.data_feed.interval, self.interval)
        self.assertEqual(len(self.data_feed._candles), 0)
        self.assertEqual(self.data_feed._candles.maxlen, self.max_records)

    def test_ready_property(self):
        self.assertFalse(self.data_feed.ready)
        self.data_feed._candles.extend(range(self.max_records))
        self.assertTrue(self.data_feed.ready)

    def test_candles_df_property(self):
        self.data_feed._candles.extend(self._candles_data_mock())
        expected_df = pd.DataFrame(self._candles_data_mock(), columns=self.data_feed.columns, dtype=float)

        pd.testing.assert_frame_equal(self.data_feed.candles_df, expected_df)

    def test_get_exchange_trading_pair(self):
        result = self.data_feed.get_exchange_trading_pair(self.trading_pair)
        self.assertEqual(result, self.ex_trading_pair)

    @patch("os.path.exists", return_value=True)
    @patch("pandas.read_csv")
    def test_load_candles_from_csv(self, mock_read_csv, _):
        mock_read_csv.return_value = pd.DataFrame(data=self._candles_data_mock(),
                                                  columns=self.data_feed.columns)

        self.data_feed.load_candles_from_csv("/path/to/data")
        self.assertEqual(len(self.data_feed._candles), 4)

    @patch("os.path.exists", return_value=False)
    def test_load_candles_from_csv_file_not_found(self, _):
        data_path = "/path/to/data"
        expected_filename = f"candles_{self.data_feed.name}_{self.data_feed.interval}.csv"
        expected_file_path = os.path.join(data_path, expected_filename)
        expected_error_message = f"File '{expected_file_path}' does not exist."

        with self.assertRaises(FileNotFoundError) as context:
            self.data_feed.load_candles_from_csv(data_path)

        self.assertEqual(str(context.exception), expected_error_message)

    def test_check_candles_sorted_and_equidistant(self):
        not_enough_data = [self._candles_data_mock()[0]]
        self.assertIsNone(self.data_feed.check_candles_sorted_and_equidistant(not_enough_data))
        self.assertEqual(len(self.data_feed._candles), 0)

        correct_data = self._candles_data_mock().copy()
        self.data_feed._candles.extend(correct_data)
        self.assertIsNone(self.data_feed.check_candles_sorted_and_equidistant(correct_data))
        self.assertEqual(len(self.data_feed._candles), 4)

    def test_check_candles_sorted_and_equidistant_reset_candles_if_not_ascending(self):
        reversed_data = list(self._candles_data_mock())[::-1]
        self.data_feed._candles.extend(reversed_data)
        self.assertEqual(len(self.data_feed._candles), 4)
        self.data_feed.check_candles_sorted_and_equidistant(reversed_data)
        self.is_logged("WARNING", "Candles are not sorted by timestamp in ascending order.")
        self.assertEqual(len(self.data_feed._candles), 0)

    def test_check_candles_sorted_and_equidistant_reset_candles_if_not_equidistant(self):
        not_equidistant_data = self._candles_data_mock()
        not_equidistant_data[0][0] += 1
        self.data_feed._candles.extend(not_equidistant_data)
        self.assertEqual(len(self.data_feed._candles), 4)
        self.data_feed.check_candles_sorted_and_equidistant(not_equidistant_data)
        self.is_logged("WARNING", "Candles are malformed. Restarting...")
        self.assertEqual(len(self.data_feed._candles), 0)

    def test_reset_candles(self):
        self.data_feed._candles.extend(self._candles_data_mock())
        self.data_feed._ws_candle_available.set()
        self.assertEqual(self.data_feed._ws_candle_available.is_set(), True)
        self.assertEqual(len(self.data_feed._candles), 4)
        self.data_feed._reset_candles()
        self.assertEqual(len(self.data_feed._candles), 0)
        self.assertEqual(self.data_feed._ws_candle_available.is_set(), False)

    def test_ensure_timestamp_in_seconds(self):
        self.assertEqual(self.data_feed.ensure_timestamp_in_seconds(1622505600), 1622505600)
        self.assertEqual(self.data_feed.ensure_timestamp_in_seconds(1622505600000), 1622505600)
        self.assertEqual(self.data_feed.ensure_timestamp_in_seconds(1622505600000000), 1622505600)

        with self.assertRaises(ValueError):
            self.data_feed.ensure_timestamp_in_seconds(162250)

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        resp = self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_klines(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_klines = self._success_subscription_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_klines))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_kline_subscription = self.data_feed.ws_subscription_payload()
        # this is bacause I couldn't find a way to mock the nonce
        if "id" in expected_kline_subscription:
            del expected_kline_subscription["id"]
        if "id" in sent_subscription_messages[0]:
            del sent_subscription_messages[0]["id"]
        self.assertEqual(expected_kline_subscription, sent_subscription_messages[0])

        self.assertTrue(self.is_logged(
            "INFO",
            "Subscribed to public klines..."
        ))

    @patch("hummingbot.data_feed.candles_feed.binance_perpetual_candles.BinancePerpetualCandles._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase._sleep")
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

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles", new_callable=AsyncMock)
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

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles", new_callable=AsyncMock)
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

    @patch("hummingbot.data_feed.candles_feed.candles_base.CandlesBase.fill_historical_candles", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_websocket_messages_with_two_valid_messages(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_candles_ws_data_mock_2()))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(self.data_feed.candles_df.shape[0], 2)
        self.assertEqual(self.data_feed.candles_df.shape[1], 10)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception
