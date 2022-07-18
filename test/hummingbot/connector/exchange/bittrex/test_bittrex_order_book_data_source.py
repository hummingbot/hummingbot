import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses

from hummingbot.connector.exchange.bittrex import bittrex_constants as CONSTANTS, bittrex_web_utils as web_utils
from hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source import BittrexAPIOrderBookDataSource
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook


class BittrexOrderBookDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self._finalMessage = 'FinalDummyMessage'
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.output_queue = asyncio.Queue()
        self.connector = AsyncMock()
        self.data_source = BittrexAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                         connector=self.connector,
                                                         api_factory=web_utils.build_api_factory())

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

    def _create_queue_mock(self):
        queue = AsyncMock()
        queue.get.side_effect = self._get_next_ws_received_message
        return queue

    async def _get_next_ws_received_message(self):
        message = await self.ws_incoming_messages.get()
        if message == self._finalMessage:
            self.resume_test_event.set()
        return message

    def _trade_update_event(self):
        resp = {
            "sequence": "int",
            "marketSymbol": self.symbol,
            "deltas": [
                {
                    "id": "string (uuid)",
                    "executedAt": "string (date-time)",
                    "quantity": "number (double)",
                    "rate": "number (double)",
                    "takerSide": "string"
                }
            ]
        }
        return resp

    def _order_diff_event(self):
        resp = {
            "marketSymbol": self.symbol,
            "depth": 25,
            "sequence": "int",
            "bidDeltas": [
                {
                    "quantity": "number (double)",
                    "rate": "number (double)"
                }
            ],
            "askDeltas": [
                {
                    "quantity": "number (double)",
                    "rate": "number (double)"
                }
            ]
        }
        return resp

    def _snapshot_response(self):
        resp = {
            "bid": [
                {
                    "quantity": 431.0,
                    "rate": 4.0
                }
            ],
            "ask": [
                {
                    "quantity": 12.2,
                    "rate": 4.002
                }
            ]
        }
        return resp

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_URL.format(self.symbol))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(resp))
        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )
        bids = list(order_book["bid"])
        asks = list(order_book["ask"])
        self.assertEqual(1, len(bids))
        self.assertEqual(4.0, bids[0].rate)
        self.assertEqual(431, bids[0].quantity)
        self.assertEqual(1, len(asks))
        self.assertEqual(4.002, asks[0].rate)
        self.assertEqual(12.2, asks[0].quantity)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_URL.format(self.symbol))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_trades = {
            "R": [
                {
                    "Success": True,
                    "ErrorCode": None
                },
            ],
            "I": 1
        }
        result_subscribe_diffs = {
            "R": [
                {
                    "Success": True,
                    "ErrorCode": None
                },
            ],
            "I": 1
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "H": "c3",
            "M": "Subscribe",
            "A": [[f"trade_{self.symbol}"]],
            "I": 1
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "H": "c3",
            "M": "Subscribe",
            "A": [[f"orderbook_{self.symbol}_25"]],
            "I": 1
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("signalr_aio.Connection.start")
    @patch("asyncio.Queue")
    @patch(
        "hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source.BittrexAPIOrderBookDataSource"
        "._transform_raw_message"
    )
    def test_listen_for_trades(self, transform_raw_message_mock, mocked_connection, _):
        transform_raw_message_mock.side_effect = lambda arg: arg
        mocked_connection.return_value = self._create_queue_mock()
        self.ws_incoming_messages.put_nowait(
            {
                'nonce': 1630292147820.41,
                'type': 'trade',
                'results': {
                    'deltas': [
                        {
                            'id': 'b25fd775-bc1d-4f83-a82f-ff3022bb6982',
                            'executedAt': '2021-08-30T02:55:47.75Z',
                            'quantity': '0.01000000',
                            'rate': '3197.61663059',
                            'takerSide': 'SELL',
                        }
                    ],
                    'sequence': 1228,
                    'marketSymbol': self.trading_pair,
                }
            }
        )
        self.ws_incoming_messages.put_nowait(self._finalMessage)  # to resume test event
        self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
        self.ev_loop.create_task(self.ob_data_source.listen_for_trades(self.ev_loop, self.output_queue))
        self.ev_loop.run_until_complete(asyncio.wait([self.resume_test_event.wait()], timeout=1))

        queued_msg = self.output_queue.get_nowait()
        self.assertEquals(queued_msg.trading_pair, self.trading_pair)

    @patch("signalr_aio.Connection.start")
    @patch("asyncio.Queue")
    @patch(
        "hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source.BittrexAPIOrderBookDataSource"
        "._transform_raw_message"
    )
    def test_listen_for_order_book_diffs(self, transform_raw_message_mock, mocked_connection, _):
        transform_raw_message_mock.side_effect = lambda arg: arg
        mocked_connection.return_value = self._create_queue_mock()
        self.ws_incoming_messages.put_nowait(
            {
                'nonce': 1630292145769.5452,
                'type': 'delta',
                'results': {
                    'marketSymbol': self.trading_pair,
                    'depth': 25,
                    'sequence': 148887,
                    'bidDeltas': [],
                    'askDeltas': [
                        {
                            'quantity': '0',
                            'rate': '3199.09000000',
                        },
                        {
                            'quantity': '0.36876366',
                            'rate': '3200.78897180',
                        },
                    ],
                },
            }
        )
        self.ws_incoming_messages.put_nowait(self._finalMessage)  # to resume test event
        self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
        self.ev_loop.create_task(self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, self.output_queue))
        self.ev_loop.run_until_complete(asyncio.wait([self.resume_test_event.wait()], timeout=1))

        queued_msg = self.output_queue.get_nowait()
        self.assertEquals(queued_msg.trading_pair, self.trading_pair)
