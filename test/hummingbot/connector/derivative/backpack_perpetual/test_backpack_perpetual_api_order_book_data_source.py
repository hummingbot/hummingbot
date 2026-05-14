import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.backpack_perpetual import (
    backpack_perpetual_constants as CONSTANTS,
    backpack_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_api_order_book_data_source import (
    BackpackPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import BackpackPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class BackpackPerpetualAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}_PERP"
        cls.domain = "exchange"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.connector = BackpackPerpetualDerivative(
            backpack_api_key="",
            backpack_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.data_source = BackpackPerpetualAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                                   connector=self.connector,
                                                                   api_factory=self.connector._web_assistants_factory,
                                                                   domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    def _trade_update_event(self):
        resp = {
            "stream": f"trade.{self.ex_trading_pair}",
            "data": {
                "e": "trade",
                "E": 123456789,
                "s": self.ex_trading_pair,
                "t": 12345,
                "p": "0.001",
                "q": "100",
                "b": 88,
                "a": 50,
                "T": 123456785,
                "m": True,
                "M": True
            }
        }
        return resp

    def _order_diff_event(self):
        resp = {
            "stream": f"depth.{self.ex_trading_pair}",
            "data": {
                "e": "depth",
                "E": 123456789,
                "s": self.ex_trading_pair,
                "U": 157,
                "u": 160,
                "b": [["0.0024", "10"]],
                "a": [["0.0026", "100"]]
            }
        }
        return resp

    def _snapshot_response(self):
        resp = {
            "lastUpdateId": 1027024,
            "bids": [
                [
                    "4.00000000",
                    "431.00000000"
                ]
            ],
            "asks": [
                [
                    "4.00000200",
                    "12.00000000"
                ]
            ]
        }
        return resp

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        expected_update_id = resp["lastUpdateId"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4, bids[0].price)
        self.assertEqual(431, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(4.000002, asks[0].price)
        self.assertEqual(12, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_channels(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "result": None,
        }
        result_subscribe_diffs = {
            "result": None,
        }
        result_subscribe_funding_rates = {
            "result": None,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_funding_rates))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_subscription_messages))
        expected_trade_subscription = {
            "method": "SUBSCRIBE",
            "params": [f"trade.{self.ex_trading_pair}"]}
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "method": "SUBSCRIBE",
            "params": [f"depth.{self.ex_trading_pair}"]}
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])
        expected_funding_subscription = {
            "method": "SUBSCRIBE",
            "params": [f"markPrice.{self.ex_trading_pair}"]}
        self.assertEqual(expected_funding_subscription, sent_subscription_messages[2])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        self.data_source._ws_assistant = mock_ws

        # Mock exchange_symbol_associated_to_pair to raise an exception
        with patch.object(self.connector, 'exchange_symbol_associated_to_pair', side_effect=Exception("Test Error")):
            with self.assertRaises(Exception):
                await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "stream": f"trade.{self.ex_trading_pair}",
            "data": {
                "m": 1,
                "i": 2,
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(12345, msg.trade_id)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "stream": f"depth.{self.ex_trading_pair}",
            "data": {
                "m": 1,
                "i": 2,
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(diff_event["data"]["u"], msg.update_id)

    @aioresponses()
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @aioresponses()
    @patch("hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_api_order_book_data_source"
           ".BackpackPerpetualAPIOrderBookDataSource._sleep")
    async def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception, repeat=True)

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )
        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    async def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(1027024, msg.update_id)

    @aioresponses()
    async def test_get_funding_info(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARK_PRICE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        funding_resp = [
            {
                "symbol": self.ex_trading_pair,
                "indexPrice": "50000.00",
                "markPrice": "50001.50",
                "nextFundingTimestamp": 1234567890000,
                "fundingRate": "0.0001"
            }
        ]

        mock_api.get(regex_url, body=json.dumps(funding_resp))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("50000.00"), funding_info.index_price)
        self.assertEqual(Decimal("50001.50"), funding_info.mark_price)
        self.assertEqual(1234567890, funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal("0.0001"), funding_info.rate)

    # Dynamic subscription tests

    async def test_subscribe_to_trading_pair_successful(self):
        """Test successful subscription to a trading pair."""
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.subscribe_to_trading_pair(self.ex_trading_pair)

        self.assertTrue(result)
        # Backpack subscribes to 2 channels: trade and depth
        self.assertEqual(2, mock_ws.send.call_count)

        # Verify the subscription payloads
        calls = mock_ws.send.call_args_list
        trade_payload = calls[0][0][0].payload
        depth_payload = calls[1][0][0].payload

        self.assertEqual("SUBSCRIBE", trade_payload["method"])
        self.assertEqual([f"trade.{self.ex_trading_pair}"], trade_payload["params"])
        self.assertEqual("SUBSCRIBE", depth_payload["method"])
        self.assertEqual([f"depth.{self.ex_trading_pair}"], depth_payload["params"])

    async def test_subscribe_to_trading_pair_websocket_not_connected(self):
        """Test subscription when WebSocket is not connected."""
        self.data_source._ws_assistant = None

        result = await self.data_source.subscribe_to_trading_pair(self.ex_trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("WARNING", f"Cannot unsubscribe from {self.ex_trading_pair}: WebSocket not connected")
        )

    async def test_subscribe_to_trading_pair_raises_cancel_exception(self):
        """Test that CancelledError is properly raised during subscription."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.subscribe_to_trading_pair(self.ex_trading_pair)

    async def test_subscribe_to_trading_pair_raises_exception_and_logs_error(self):
        """Test that exceptions during subscription are logged and return False."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.subscribe_to_trading_pair(self.ex_trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("ERROR", f"Error subscribing to {self.ex_trading_pair}")
        )

    async def test_unsubscribe_from_trading_pair_successful(self):
        """Test successful unsubscription from a trading pair."""
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.unsubscribe_from_trading_pair(self.ex_trading_pair)

        self.assertTrue(result)
        # Backpack sends 2 unsubscribe messages: trade and depth
        self.assertEqual(2, mock_ws.send.call_count)

        # Verify the unsubscription payloads
        calls = mock_ws.send.call_args_list
        trade_payload = calls[0][0][0].payload
        depth_payload = calls[1][0][0].payload

        self.assertEqual("UNSUBSCRIBE", trade_payload["method"])
        self.assertEqual([f"trade.{self.ex_trading_pair}"], trade_payload["params"])
        self.assertEqual("UNSUBSCRIBE", depth_payload["method"])
        self.assertEqual([f"depth.{self.ex_trading_pair}"], depth_payload["params"])

    async def test_unsubscribe_from_trading_pair_websocket_not_connected(self):
        """Test unsubscription when WebSocket is not connected."""
        self.data_source._ws_assistant = None

        result = await self.data_source.unsubscribe_from_trading_pair(self.ex_trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("WARNING", f"Cannot unsubscribe from {self.ex_trading_pair}: WebSocket not connected")
        )

    async def test_unsubscribe_from_trading_pair_raises_cancel_exception(self):
        """Test that CancelledError is properly raised during unsubscription."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.unsubscribe_from_trading_pair(self.ex_trading_pair)

    async def test_unsubscribe_from_trading_pair_raises_exception_and_logs_error(self):
        """Test that exceptions during unsubscription are logged and return False."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.unsubscribe_from_trading_pair(self.ex_trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error occurred unsubscribing from {self.ex_trading_pair}...")
        )

    async def test_subscribe_funding_info_successful(self):
        """Test successful subscription to funding info."""
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        await self.data_source.subscribe_funding_info(self.ex_trading_pair)

        # Verify send was called once for funding info subscription
        self.assertEqual(1, mock_ws.send.call_count)

        # Verify the subscription payload
        call = mock_ws.send.call_args_list[0]
        payload = call[0][0].payload

        self.assertEqual("SUBSCRIBE", payload["method"])
        self.assertEqual([f"markPrice.{self.ex_trading_pair}"], payload["params"])

    async def test_subscribe_funding_info_websocket_not_connected(self):
        """Test funding info subscription when WebSocket is not connected."""
        self.data_source._ws_assistant = None

        await self.data_source.subscribe_funding_info(self.ex_trading_pair)

        self.assertTrue(
            self._is_logged("WARNING", f"Cannot unsubscribe from {self.ex_trading_pair}: WebSocket not connected")
        )

    async def test_subscribe_funding_info_raises_cancel_exception(self):
        """Test that CancelledError is properly raised during funding info subscription."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.subscribe_funding_info(self.ex_trading_pair)

    async def test_subscribe_funding_info_raises_exception_and_logs_error(self):
        """Test that exceptions during funding info subscription are logged."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        await self.data_source.subscribe_funding_info(self.ex_trading_pair)

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error occurred subscribing to funding info for {self.ex_trading_pair}...")
        )
