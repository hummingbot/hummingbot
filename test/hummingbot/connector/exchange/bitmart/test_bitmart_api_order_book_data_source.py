import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import WSMsgType
from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.connector.exchange.bitmart.bitmart_api_order_book_data_source import BitmartAPIOrderBookDataSource
from hummingbot.connector.exchange.bitmart.bitmart_exchange import BitmartExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitmartAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.connector = BitmartExchange(
            bitmart_api_key="",
            bitmart_secret_key="",
            bitmart_memo="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.data_source = BitmartAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair}))

    def handle(self, record):
        self.log_records.append(record)

    def _order_book_snapshot_example(self):
        return {
            "data": {
                "ts": 1527777538000,
                "symbol": "COINALPHA_HBOT",
                "asks": [
                    [
                        "1.00",
                        "0.007000"
                    ]
                ],
                "bids": [
                    [
                        "0.000767",
                        "4800.0"
                    ],
                    [
                        "0.000201",
                        "99996475.79"
                    ]
                ]
            }
        }

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @aioresponses()
    def test_get_last_traded_prices(self, mock_get):
        mock_response: Dict[Any] = {
            "message": "OK",
            "code": 1000,
            "trace": "6e42c7c9-fdc5-461b-8fd1-b4e2e1b9ed57",
            "data": {
                "symbol": "COINALPHA_HBOT",
                "last": "1.00",
                "qv_24h": "201477650.88000",
                "v_24h": "25186.48000",
                "high_24h": "8800.00",
                "low_24h": "1.00",
                "open_24h": "8800.00",
                "ask_px": "0.00",
                "ask_sz": "0.00000",
                "bid_px": "0.00",
                "bid_sz": "0.00000",
                "fluctuation": "-0.9999"
            }
        }
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_LAST_TRADING_PRICES_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))

        results = self.local_event_loop.run_until_complete(
            asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results: Dict[str, Any] = results[0]

        self.assertEqual(results[self.trading_pair], float("1.00"))

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_get):
        mock_response: Dict[str, Any] = self._order_book_snapshot_example()
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))

        results = self.local_event_loop.run_until_complete(
            asyncio.gather(self.data_source.get_new_order_book(self.trading_pair)))
        order_book: OrderBook = results[0]

        self.assertTrue(type(order_book) is OrderBook)
        self.assertEqual(order_book.snapshot_uid, mock_response["data"]["ts"])

        self.assertEqual(mock_response["data"]["ts"], order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(2, len(bids))
        self.assertEqual(float(mock_response["data"]["bids"][0][0]), bids[0].price)
        self.assertEqual(float(mock_response["data"]["bids"][0][1]), bids[0].amount)
        self.assertEqual(mock_response["data"]["ts"], bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(float(mock_response["data"]["asks"][0][0]), asks[0].price)
        self.assertEqual(float(mock_response["data"]["asks"][0][1]), asks[0].amount)
        self.assertEqual(mock_response["data"]["ts"], asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "event": "subscribe",
            "table": f"{CONSTANTS.PUBLIC_TRADE_CHANNEL_NAME}:{self.ex_trading_pair}",
        }
        result_subscribe_diffs = {
            "event": "subscribe",
            "table": f"{CONSTANTS.PUBLIC_DEPTH_CHANNEL_NAME}:{self.ex_trading_pair}",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "op": "subscribe",
            "args": [f"{CONSTANTS.PUBLIC_TRADE_CHANNEL_NAME}:{self.ex_trading_pair}"]
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "op": "subscribe",
            "args": [f"{CONSTANTS.PUBLIC_DEPTH_CHANNEL_NAME}:{self.ex_trading_pair}"]
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        try:
            await self.data_source.listen_for_subscriptions()
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_compressed_messages_are_correctly_read(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "event": "subscribe",
            "table": f"{CONSTANTS.PUBLIC_TRADE_CHANNEL_NAME}:{self.ex_trading_pair}",
        }
        result_subscribe_diffs = {
            "event": "subscribe",
            "table": f"{CONSTANTS.PUBLIC_DEPTH_CHANNEL_NAME}:{self.ex_trading_pair}",
        }

        trade_event = {
            "table": CONSTANTS.PUBLIC_TRADE_CHANNEL_NAME,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "price": "162.12",
                    "side": "buy",
                    "size": "11.085",
                    "s_t": 1542337219
                },
                {
                    "symbol": self.ex_trading_pair,
                    "price": "163.12",
                    "side": "buy",
                    "size": "15",
                    "s_t": 1542337238
                }
            ]
        }

        compressed_trade_event = bitmart_utils.compress_ws_message(json.dumps(trade_event))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=compressed_trade_event,
            message_type=WSMsgType.BINARY
        )

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        trade_message = await self.data_source._message_queue[self.data_source._trade_messages_queue_key].get()

        self.assertEqual(trade_event, trade_message)

    async def test_listen_for_trades(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_queue = AsyncMock()

        trade_event = {
            "table": CONSTANTS.PUBLIC_TRADE_CHANNEL_NAME,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "price": "162.12",
                    "side": "buy",
                    "size": "11.085",
                    "s_t": 1542337219
                },
                {
                    "symbol": self.ex_trading_pair,
                    "price": "163.12",
                    "side": "buy",
                    "size": "15",
                    "s_t": 1542337238
                }
            ]
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        )

        trade1: OrderBookMessage = await msg_queue.get()
        trade2: OrderBookMessage = await msg_queue.get()

        self.assertTrue(msg_queue.empty())
        self.assertEqual(1542337219, int(trade1.trade_id))
        self.assertEqual(1542337238, int(trade2.trade_id))

    async def test_listen_for_trades_raises_cancelled_exception(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "table": CONSTANTS.PUBLIC_TRADE_CHANNEL_NAME,
            "data": [
                {
                    "symbol": self.ex_trading_pair,

                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        snapshot_event = {
            "table": CONSTANTS.PUBLIC_DEPTH_CHANNEL_NAME,
            "data": [
                {
                    "asks": [["161.96", "7.37567"]],
                    "bids": [["161.94", "4.552355"]],
                    "symbol": self.ex_trading_pair,
                    "ms_t": 1542337219120
                }
            ]
        }
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(snapshot_event["data"][0]["ms_t"]) * 1e-3, msg.timestamp)
        expected_update_id = int(snapshot_event["data"][0]["ms_t"])
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(float(snapshot_event["data"][0]["bids"][0][0]), bids[0].price)
        self.assertEqual(float(snapshot_event["data"][0]["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(float(snapshot_event["data"][0]["asks"][0][0]), asks[0].price)
        self.assertEqual(float(snapshot_event["data"][0]["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    async def test_listen_for_order_book_snapshots_raises_cancelled_exception(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_snapshots_logs_exception(self):
        incomplete_resp = {
            "table": CONSTANTS.PUBLIC_DEPTH_CHANNEL_NAME,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "ms_t": 1542337219120
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))
