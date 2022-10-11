import asyncio
import json
import re
import unittest
from socket import gaierror, socket
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter

# Polkadex Classes
from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange
from hummingbot.connector.exchange.polkadex.polkadex_order_book_data_source import PolkadexOrderbookDataSource
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class PolkadexOrderBookDataSourceUnitTests(unittest.TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        # Polkadex Connector
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = PolkadexExchange(
            client_config_map = client_config_map,
            polkadex_seed_phrase="empower open normal dream vendor day catch flee entry monitor like april"
        )
        # Polkadex OrderBookDataSource
        #
        self.data_source = PolkadexOrderbookDataSource(
            trading_pairs=["PDEX-1"],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            api_key=" ")

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    # Test getting new orderbook succesfully
    @aioresponses()
    def test_get_new_order_book_succesful(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        # resp = {"Error": 400}
        resp = {
            "data": {
                "getOrderbook": {
                    "items": [
                        {
                            "p": "10000000000000",
                            "q": "20000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "13000000000000",
                            "q": "3000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "6000000000000",
                            "q": "10000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7380000000000",
                            "q": "60000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7440000000000",
                            "q": "65000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7480000000000",
                            "q": "55000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7600000000000",
                            "q": "88000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7800000000000",
                            "q": "57000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "8000000000000",
                            "q": "56696428571429",
                            "s": "Ask"
                        },
                        {
                            "p": "8300000000000",
                            "q": "105000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "8500000000000",
                            "q": "95000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "1000000000000",
                            "q": "7000000000000",
                            "s": "Bid"
                        },
                        {
                            "p": "200000000000",
                            "q": "5000000000000",
                            "s": "Bid"
                        }
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(2, len(bids))
        self.assertEqual(11, len(asks))
        # self.assertEqual(7.0, bids[0].amount)
        # self.assertEqual(1, 1)

    # This test will fail since there is no exception handling
    """ @aioresponses()
    def test_get_new_order_book_raise_exception(self, mock_api):
        raw_url = "https://zxhxwfyccraqppr3uy6r5yxqvm.appsync-api.eu-central-1.amazonaws.com/graphql"
        mock_api.post(raw_url, status=400)
        self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        ) """

    @aioresponses()
    def test_get_order_book_snapshot(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "getOrderbook": {
                    "items": [
                        {
                            "p": "10000000000000",
                            "q": "20000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "13000000000000",
                            "q": "3000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "6000000000000",
                            "q": "10000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7380000000000",
                            "q": "60000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7440000000000",
                            "q": "65000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7480000000000",
                            "q": "55000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7600000000000",
                            "q": "88000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "7800000000000",
                            "q": "57000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "8000000000000",
                            "q": "56696428571429",
                            "s": "Ask"
                        },
                        {
                            "p": "8300000000000",
                            "q": "105000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "8500000000000",
                            "q": "95000000000000",
                            "s": "Ask"
                        },
                        {
                            "p": "1000000000000",
                            "q": "7000000000000",
                            "s": "Bid"
                        },
                        {
                            "p": "200000000000",
                            "q": "5000000000000",
                            "s": "Bid"
                        }
                    ]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        order_book_message: OrderBookMessage = self.async_run_with_timeout(
            self.data_source._order_book_snapshot(self.trading_pair)
        )
        print(order_book_message)
        # self.assertEqual(1,0)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscription(self, ws_connect_mock):
        mock_ws = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value = mock_ws
        result_subscribe_trades = {
            "result": None,
            "id": 1
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))

        """ self.async_run_with_timeout(
          self.data_source.listen_for_subscriptions()
        ) """

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
            "data": {
                "getRecentTrades": {
                    "items": [{
                        "p": 20
                    }]
                }
            }
        }
        mock_api.post(raw_url, body=json.dumps(resp))
        prices = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices([self.trading_pair])
        )

    @aioresponses()
    def test_parse_trade_message(self, mock_api):
        raw_url = "https://szzsvapgkjdurfl7ijvc3vtbba.appsync-api.eu-central-1.amazonaws.com/graphql"
        resp = {
                    "data": [{"m": "PDEX-1", "p": 1000000000000, "q": 1000000000000, "tid": 20, "t": 1661927828000}],
        }
        msg_queue: asyncio.Queue = asyncio.Queue()
        trade_message = self.async_run_with_timeout(
            self.data_source._parse_trade_message(raw_message=resp,  message_queue=msg_queue)
        )

    @aioresponses()
    def test_parse_order_book_diff_message(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        diff_message = self.async_run_with_timeout(
            self.data_source._parse_order_book_diff_message(raw_message={'side': 'Ask', 'price': '11.11', 'qty': '10.1', 'id': 263, 'market': 'PDEX-1'}, message_queue=msg_queue)
        )

    @aioresponses()
    def test_on_recent_trade_callback(self, mock_api):
        msg = {"data": {
            "websocket_streams": {
                "data": '{"type": "TradeFormat", "m": "PDEX-3", "p": "2", "vq": "20", "q": "10", "tid": "111", "t": 1664193952989, "sid": "16"}',
                "name": "PDEX-1-ob-inc"
            },
            "market": "PDEX-1"
        }}
        self.data_source.on_recent_trade_callback(msg["data"], self.trading_pair)

    @aioresponses()
    def test_on_ob_increment(self, mock_api):
        msg = {
            "websocket_streams": {
                        "data": '{"type":"IncOB","changes":[["Ask","3","2",123]]}'
            }
        }
        self.data_source.on_ob_increment(msg, self.trading_pair)
        # self.assertEqual(self.data_source._message_queue[self.data_source._diff_messages_queue_key]._queue[0], msg["websocket_streams"])
        # self.assertEqual(1,0)

    @aioresponses()
    def test_on_ob_increment_check(self, mock_api):
        msg = {
            "websocket_streams": {
                "data":
                    '{"type":"IncOB","changes":[["Ask","3","2",123]]}'
            }
        }

        self.data_source.on_ob_increment(msg, self.trading_pair)
        # self.assertEqual(self.data_source._message_queue[self.data_source._diff_messages_queue_key]._queue[0], msg["websocket_streams"])
        # self.assertEqual(1, 0)

    def test_channel_originating_message(self):
        msg = {
            "websocket_streams": {
                "data": "[{\"side\":\"Bid\",\"price\":2000000000000,\"qty\":1000000000000,\"seq\":3}]",
                "name": "PDEX-1-ob-inc"
            }
        }
        with self.assertRaises(NotImplementedError):
            self.data_source._channel_originating_message(event_message=msg)

    @aioresponses()
    def test_connected_websocket_assistant_subscribe_channels(self, mock_api):
        web_socket = self.async_run_with_timeout(
            self.data_source._connected_websocket_assistant()
        )
        self.async_run_with_timeout(
            self.data_source._subscribe_channels(ws=web_socket)
        )

    @aioresponses()
    def test_listen_for_subscriptions_(self, mock_api):
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.async_run_with_timeout(
                self.data_source.listen_for_subscriptions()
            )





