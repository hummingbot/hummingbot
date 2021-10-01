import json
import re
import unittest
import asyncio
from typing import Awaitable, Dict, AsyncIterable
from unittest.mock import patch, AsyncMock

import aiohttp
from aioresponses import aioresponses

from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import (
    KucoinWSConnectionIterator, KucoinAPIOrderBookDataSource, StreamType
)
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class KucoinTestProviders:  # does not inherit from TestCase so as to not be discovered
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ws_endpoint = "ws://someEndpoint"
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def anext(ai: AsyncIterable) -> Awaitable:
        return ai.__anext__()


class TestKucoinWSConnectionIterator(KucoinTestProviders, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.conn_iterator = KucoinWSConnectionIterator(StreamType.Trade, {self.trading_pair}, self.throttler)

    @aioresponses()
    def test_get_ws_connection_context_fail(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PUBLIC_WS_DATA_PATH_URL
        mock_api.post(url, status=500)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.conn_iterator.open_ws_connection())

    @aioresponses()
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_get_ws_connection_context_success(self, mock_api, ws_connect_mock):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PUBLIC_WS_DATA_PATH_URL
        resp_data = {
            "data": {
                "instanceServers": [
                    {
                        "endpoint": self.ws_endpoint,
                    }
                ],
                "token": "someToken",
            }
        }
        mock_api.post(url, body=json.dumps(resp_data))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.conn_iterator.open_ws_connection())
        self.assertEqual(self.conn_iterator.websocket, ws_connect_mock.return_value)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_update_subscription(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.async_run_with_timeout(self.conn_iterator.open_ws_connection())

        self.async_run_with_timeout(
            self.conn_iterator.update_subscription(StreamType.Depth, {self.trading_pair}, subscribe=True)
        )

        self.assertTrue(len(ws_json_messages) == 1)

        self.async_run_with_timeout(
            self.conn_iterator.update_subscription(StreamType.Trade, {self.trading_pair}, subscribe=True)
        )

        self.assertTrue(len(ws_json_messages) == 2)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws = self.ev_loop.run_until_complete(ws_connect_mock())
        ws_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        conn_iterator = KucoinWSConnectionIterator(
            StreamType.Trade, {self.trading_pair}, AsyncThrottler(CONSTANTS.RATE_LIMITS)
        )
        conn_iterator._ws = ws

        self.async_run_with_timeout(conn_iterator.subscribe(StreamType.Depth, {self.trading_pair}))

        self.assertTrue(len(ws_json_messages) == 1)
        msg = ws_json_messages.pop()
        self.assertEqual(msg["type"], "subscribe")

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_unsubscribe(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws = self.ev_loop.run_until_complete(ws_connect_mock())
        ws_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        conn_iterator = KucoinWSConnectionIterator(
            StreamType.Trade, {self.trading_pair}, AsyncThrottler(CONSTANTS.RATE_LIMITS)
        )
        conn_iterator._ws = ws

        self.async_run_with_timeout(conn_iterator.unsubscribe(StreamType.Depth, {self.trading_pair}))

        self.assertTrue(len(ws_json_messages) == 1)
        msg = ws_json_messages.pop()
        self.assertEqual(msg["type"], "unsubscribe")

    @aioresponses()
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_close_ws_connection(self, mock_api, ws_connect_mock):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PUBLIC_WS_DATA_PATH_URL
        resp_data = {
            "data": {
                "instanceServers": [
                    {
                        "endpoint": self.ws_endpoint,
                    }
                ],
                "token": "someToken",
            }
        }
        mock_api.post(url, body=json.dumps(resp_data))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.conn_iterator.open_ws_connection())
        self.async_run_with_timeout(self.conn_iterator.close_ws_connection())

        self.assertEqual(None, self.conn_iterator.websocket)
        self.assertEqual(None, self.conn_iterator._client)

    @aioresponses()
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_iteration(self, mock_api, ws_connect_mock):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PUBLIC_WS_DATA_PATH_URL
        resp_data = {
            "data": {
                "instanceServers": [
                    {
                        "endpoint": self.ws_endpoint,
                    }
                ],
                "token": "someToken",
            }
        }
        mock_api.post(url, body=json.dumps(resp_data))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        msg_data = {"someKey": "someValue"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(msg_data),
        )

        msg = self.async_run_with_timeout(self.anext(self.conn_iterator.__aiter__()))

        self.assertEqual(msg_data, msg)


class TestKucoinAPIOrderBookDataSource(KucoinTestProviders, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.auth = KucoinAuth(self.api_key, self.api_passphrase, self.api_secret_key)
        self.ob_data_source = KucoinAPIOrderBookDataSource(self.throttler, [self.trading_pair], self.auth)

    @staticmethod
    def get_snapshot_mock() -> Dict:
        snapshot = {
            "code": "200000",
            "data": {
                "time": 1630556205455,
                "sequence": "1630556205456",
                "bids": [["0.3003", "4146.5645"]],
                "asks": [["0.3004", "1553.6412"]]
            }
        }
        return snapshot

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        resp = {
            "data": {
                "ticker": [
                    {
                        "symbol": self.trading_pair,
                        "last": 100.0,
                    }
                ]
            }
        }
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=KucoinAPIOrderBookDataSource.get_last_traded_prices([self.trading_pair])
        )

        self.assertEqual(ret[self.trading_pair], 100)

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.EXCHANGE_INFO_PATH_URL
        resp = {
            "data": [
                {
                    "symbol": self.trading_pair,
                    "enableTrading": True,
                },
                {
                    "symbol": "SOME-PAIR",
                    "enableTrading": False,
                }
            ]
        }
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=KucoinAPIOrderBookDataSource.fetch_trading_pairs())

        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0], self.trading_pair)

    @aioresponses()
    def test_get_snapshot_raises(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=500)

        client = self.ev_loop.run_until_complete(aiohttp.ClientSession().__aenter__())
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                coroutine=KucoinAPIOrderBookDataSource.get_snapshot(client, self.trading_pair)
            )
        self.ev_loop.run_until_complete(client.__aexit__(None, None, None))

    @aioresponses()
    def test_get_snapshot_no_auth(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_snapshot_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        client = aiohttp.ClientSession()
        ret = self.async_run_with_timeout(
            coroutine=KucoinAPIOrderBookDataSource.get_snapshot(client, self.trading_pair)
        )
        self.ev_loop.run_until_complete(client.__aexit__(None, None, None))

        self.assertEqual(ret, resp)  # shallow comparison ok

    @aioresponses()
    def test_get_snapshot_with_auth(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.SNAPSHOT_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_snapshot_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        client = self.ev_loop.run_until_complete(aiohttp.ClientSession().__aenter__())
        ret = self.async_run_with_timeout(
            coroutine=self.ob_data_source.get_snapshot(client, self.trading_pair, self.auth, self.throttler)
        )
        self.ev_loop.run_until_complete(client.__aexit__(None, None, None))

        self.assertEqual(ret, resp)  # shallow comparison ok

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = CONSTANTS.BASE_PATH_URL + CONSTANTS.SNAPSHOT_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_snapshot_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.ob_data_source.get_new_order_book(self.trading_pair))

        self.assertTrue(isinstance(ret, OrderBook))
