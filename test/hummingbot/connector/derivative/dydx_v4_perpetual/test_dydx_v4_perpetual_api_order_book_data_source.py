import asyncio
import re
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import dateutil.parser as dp
import ujson
from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source import (
    DydxV4PerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_derivative import DydxV4PerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class DydxV4PerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = DydxV4PerpetualDerivative(
            client_config_map,
            dydx_v4_perpetual_secret_phrase="mirror actor skill push coach wait confirm orchard "
                                            "lunch mobile athlete gossip awake miracle matter "
                                            "bus reopen team ladder lazy list timber render wait",
            dydx_v4_perpetual_chain_address="dydx14zzueazeh0hj67cghhf9jypslcf9sh2n5k6art",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}-{self.quote_asset}": self.trading_pair})
        )
        self.data_source = DydxV4PerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.PATH_MARKETS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "markets": {
                self.trading_pair: {
                    "market": self.trading_pair,
                    "status": "ONLINE",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "stepSize": "0.1",
                    "tickSize": "0.01",
                    "indexPrice": "12",
                    "oraclePrice": "101",
                    "priceChange24H": "0",
                    "nextFundingRate": "0.0000125000",
                    "nextFundingAt": "2022-07-06T12:20:53.000Z",
                    "minOrderSize": "1",
                    "type": "PERPETUAL",
                    "initialMarginFraction": "0.10",
                    "maintenanceMarginFraction": "0.05",
                    "baselinePositionSize": "1000",
                    "incrementalPositionSize": "1000",
                    "incrementalInitialMarginFraction": "0.2",
                    "volume24H": "0",
                    "trades24H": "0",
                    "openInterest": "0",
                    "maxPositionSize": "10000",
                    "assetResolution": "10000000",
                    "syntheticAssetId": "0x4c494e4b2d37000000000000000000",
                }
            }
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_last_traded_prices([self.trading_pair]))

        self.assertEqual(1, len(result))
        self.assertEqual(float("101"), result[self.trading_pair])

    @aioresponses()
    def test_get_snapshot_raise_io_error(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.PATH_SNAPSHOT + "/" + self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=ujson.dumps({}))

        with self.assertRaisesRegex(
                IOError,
                f"Error executing request GET {url}. " f"HTTP status is 400. Error: {{}}",
        ):
            self.async_run_with_timeout(self.data_source._order_book_snapshot(self.trading_pair))

    @aioresponses()
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source."
        "DydxV4PerpetualAPIOrderBookDataSource._time"
    )
    def test_get_snapshot_successful(self, mock_api, mock_time):
        mock_time.return_value = 1640780000

        url = web_utils.public_rest_url(CONSTANTS.PATH_SNAPSHOT + "/" + self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "asks": [{"size": "2.0", "price": "20.0"}],
            "bids": [{"size": "1.0", "price": "10.0"}],
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source._order_book_snapshot(self.trading_pair))

        self.assertEqual(mock_response["asks"][0]["size"], str(result.asks[0].amount))
        self.assertEqual(mock_response["asks"][0]["price"], str(result.asks[0].price))
        self.assertEqual(mock_response["bids"][0]["size"], str(result.bids[0].amount))
        self.assertEqual(mock_response["bids"][0]["price"], str(result.bids[0].price))

        self.assertEqual(result.content["update_id"], 1640780000000000)

        self.assertEqual(self.trading_pair, result.trading_pair)

    @aioresponses()
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source"
        ".DydxV4PerpetualAPIOrderBookDataSource._time"
    )
    def test_get_snapshot_raises_error(self, mock_api, mock_time):
        mock_time.return_value = 1640780000

        url = web_utils.public_rest_url(CONSTANTS.PATH_SNAPSHOT + "/" + self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)

        with self.assertRaisesRegex(IOError, f"Error executing request GET {url}. HTTP status is 400. "):
            self.async_run_with_timeout(self.data_source._order_book_snapshot(self.trading_pair))

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.PATH_SNAPSHOT + "/" + self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "asks": [{"size": "2.0", "price": "20.0"}],
            "bids": [{"size": "1.0", "price": "10.0"}],
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1, len(list(result.bid_entries())))
        self.assertEqual(1, len(list(result.ask_entries())))
        self.assertEqual(float(mock_response["bids"][0]["price"]), list(result.bid_entries())[0].price)
        self.assertEqual(float(mock_response["bids"][0]["size"]), list(result.bid_entries())[0].amount)
        self.assertEqual(float(mock_response["asks"][0]["price"]), list(result.ask_entries())[0].price)
        self.assertEqual(float(mock_response["asks"][0]["size"]), list(result.ask_entries())[0].amount)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source."
        "DydxV4PerpetualAPIOrderBookDataSource._sleep"
    )
    def test_listen_for_subscriptions_raises_cancelled_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source."
        "DydxV4PerpetualAPIOrderBookDataSource._sleep"
    )
    def test_listen_for_subscriptions_raises_logs_exception(self, mock_sleep, ws_connect_mock):
        mock_sleep.side_effect = lambda: (self.ev_loop.run_until_complete(asyncio.sleep(0.5)))
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda *_: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait(), 1.0)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source."
        "DydxV4PerpetualAPIOrderBookDataSource._sleep"
    )
    def test_listen_for_subscriptions_successful(self, mock_sleep, ws_connect_mock):
        mock_sleep.side_effect = lambda: (self.ev_loop.run_until_complete(asyncio.sleep(0.5)))
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        mock_response = {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "connection_id": "d600a0d2-8039-4cd9-a010-2d6f5c336473",
            "message_id": 2,
            "id": self.trading_pair,
            "channel": CONSTANTS.WS_CHANNEL_ORDERBOOK,
            "contents": {"offset": "3218381978", "bids": [], "asks": [["36.152", "304.8"]]},
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=ujson.dumps(mock_response)
        )

        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, self.data_source._message_queue[self.data_source._diff_messages_queue_key].qsize())

        message = self.data_source._message_queue[self.data_source._diff_messages_queue_key]._queue[0]
        self.assertEqual(message, mock_response)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ws = self.async_run_with_timeout(self.data_source._connected_websocket_assistant())
        self.async_run_with_timeout(self.data_source._subscribe_channels(ws))

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertEqual(len(sent_messages), 3)

        self.assertEqual(sent_messages[0]["type"], CONSTANTS.WS_TYPE_SUBSCRIBE)
        self.assertEqual(sent_messages[0]["channel"], CONSTANTS.WS_CHANNEL_ORDERBOOK)
        self.assertEqual(sent_messages[0]["id"], self.trading_pair)

        self.assertEqual(sent_messages[1]["type"], CONSTANTS.WS_TYPE_SUBSCRIBE)
        self.assertEqual(sent_messages[1]["channel"], CONSTANTS.WS_CHANNEL_TRADES)
        self.assertEqual(sent_messages[1]["id"], self.trading_pair)

        self.assertEqual(sent_messages[2]["type"], CONSTANTS.WS_TYPE_SUBSCRIBE)
        self.assertEqual(sent_messages[2]["channel"], CONSTANTS.WS_CHANNEL_MARKETS)
        self.assertEqual(sent_messages[2]["id"], self.trading_pair)

        self.assertTrue(self._is_logged("INFO", "Subscribed to public orderbook and trade channels..."))

    def test_subscribe_channels_canceled(self):
        ws = MagicMock()
        ws.send.side_effect = asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._subscribe_channels(ws))

    def test_subscribe_channels_error(self):
        ws = MagicMock()
        ws.send.side_effect = Exception()

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_source._subscribe_channels(ws))

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "id": self.trading_pair,
            "connection_id": "e2a6c717-6f77-4c1c-ac22-72ce2b7ed77d",
            "channel": CONSTANTS.WS_CHANNEL_TRADES,
            "message_id": 2,
            "contents": {
                "trades": [
                    {
                        "side": "BUY",
                        "size": "100",
                    },
                    {"side": "SELL", "size": "100", "price": "4000", "createdAt": "2020-11-29T14:00:03.382Z"},
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
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "id": self.trading_pair,
            "connection_id": "e2a6c717-6f77-4c1c-ac22-72ce2b7ed77d",
            "channel": CONSTANTS.WS_CHANNEL_TRADES,
            "message_id": 2,
            "contents": {
                "trades": [
                    {"side": "BUY", "size": "100", "price": "4000", "createdAt": "2020-11-29T00:26:30.759Z"},
                    {"side": "SELL", "size": "100", "price": "4000", "createdAt": "2020-11-29T14:00:03.382Z"},
                ]
            },
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        timestamp = dp.parse(trade_event["contents"]["trades"][0]["createdAt"]).timestamp()
        trade_id = timestamp * 1e3

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_id, msg.trade_id)
        self.assertEqual(timestamp, msg.timestamp)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "id": self.trading_pair,
            "connection_id": "e2a6c717-6f77-4c1c-ac22-72ce2b7ed77d",
            "channel": CONSTANTS.WS_CHANNEL_ORDERBOOK,
            "message_id": 2,
            "contents": {"offset": "178", "bids": [["102"]], "asks": [["104", "0"]]},
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
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange")
        )

    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source."
        "DydxV4PerpetualAPIOrderBookDataSource._time"
    )
    def test_listen_for_order_book_diffs_successful(self, mock_time):
        mock_time.return_value = 1640780000

        mock_queue = AsyncMock()
        diff_event = {
            "type": CONSTANTS.WS_TYPE_CHANNEL_DATA,
            "id": self.trading_pair,
            "connection_id": "e2a6c717-6f77-4c1c-ac22-72ce2b7ed77d",
            "channel": CONSTANTS.WS_CHANNEL_ORDERBOOK,
            "message_id": 2,
            "contents": {"offset": "178", "bids": [["102", "11"]], "asks": [["104", "0"]]},
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1640780000, msg.timestamp)
        # Decreased by 1 because previous nonce is already taked by the execution
        expected_update_id = self.data_source._nonce_provider.get_tracking_nonce(timestamp=1640780000) - 1
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(102, bids[0].price)
        self.assertEqual(11, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(104, asks[0].price)
        self.assertEqual(0, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source"
        ".DydxV4PerpetualAPIOrderBookDataSource._sleep"
    )
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source"
        ".DydxV4PerpetualAPIOrderBookDataSource._time"
    )
    def test_listen_for_order_book_snapshots_log_exception(self, mock_time, mock_sleep):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 1

        mock_time.return_value = 1640780000

        mock_input_queue = AsyncMock()
        mock_output_queue = AsyncMock()

        mock_sleep.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        incomplete_resp = {
            "type": CONSTANTS.WS_TYPE_SUBSCRIBED,
            "connection_id": "87b25218-0170-4111-bfbf-d9f0a506fcab",
            "message_id": 1,
            "channel": CONSTANTS.WS_CHANNEL_ORDERBOOK,
            "id": self.trading_pair,
            "contents": {
                "bids": [
                    {
                        "price": "1779",
                    },
                    {"price": "1778.5", "size": "18"},
                ],
                "asks": [{"price": "1782.8", "size": "10"}, {"price": "1784", "size": "2.81"}],
            },
        }

        mock_input_queue.get.side_effect = [incomplete_resp]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_input_queue

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=mock_output_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book snapshots from exchange")
        )

    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source"
        ".DydxV4PerpetualAPIOrderBookDataSource._sleep"
    )
    @patch(
        "hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source"
        ".DydxV4PerpetualAPIOrderBookDataSource._time"
    )
    def test_listen_for_order_book_snapshots_successful(self, mock_time, mock_sleep):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 1

        mock_time.return_value = 1640780000

        mock_input_queue = AsyncMock()
        output_queue = asyncio.Queue()

        mock_sleep.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        resp = {
            "type": CONSTANTS.WS_TYPE_SUBSCRIBED,
            "connection_id": "87b25218-0170-4111-bfbf-d9f0a506fcab",
            "message_id": 1,
            "channel": CONSTANTS.WS_CHANNEL_ORDERBOOK,
            "id": self.trading_pair,
            "contents": {
                "bids": [{"price": "1779", "size": "1"}, {"price": "1778.5", "size": "18"}],
                "asks": [{"price": "1782.8", "size": "10"}, {"price": "1784", "size": "2.81"}],
            },
        }

        mock_input_queue.get.side_effect = [resp, Exception]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_input_queue

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=output_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        msg: OrderBookMessage = self.async_run_with_timeout(output_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1640780000, msg.timestamp)
        # Decreased by 1 because previous nonce is already taked by the execution
        expected_update_id = self.data_source._nonce_provider.get_tracking_nonce(timestamp=1640780000) - 1
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(1779, bids[0].price)
        self.assertEqual(1, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(1782.8, asks[0].price)
        self.assertEqual(10, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)
