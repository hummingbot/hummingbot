import asyncio
import json
import re
from datetime import datetime
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.ciex import ciex_constants as CONSTANTS, ciex_web_utils as web_utils
from hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source import CiexAPIOrderBookDataSource
from hummingbot.connector.exchange.ciex.ciex_exchange import CiexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class CiexAPIOrderBookDataSourceUnitTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset.lower()}{cls.quote_asset.lower()}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = CiexExchange(
            client_config_map=client_config_map,
            ciex_api_key="",
            ciex_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.data_source = CiexAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset.lower()}{self.quote_asset.lower()}": self.trading_pair})
        )

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    @patch("hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source.CiexAPIOrderBookDataSource._time")
    def test_get_new_order_book_successful(self, mock_api, time_mock):
        time_mock.return_value = 1640001112.223334
        url = web_utils.public_rest_url(path_url=CONSTANTS.CIEX_DEPTH_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "time": 1595563624731,
            "bids": [[4112.25, 49.29]],  # price  # amount
            "asks": [[4114.25, 6.263]],
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = int(resp["time"])

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4112.25, bids[0].price)
        self.assertEqual(49.29, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(4114.25, asks[0].price)
        self.assertEqual(6.263, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.CIEX_DEPTH_PATH.format(self.ex_trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps({})
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "event": "sub",
            "params": {"channel": CONSTANTS.WS_PUBLIC_TRADES_CHANNEL.format(self.ex_trading_pair.lower())},
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "event": "sub",
            "params": {"channel": CONSTANTS.WS_FULL_DEPTH_CHANNEL.format(self.ex_trading_pair.lower())},
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book and trade channels..."))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...")
        )

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source.CiexAPIOrderBookDataSource._time")
    def test_pong_message_sent_when_ping_received(self, time_mock, ws_connect_mock):
        time_mock.return_value = 0
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ping_message = {
            "ping": 1535975085052,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(ping_message)
        )

        ws: WSAssistant = self.async_run_with_timeout(self.data_source._api_factory.get_ws_assistant())
        self.async_run_with_timeout(ws.connect(""))
        self.listening_task = self.ev_loop.create_task(self.data_source._process_websocket_messages(ws))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )
        self.assertEqual(1, len(sent_messages))
        expected_pong = {"pong": ping_message["ping"]}
        self.assertEqual(expected_pong, sent_messages[0])

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "channel": CONSTANTS.WS_PUBLIC_TRADES_CHANNEL.format(self.ex_trading_pair.lower()),
            "ts": 1506584998239,
            "tick": {
                "data": [
                    {
                        "side": "buy",
                    }
                ]
            },
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {
            "channel": CONSTANTS.WS_PUBLIC_TRADES_CHANNEL.format(self.ex_trading_pair.lower()),
            "ts": 1506584998000,
            "tick": {
                "data": [
                    {
                        "side": "BUY",
                        "ts": 1506584998239,
                        "price": 32.233,
                        "vol": 232,
                        "amount": 323,
                        "ds": datetime.fromtimestamp(1506584998).strftime("%Y-%m-%d %H:%M:%S"),
                    }
                ]
            },
        }

        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_event["tick"]["data"][0]["ts"], msg.trade_id)
        self.assertEqual(trade_event["tick"]["data"][0]["ts"] * 1e-3, msg.timestamp)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_snapshots_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source" ".CiexAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, _):
        incomplete_resp = {
            "channel": CONSTANTS.WS_FULL_DEPTH_CHANNEL.format(self.ex_trading_pair.lower()),
            "ts": 1506584998239,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book snapshots from exchange")
        )

    def test_listen_for_order_book_snapshots_successful(self):
        mock_queue = AsyncMock()
        snapshot_event = {
            "channel": CONSTANTS.WS_FULL_DEPTH_CHANNEL.format(self.ex_trading_pair.lower()),
            "ts": 1506584998239,
            "tick": {
                "asks": [[20460.0, 0.039]],
                "buys": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
            },
        }

        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(snapshot_event["ts"] * 1e-3, msg.timestamp)
        expected_update_id = snapshot_event["ts"]
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(20447.0, bids[0].price)
        self.assertEqual(0.1901, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(20460.0, asks[0].price)
        self.assertEqual(0.039, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source.CiexAPIOrderBookDataSource._time")
    def test_trade_event_correctly_queued(self, time_mock, ws_connect_mock):
        time_mock.return_value = 0
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_event = {
            "channel": CONSTANTS.WS_PUBLIC_TRADES_CHANNEL.format(self.ex_trading_pair.lower()),
            "ts": 1506584998000,
            "tick": {
                "data": [
                    {
                        "side": "BUY",
                        "ts": 1506584998239,
                        "price": 32.233,
                        "vol": 232,
                        "amount": 323,
                        "ds": datetime.fromtimestamp(1506584998).strftime("%Y-%m-%d %H:%M:%S"),
                    }
                ]
            },
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(trade_event)
        )

        ws: WSAssistant = self.async_run_with_timeout(self.data_source._api_factory.get_ws_assistant())
        self.async_run_with_timeout(ws.connect(""))
        self.listening_task = self.ev_loop.create_task(self.data_source._process_websocket_messages(ws))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        trades_queue: asyncio.Queue = self.data_source._message_queue[self.data_source._trade_messages_queue_key]
        self.assertEqual(1, trades_queue.qsize())
        queued_message = trades_queue.get_nowait()
        self.assertEqual(trade_event, queued_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source.CiexAPIOrderBookDataSource._time")
    def test_snapshot_event_correctly_queued(self, time_mock, ws_connect_mock):
        time_mock.return_value = 0
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        snapshot_event = {
            "channel": CONSTANTS.WS_FULL_DEPTH_CHANNEL.format(self.ex_trading_pair.lower()),
            "ts": 1506584998239,
            "tick": {
                "asks": [[20460.0, 0.039]],
                "buys": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
            },
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(snapshot_event)
        )

        ws: WSAssistant = self.async_run_with_timeout(self.data_source._api_factory.get_ws_assistant())
        self.async_run_with_timeout(ws.connect(""))
        self.listening_task = self.ev_loop.create_task(self.data_source._process_websocket_messages(ws))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        snapshots_queue: asyncio.Queue = self.data_source._message_queue[self.data_source._snapshot_messages_queue_key]
        self.assertEqual(1, snapshots_queue.qsize())
        queued_message = snapshots_queue.get_nowait()
        self.assertEqual(snapshot_event, queued_message)
