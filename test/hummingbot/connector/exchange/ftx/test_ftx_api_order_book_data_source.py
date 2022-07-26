import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses

# from hummingbot.client.config.client_config_map import ClientConfigMap
# from hummingbot.client.config.config_helpers import ClientConfigAdapter
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.ftx import ftx_constants as CONSTANTS, ftx_web_utils as web_utils
from hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source import FtxAPIOrderBookDataSource
from hummingbot.connector.exchange.ftx.ftx_exchange import FtxExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class FtxAPIOrderBookDataSourceUnitTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.trading_pair.replace("-", "/")

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = FtxExchange(
            client_config_map=client_config_map,
            ftx_api_key="",
            ftx_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.data_source = FtxAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}/{self.quote_asset}": self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    @patch("hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source.FtxAPIOrderBookDataSource._time")
    def test_get_new_order_book_successful(self, mock_api, time_mock):
        time_mock.return_value = 1640001112.223334
        url = web_utils.public_rest_url(path_url=CONSTANTS.FTX_ORDER_BOOK_PATH.format(self.ex_trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "success": True,
            "result": {
                "asks": [
                    [
                        4114.25,
                        6.263
                    ]
                ],
                "bids": [
                    [
                        4112.25,
                        49.29
                    ]
                ]
            }
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = int(time_mock.return_value * 1e3)

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
        url = web_utils.public_rest_url(path_url=CONSTANTS.FTX_ORDER_BOOK_PATH.format(self.ex_trading_pair))
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
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "subscribed",
            "code": 0,
            "msg": "",
            "data": None,
        }
        result_subscribe_order_book = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "subscribed",
            "code": 0,
            "msg": "",
            "data": None,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_order_book))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "op": "subscribe",
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair}
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "op": "subscribe",
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair}
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_sends_ping_message_before_ping_interval_finishes(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = [asyncio.TimeoutError("Test timeout"),
                                                            asyncio.CancelledError]

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = {"op": "ping"}
        self.assertEqual(expected_ping_message, sent_messages[2])

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_error_coming_from_the_exchange(self, ws_connect_mock, sleep_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "subscribed",
            "code": 0,
            "msg": "",
            "data": None,
        }
        result_subscribe_order_book = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "subscribed",
            "code": 0,
            "msg": "",
            "data": None,
        }
        error_message = {
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "error",
            "code": "400",
            "msg": "An error message",
            "data": None
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_order_book))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(error_message))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

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

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": [
                {
                    "price": 10000,
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": [
                {
                    "id": 4442208960,
                    "price": 42219.9,
                    "size": 0.12060306,
                    "side": "buy",
                    "liquidation": False,
                    "time": datetime.fromtimestamp(1640002223.334445, tz=timezone.utc).isoformat()
                }
            ]
        }

        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(int(trade_event["data"][0]["id"]), msg.trade_id)
        self.assertEqual(1640002223.334445, msg.timestamp)

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

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": {}
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": {
                "time": 1640001112.223334,
                "checksum": 329366394,
                "bids": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
                "asks": [[20460.0, 0.039]],
                "action": "update"
            }
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1640001112.223334, msg.timestamp)
        expected_update_id = int(1640001112.223334 * 1e3)
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

    @patch("hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source"
           ".FtxAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, _):
        incomplete_resp = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "partial",
            "data": {}
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
            self._is_logged("ERROR", "Unexpected error when processing public order book snapshots from exchange"))

    def test_listen_for_order_book_snapshots_successful(self):
        mock_queue = AsyncMock()
        snapshot_event = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "partial",
            "data": {
                "time": 1640001112.223334,
                "checksum": 329366394,
                "bids": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
                "asks": [[20460.0, 0.039]],
                "action": "partial"
            }
        }
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1640001112.223334, msg.timestamp)
        expected_update_id = int(1640001112.223334 * 1e3)
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
    @patch("hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source.FtxAPIOrderBookDataSource._time")
    def test_trade_event_correctly_queued(self, time_mock, ws_connect_mock):
        time_mock.return_value = 0
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_event = {
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": [
                {
                    "id": 4442208960,
                    "price": 42219.9,
                    "size": 0.12060306,
                    "side": "buy",
                    "liquidation": False,
                    "time": datetime.fromtimestamp(1640002223.334445, tz=timezone.utc).isoformat()
                }
            ]
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(trade_event))

        ws: WSAssistant = self.async_run_with_timeout(self.data_source._api_factory.get_ws_assistant())
        self.async_run_with_timeout(ws.connect(""))
        self.listening_task = self.ev_loop.create_task(self.data_source._process_websocket_messages(ws))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        trades_queue: asyncio.Queue = self.data_source._message_queue[self.data_source._trade_messages_queue_key]
        self.assertEqual(1, trades_queue.qsize())
        queued_message = trades_queue.get_nowait()
        self.assertEqual(trade_event, queued_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source.FtxAPIOrderBookDataSource._time")
    def test_snapshot_event_correctly_queued(self, time_mock, ws_connect_mock):
        time_mock.return_value = 0
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        snapshot_event = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "partial",
            "data": {
                "time": 1640001112.223334,
                "checksum": 329366394,
                "bids": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
                "asks": [[20460.0, 0.039]],
                "action": "partial"
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(snapshot_event))

        ws: WSAssistant = self.async_run_with_timeout(self.data_source._api_factory.get_ws_assistant())
        self.async_run_with_timeout(ws.connect(""))
        self.listening_task = self.ev_loop.create_task(self.data_source._process_websocket_messages(ws))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        snapshots_queue: asyncio.Queue = self.data_source._message_queue[self.data_source._snapshot_messages_queue_key]
        self.assertEqual(1, snapshots_queue.qsize())
        queued_message = snapshots_queue.get_nowait()
        self.assertEqual(snapshot_event, queued_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source.FtxAPIOrderBookDataSource._time")
    def test_diff_event_correctly_queued(self, time_mock, ws_connect_mock):
        time_mock.return_value = 0
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        diff_event = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": {
                "time": 1640001112.223334,
                "checksum": 329366394,
                "bids": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
                "asks": [[20460.0, 0.039]],
                "action": "update"
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(diff_event))

        ws: WSAssistant = self.async_run_with_timeout(self.data_source._api_factory.get_ws_assistant())
        self.async_run_with_timeout(ws.connect(""))
        self.listening_task = self.ev_loop.create_task(self.data_source._process_websocket_messages(ws))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        diffs_queue: asyncio.Queue = self.data_source._message_queue[self.data_source._diff_messages_queue_key]
        self.assertEqual(1, diffs_queue.qsize())
        queued_message = diffs_queue.get_nowait()
        self.assertEqual(diff_event, queued_message)
