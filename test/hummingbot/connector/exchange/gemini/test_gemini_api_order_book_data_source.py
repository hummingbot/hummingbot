import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_api_order_book_data_source import GeminiAPIOrderBookDataSource
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class GeminiAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = "btcusd"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.connector = GeminiExchange(
            gemini_api_key="",
            gemini_api_secret="",
            trading_pairs=[self.trading_pair],
            trading_required=False)
        self.data_source = GeminiAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

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

    def _snapshot_response(self):
        return {
            "bids": [
                {"price": "9", "amount": "1", "timestamp": "1500000000"},
            ],
            "asks": [
                {"price": "11", "amount": "2", "timestamp": "1500000000"},
            ],
        }

    def _trade_event(self):
        return {
            "type": "trade",
            "symbol": "BTCUSD",
            "event_id": 1,
            "timestamp": 1700000000000,
            "E": 1700000000000000000,
            "s": self.ex_trading_pair,
            "t": 12345,
            "p": "10.0",
            "q": "0.5",
            "m": False,
        }

    def _diff_event(self):
        return {
            "e": CONSTANTS.WS_EVENT_DEPTH_UPDATE,
            "s": self.ex_trading_pair,
            "U": 100,
            "u": 110,
            "b": [["9", "1"]],
            "a": [["11", "2"]],
        }

    def _set_symbol_map_with_extra_pair(self, trading_pair: str, exchange_symbol: str):
        self.connector._set_trading_pair_symbol_map(bidict({
            self.ex_trading_pair: self.trading_pair,
            exchange_symbol: trading_pair,
        }))

    # ------------------------------------------------------------------
    # REST snapshot
    # ------------------------------------------------------------------

    async def test_get_new_order_book_successful(self):
        rest_assistant = MagicMock()
        rest_assistant.execute_request = AsyncMock(return_value=self._snapshot_response())
        self.data_source._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(9, bids[0].price)
        self.assertEqual(1, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(11, asks[0].price)
        self.assertEqual(2, asks[0].amount)

    async def test_request_order_book_snapshot_requests_full_depth(self):
        rest_assistant = MagicMock()
        rest_assistant.execute_request = AsyncMock(return_value=self._snapshot_response())
        self.data_source._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        await self.data_source._request_order_book_snapshot(self.trading_pair)

        _, kwargs = rest_assistant.execute_request.call_args
        self.assertEqual({"limit_bids": 0, "limit_asks": 0}, kwargs["params"])

    async def test_get_new_order_book_raises_exception(self):
        rest_assistant = MagicMock()
        rest_assistant.execute_request = AsyncMock(side_effect=IOError)
        self.data_source._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    async def test_get_last_traded_prices_delegates_to_connector(self):
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 10.0})
        result = await self.data_source.get_last_traded_prices([self.trading_pair])
        self.assertEqual({self.trading_pair: 10.0}, result)

    # ------------------------------------------------------------------
    # WS subscriptions
    # ------------------------------------------------------------------

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps({"result": None, "id": 1}))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)
        self.assertEqual(2, len(sent))
        self.assertEqual([CONSTANTS.WS_TRADE_STREAM.format(self.ex_trading_pair)], sent[0]["params"])
        self.assertEqual([CONSTANTS.WS_DEPTH_STREAM.format(self.ex_trading_pair)], sent[1]["params"])
        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book and trade channels..."))

    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws):
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
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("Test Error"))
        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred subscribing to order book trading and delta streams..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connected_websocket_assistant(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws = await self.data_source._connected_websocket_assistant()
        self.assertIsNotNone(ws)
        ws_connect_mock.assert_called_once()
        self.assertEqual(
            web_utils.wss_url(snapshot=-1),
            ws_connect_mock.call_args.args[0],
        )

    # ------------------------------------------------------------------
    # Message parsing
    # ------------------------------------------------------------------

    async def test_parse_trade_message_queues_message(self):
        queue = asyncio.Queue()
        await self.data_source._parse_trade_message(self._trade_event(), queue)
        msg: OrderBookMessage = queue.get_nowait()
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])

    async def test_parse_trade_message_skips_subscription_ack(self):
        queue = asyncio.Queue()
        await self.data_source._parse_trade_message({"result": None, "id": 1}, queue)
        await self.data_source._parse_trade_message({"id": 1}, queue)
        self.assertEqual(0, queue.qsize())

    async def test_parse_order_book_diff_message_queues_message(self):
        queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message(self._diff_event(), queue)
        msg: OrderBookMessage = queue.get_nowait()
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])

    async def test_parse_order_book_snapshot_message_queues_sequence_bearing_snapshot(self):
        queue = asyncio.Queue()
        await self.data_source._parse_order_book_snapshot_message(self._diff_event(), queue)
        msg: OrderBookMessage = queue.get_nowait()
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(110, msg.update_id)
        self.assertEqual([["9", "1"]], msg.content["bids"])

    async def test_parse_order_book_diff_message_skips_non_depth(self):
        queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message({"result": None}, queue)
        await self.data_source._parse_order_book_diff_message({"id": 5}, queue)
        await self.data_source._parse_order_book_diff_message({"e": "other", "s": self.ex_trading_pair}, queue)
        self.assertEqual(0, queue.qsize())

    def test_channel_originating_message(self):
        snapshot_event = self._diff_event()
        self.assertEqual(
            self.data_source._snapshot_messages_queue_key,
            self.data_source._channel_originating_message(snapshot_event))
        next_diff = self._diff_event()
        next_diff.update({"U": 111, "u": 120})
        self.assertEqual(
            self.data_source._diff_messages_queue_key,
            self.data_source._channel_originating_message(next_diff))
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"t": 123}))
        self.assertEqual("", self.data_source._channel_originating_message({"result": None}))

    def test_channel_originating_message_ignores_stale_depth_update(self):
        self.data_source._channel_originating_message(self._diff_event())
        stale = self._diff_event()
        stale.update({"U": 100, "u": 109})
        self.assertEqual("", self.data_source._channel_originating_message(stale))

    def test_channel_originating_message_reconnects_on_sequence_gap(self):
        self.data_source._channel_originating_message(self._diff_event())
        gap = self._diff_event()
        gap.update({"U": 112, "u": 120})
        with self.assertRaisesRegex(ConnectionError, "sequence gap"):
            self.data_source._channel_originating_message(gap)
        self.assertNotIn(self.ex_trading_pair, self.data_source._snapshot_symbols)

    # ------------------------------------------------------------------
    # Listen loops (trades / diffs / snapshots)
    # ------------------------------------------------------------------

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_event(), asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertIs(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(12345, msg.trade_id)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(float(TradeType.BUY.value), msg.content["trade_type"])
        self.assertEqual("10.0", msg.content["price"])
        self.assertEqual("0.5", msg.content["amount"])
        self.assertEqual(1700000000.0, msg.timestamp)
        self.assertEqual(1700000000000000000, msg.content["update_id"])

    async def test_listen_for_trades_raises_cancel_exception(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, asyncio.Queue())

    async def test_listen_for_trades_logs_exception(self):
        bad_event = {"E": 1700000000000000000, "s": "unknownpair", "t": 999, "p": "1", "q": "1", "m": False}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [bad_event, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, asyncio.Queue())
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._diff_event(), asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertIs(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(110, msg.update_id)
        self.assertEqual(100, msg.first_update_id)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(9.0, msg.bids[0].price)
        self.assertEqual(1.0, msg.bids[0].amount)
        self.assertEqual(11.0, msg.asks[0].price)
        self.assertEqual(2.0, msg.asks[0].amount)

    async def test_listen_for_order_book_diffs_raises_cancel_exception(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, asyncio.Queue())

    async def test_listen_for_order_book_diffs_logs_exception(self):
        bad_event = {"e": CONSTANTS.WS_EVENT_DEPTH_UPDATE, "s": "unknownpair", "U": 1, "u": 2, "b": [], "a": []}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [bad_event, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, asyncio.Queue())
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error when processing public order book updates from exchange"))

    async def test_listen_for_order_book_snapshots_successful(self):
        event = self._diff_event()
        event["E"] = 1700000000000000000
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event, asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertIs(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(110, msg.update_id)
        self.assertEqual(1700000000.0, msg.timestamp)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual([["9", "1"]], msg.content["bids"])
        self.assertEqual([["11", "2"]], msg.content["asks"])

    async def test_listen_for_order_book_snapshots_raises_cancel_exception(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_order_book_snapshots_logs_exception_and_sleeps(self, sleep_mock):
        bad_event = {"e": CONSTANTS.WS_EVENT_DEPTH_UPDATE, "u": 110}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [bad_event]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue
        sleep_mock.side_effect = asyncio.CancelledError

        try:
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error when processing Gemini order book snapshots"))
        sleep_mock.assert_called_once_with(1.0)

    async def test_listen_for_order_book_snapshots_does_not_fall_back_to_rest(self):
        # The Gemini override must NEVER issue the base class's hourly REST snapshot
        # request: REST books carry no sequence id and would clobber the
        # sequence-bearing websocket book (update_id 0). The instance shadow below
        # makes the base class's timeout path reachable within the test if the
        # override is ever reverted.
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 0.1
        self.data_source._request_order_book_snapshots = AsyncMock()

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))

        await asyncio.sleep(0.3)
        self.data_source._request_order_book_snapshots.assert_not_called()

        event = self._diff_event()
        event["E"] = 1700000000000000000
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].put_nowait(event)

        msg: OrderBookMessage = await asyncio.wait_for(msg_queue.get(), timeout=1)

        self.data_source._request_order_book_snapshots.assert_not_called()
        self.assertIs(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(110, msg.update_id)

    # ------------------------------------------------------------------
    # Dynamic (un)subscribe
    # ------------------------------------------------------------------

    async def test_subscribe_to_trading_pair_no_ws(self):
        self.data_source._ws_assistant = None
        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertFalse(result)
        self.assertTrue(self._is_logged(
            "WARNING", f"Cannot subscribe to {self.trading_pair}: WebSocket not connected"))

    async def test_subscribe_to_trading_pair_successful(self):
        new_pair = "ETH-USD"
        exchange_symbol = "ethusd"
        self._set_symbol_map_with_extra_pair(new_pair, exchange_symbol)
        mock_ws = MagicMock()
        snapshot = self._diff_event()
        snapshot.update({"s": exchange_symbol, "U": 200, "u": 200})

        async def send(request):
            self.data_source._channel_originating_message({
                "id": request.payload["id"],
                "status": 200,
                "result": {},
            })
            self.data_source._channel_originating_message(snapshot)

        mock_ws.send = AsyncMock(side_effect=send)
        self.data_source._ws_assistant = mock_ws
        result = await self.data_source.subscribe_to_trading_pair(new_pair)
        self.assertTrue(result)
        mock_ws.send.assert_awaited_once()
        snapshot_message = await self.data_source._order_book_snapshot(new_pair)
        self.assertEqual(200, snapshot_message.update_id)

    async def test_subscribe_to_trading_pair_error_ack_does_not_mutate_state(self):
        new_pair = "ETH-USD"
        exchange_symbol = "ethusd"
        self._set_symbol_map_with_extra_pair(new_pair, exchange_symbol)
        mock_ws = MagicMock()

        async def send(request):
            self.data_source._channel_originating_message({
                "id": request.payload["id"],
                "status": 400,
                "error": {"msg": "bad stream"},
            })

        mock_ws.send = AsyncMock(side_effect=send)
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.subscribe_to_trading_pair(new_pair)

        self.assertFalse(result)
        self.assertNotIn(new_pair, self.data_source._trading_pairs)

    async def test_subscribe_to_trading_pair_times_out_without_initial_snapshot(self):
        new_pair = "ETH-USD"
        exchange_symbol = "ethusd"
        self._set_symbol_map_with_extra_pair(new_pair, exchange_symbol)
        mock_ws = MagicMock()

        async def send(request):
            self.data_source._channel_originating_message({
                "id": request.payload["id"],
                "status": 200,
                "result": {},
            })

        mock_ws.send = AsyncMock(side_effect=send)
        self.data_source._ws_assistant = mock_ws

        with patch.object(CONSTANTS, "WS_DYNAMIC_SNAPSHOT_TIMEOUT", 0.01):
            result = await self.data_source.subscribe_to_trading_pair(new_pair)

        self.assertFalse(result)
        self.assertNotIn(new_pair, self.data_source._trading_pairs)

    async def test_subscribe_to_trading_pair_handles_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("boom"))
        self.data_source._ws_assistant = mock_ws
        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertFalse(result)

    async def test_unsubscribe_from_trading_pair_no_ws(self):
        self.data_source._ws_assistant = None
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertFalse(result)
        self.assertTrue(self._is_logged(
            "WARNING", f"Cannot unsubscribe from {self.trading_pair}: WebSocket not connected"))

    async def test_unsubscribe_from_trading_pair_successful(self):
        mock_ws = MagicMock()

        async def send(request):
            self.data_source._channel_originating_message({
                "id": request.payload["id"],
                "status": 200,
                "result": {},
            })

        mock_ws.send = AsyncMock(side_effect=send)
        self.data_source._ws_assistant = mock_ws
        self.data_source.add_trading_pair(self.trading_pair)
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertTrue(result)
        mock_ws.send.assert_awaited_once()

    async def test_unsubscribe_from_trading_pair_error_ack_does_not_mutate_state(self):
        mock_ws = MagicMock()

        async def send(request):
            self.data_source._channel_originating_message({
                "id": request.payload["id"],
                "status": 400,
                "error": {"msg": "bad stream"},
            })

        mock_ws.send = AsyncMock(side_effect=send)
        self.data_source._ws_assistant = mock_ws
        self.data_source.add_trading_pair(self.trading_pair)

        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertFalse(result)
        self.assertIn(self.trading_pair, self.data_source._trading_pairs)

    async def test_unsubscribe_from_trading_pair_handles_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("boom"))
        self.data_source._ws_assistant = mock_ws
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertFalse(result)

    def test_get_next_subscribe_id_increments(self):
        first = GeminiAPIOrderBookDataSource._get_next_subscribe_id()
        second = GeminiAPIOrderBookDataSource._get_next_subscribe_id()
        self.assertEqual(first + 1, second)
