import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_api_order_book_data_source import XtAPIOrderBookDataSource
from hummingbot.connector.exchange.xt.xt_exchange import XtExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker


class XtAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.pairs = ["COINALPHA-HBOT", "ETH-USDT"]
        self.symbols = ["coinalpha_hbot", "eth_usdt"]
        self.connector = XtExchange(xt_api_key="", xt_api_secret="", trading_pairs=self.pairs, trading_required=False)
        self.connector._time_synchronizer.add_time_offset_ms_sample(0)
        self.connector._set_trading_pair_symbol_map(bidict(zip(self.symbols, self.pairs)))
        self.source = XtAPIOrderBookDataSource(list(self.pairs), self.connector, self.connector._web_assistants_factory)
        self.network = NetworkMockingAssistant()
        await self.network.async_init()
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await super().asyncTearDown()

    def snapshot(self, sequence=120):
        return {"rc": 0, "mc": "SUCCESS", "result": {"lastUpdateId": sequence, "bids": [["4", "10"]], "asks": [["5", "20"]]}}

    def diff(self, first=121, last=123, symbol="coinalpha_hbot"):
        return {"topic": "depth_update", "data": {"s": symbol, "fi": first, "i": last, "b": [["4", "0"]], "a": [["5", "3"]]}}

    def trade(self, symbol="coinalpha_hbot"):
        return {"topic": "trade", "data": {"s": symbol, "i": "789", "t": 1640001112223, "p": "4", "q": "10", "b": True}}

    def mock_snapshot(self, mocked_api, sequence=120):
        url = web_utils.public_rest_url(CONSTANTS.DEPTH_PATH_URL)
        mocked_api.get(re.compile(f"^{re.escape(url)}"), payload=self.snapshot(sequence))

    @aioresponses()
    async def test_get_new_order_book_uses_symbol_and_depth_limit(self, mocked_api):
        self.mock_snapshot(mocked_api)
        book = await self.source.get_new_order_book(self.pairs[0])
        self.assertEqual(120, book.snapshot_uid)
        self.assertEqual(4, list(book.bid_entries())[0].price)
        request_url = next(iter(mocked_api.requests))[1]
        self.assertEqual({"symbol": self.symbols[0], "limit": "500"}, dict(request_url.query))

    @aioresponses()
    async def test_snapshot_api_error_is_raised(self, mocked_api):
        url = web_utils.public_rest_url(CONSTANTS.DEPTH_PATH_URL)
        mocked_api.get(re.compile(f"^{re.escape(url)}"), payload={"rc": 1, "mc": "INVALID_SYMBOL", "result": None})
        with self.assertRaises(IOError):
            await self.source.get_new_order_book(self.pairs[0])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_native_subscription_loop_routes_multiple_pairs_and_filters_control_frames(self, connect):
        ws = self.network.create_websocket_mock()
        ws.closed = False
        connect.return_value = ws
        frames = ["pong", {"code": 0, "id": "1"}, {"topic": "unknown", "data": {}}, self.trade(), self.diff(symbol=self.symbols[1])]
        for frame in frames:
            self.network.add_websocket_aiohttp_message(ws, frame if isinstance(frame, str) else json.dumps(frame))
        task = asyncio.create_task(self.source.listen_for_subscriptions())
        self.tasks.append(task)
        trade = await asyncio.wait_for(self.source._message_queue[CONSTANTS.WS_PUBLIC_TRADE_TOPIC].get(), 1)
        diff = await asyncio.wait_for(self.source._message_queue[CONSTANTS.WS_PUBLIC_DEPTH_TOPIC].get(), 1)
        self.assertEqual(self.trade(), trade)
        self.assertEqual(self.symbols[1], diff["data"]["s"])
        sent = self.network.json_messages_sent_through_websocket(ws)
        self.assertEqual(2, len(sent))
        for index, symbol in enumerate(self.symbols):
            self.assertEqual({"method": "subscribe", "params": [f"trade@{symbol}", f"depth_update@{symbol}"], "id": str(index + 1)}, sent[index])
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertIsNone(self.source._ws_assistant)
        ws.close.assert_awaited()

    async def test_parse_trade_uses_exchange_symbol_map_for_each_pair(self):
        output = asyncio.Queue()
        for symbol, pair in zip(self.symbols, self.pairs):
            await self.source._parse_trade_message(self.trade(symbol), output)
            self.assertEqual(pair, output.get_nowait().trading_pair)

    @aioresponses()
    async def test_first_diff_emits_snapshot_before_covering_range(self, mocked_api):
        self.mock_snapshot(mocked_api, 122)
        output = asyncio.Queue()
        await self.source._parse_order_book_diff_message(self.diff(), output)
        snapshot, diff = output.get_nowait(), output.get_nowait()
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot.type)
        self.assertEqual(122, snapshot.update_id)
        self.assertEqual(OrderBookMessageType.DIFF, diff.type)
        self.assertEqual((121, 123), (diff.first_update_id, diff.update_id))

    async def test_stale_duplicate_diff_is_discarded(self):
        self.source._last_diff_update_ids[self.pairs[0]] = 123
        output = asyncio.Queue()
        await self.source._parse_order_book_diff_message(self.diff(), output)
        self.assertTrue(output.empty())

    async def test_contiguous_diffs_do_not_request_snapshot_and_pairs_are_independent(self):
        self.source._last_diff_update_ids.update({self.pairs[0]: 120, self.pairs[1]: 220})
        output = asyncio.Queue()
        await self.source._parse_order_book_diff_message(self.diff(), output)
        await self.source._parse_order_book_diff_message(self.diff(221, 225, self.symbols[1]), output)
        self.assertEqual([(self.pairs[0], 123), (self.pairs[1], 225)], [(message.trading_pair, message.update_id) for message in [output.get_nowait(), output.get_nowait()]])

    @aioresponses()
    async def test_gap_recovers_with_snapshot_in_same_output_queue(self, mocked_api):
        self.source._last_diff_update_ids[self.pairs[0]] = 100
        self.mock_snapshot(mocked_api, 122)
        output = asyncio.Queue()
        await self.source._parse_order_book_diff_message(self.diff(), output)
        self.assertEqual([122, 123], [output.get_nowait().update_id, output.get_nowait().update_id])

    @aioresponses()
    async def test_gap_snapshot_ahead_of_diff_drops_stale_diff(self, mocked_api):
        self.source._last_diff_update_ids[self.pairs[0]] = 100
        self.mock_snapshot(mocked_api, 130)
        output = asyncio.Queue()
        await self.source._parse_order_book_diff_message(self.diff(), output)
        self.assertEqual(130, output.get_nowait().update_id)
        self.assertTrue(output.empty())

    @aioresponses()
    async def test_gap_snapshot_behind_last_emission_is_rejected(self, mocked_api):
        self.source._last_diff_update_ids[self.pairs[0]] = 110
        self.mock_snapshot(mocked_api, 105)
        output = asyncio.Queue()
        with self.assertRaises(IOError):
            await self.source._parse_order_book_diff_message(self.diff(), output)
        self.assertTrue(output.empty())

    @aioresponses()
    async def test_snapshot_not_covering_gap_does_not_emit_diff(self, mocked_api):
        self.source._last_diff_update_ids[self.pairs[0]] = 100
        self.mock_snapshot(mocked_api, 110)
        output = asyncio.Queue()
        with self.assertRaises(IOError):
            await self.source._parse_order_book_diff_message(self.diff(), output)
        self.assertEqual(110, output.get_nowait().update_id)
        self.assertTrue(output.empty())

    @aioresponses()
    async def test_native_tracker_processes_recovery_snapshot_then_diff(self, mocked_api):
        self.mock_snapshot(mocked_api, 122)
        tracker = OrderBookTracker(self.source, [self.pairs[0]])
        processed = asyncio.Event()

        class ObservedOrderBook(OrderBook):
            def apply_diffs(self, bids, asks, update_id):
                super().apply_diffs(bids, asks, update_id)
                processed.set()

        book = ObservedOrderBook()
        book.apply_snapshot([], [], 100)
        tracker._order_books[self.pairs[0]] = book
        tracker._tracking_message_queues[self.pairs[0]] = asyncio.Queue()
        self.source._last_diff_update_ids[self.pairs[0]] = 100
        await self.source._parse_order_book_diff_message(self.diff(), tracker._order_book_diff_stream)
        router = asyncio.create_task(tracker._order_book_diff_router())
        tracking = asyncio.create_task(tracker._track_single_book(self.pairs[0]))
        self.tasks.extend([router, tracking])
        await asyncio.wait_for(processed.wait(), 1)
        self.assertEqual(122, book.snapshot_uid)
        self.assertEqual([], list(book.bid_entries()))
        self.assertEqual(3, list(book.ask_entries())[0].amount)

    async def test_late_hourly_snapshot_cannot_undo_native_gap_recovery(self):
        pair = self.pairs[0]
        self.source._trading_pairs = [pair]
        self.source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 0
        self.source._last_diff_update_ids[pair] = 100
        hourly_started, release_hourly, hourly_enqueued = (asyncio.Event() for _ in range(3))
        repaired, next_diff_applied, snapshot_router_started = (asyncio.Event() for _ in range(3))

        async def snapshot_response(trading_pair):
            if not hourly_started.is_set():
                hourly_started.set()
                await release_hourly.wait()
                return self.snapshot(110)
            response = self.snapshot(122)
            response["result"]["bids"] = [["4", "7"]]
            return response

        periodic_request = self.source._request_order_book_snapshots

        async def fetch_one_hourly_snapshot(output):
            await periodic_request(output)
            hourly_enqueued.set()
            await asyncio.Event().wait()

        class ObservedOrderBook(OrderBook):
            def apply_diffs(self, bids, asks, update_id):
                super().apply_diffs(bids, asks, update_id)
                if update_id == 123:
                    repaired.set()
                elif update_id == 124:
                    next_diff_applied.set()

        book = ObservedOrderBook()
        book.apply_snapshot([OrderBookRow(4, 10, 100)], [OrderBookRow(5, 20, 100)], 100)
        tracker = OrderBookTracker(self.source, [pair])
        tracker._order_books[pair] = book
        tracker._tracking_message_queues[pair] = asyncio.Queue()
        tracker._order_books_initialized.set()

        async def route_snapshots():
            snapshot_router_started.set()
            await tracker._order_book_snapshot_router()

        with patch.object(self.source, "_request_order_book_snapshot", side_effect=snapshot_response), patch.object(
            self.source, "_request_order_book_snapshots", side_effect=fetch_one_hourly_snapshot
        ):
            self.tasks.extend(asyncio.create_task(coro) for coro in [
                self.source.listen_for_order_book_snapshots(asyncio.get_running_loop(), tracker._order_book_snapshot_stream),
                self.source.listen_for_order_book_diffs(asyncio.get_running_loop(), tracker._order_book_diff_stream),
                tracker._order_book_diff_router(),
                tracker._track_single_book(pair),
            ])
            await asyncio.wait_for(hourly_started.wait(), 1)
            recovery_diff = self.diff()
            recovery_diff["data"]["b"] = []
            self.source._message_queue[self.source._diff_messages_queue_key].put_nowait(recovery_diff)
            await asyncio.wait_for(repaired.wait(), 1)
            self.assertEqual((122, 7, 3), (book.snapshot_uid, list(book.bid_entries())[0].amount, list(book.ask_entries())[0].amount))
            release_hourly.set()
            await asyncio.wait_for(hourly_enqueued.wait(), 1)
            # Starting this router after the late request queues any old-path
            # snapshot ahead of the next diff, without depending on wall time.
            self.tasks.append(asyncio.create_task(route_snapshots()))
            await asyncio.wait_for(snapshot_router_started.wait(), 1)
            next_diff = self.diff(124, 124)
            next_diff["data"].update({"b": [], "a": [["5", "4"]]})
            self.source._message_queue[self.source._diff_messages_queue_key].put_nowait(next_diff)
            await asyncio.wait_for(next_diff_applied.wait(), 1)
            self.assertEqual((122, 124, 7, 4), (
                book.snapshot_uid, book.last_diff_uid,
                list(book.bid_entries())[0].amount, list(book.ask_entries())[0].amount,
            ))
            self.assertEqual(124, self.source._last_diff_update_ids[pair])

    @aioresponses()
    async def test_periodic_snapshots_share_diff_output_and_update_each_pair_cursor(self, mocked_api):
        self.source._last_diff_update_ids[self.pairs[0]] = 100
        self.mock_snapshot(mocked_api, 120)
        self.mock_snapshot(mocked_api, 520)
        snapshot_output, diff_output = asyncio.Queue(), asyncio.Queue()
        await self.source._request_order_book_snapshots(snapshot_output)
        self.assertTrue(snapshot_output.empty())
        depth_input = self.source._message_queue[self.source._diff_messages_queue_key]
        await self.source._parse_order_book_diff_message(depth_input.get_nowait(), diff_output)
        await self.source._parse_order_book_diff_message(depth_input.get_nowait(), diff_output)
        self.assertEqual({self.pairs[0]: 120, self.pairs[1]: 520}, self.source._last_diff_update_ids)
        await self.source._parse_order_book_diff_message(self.diff(), diff_output)
        await self.source._parse_order_book_diff_message(self.diff(521, 525, self.symbols[1]), diff_output)
        self.assertEqual([
            (self.pairs[0], OrderBookMessageType.SNAPSHOT, 120),
            (self.pairs[1], OrderBookMessageType.SNAPSHOT, 520),
            (self.pairs[0], OrderBookMessageType.DIFF, 123),
            (self.pairs[1], OrderBookMessageType.DIFF, 525),
        ], [(message.trading_pair, message.type, message.update_id) for message in [diff_output.get_nowait() for _ in range(4)]])

    async def test_native_tracker_applies_periodic_snapshots_and_contiguous_diffs_per_pair(self):
        tracker = OrderBookTracker(self.source, self.pairs)
        snapshots_applied = {pair: asyncio.Event() for pair in self.pairs}
        diffs_applied = {pair: asyncio.Event() for pair in self.pairs}
        source_snapshots = dict(zip(self.pairs, [120, 520]))

        class ObservedOrderBook(OrderBook):
            def __init__(self, pair):
                super().__init__()
                self.pair = pair

            def restore_from_snapshot_and_diffs(self, message, diffs):
                super().restore_from_snapshot_and_diffs(message, diffs)
                snapshots_applied[self.pair].set()

            def apply_diffs(self, bids, asks, update_id):
                super().apply_diffs(bids, asks, update_id)
                diffs_applied[self.pair].set()

        for pair in self.pairs:
            book = ObservedOrderBook(pair)
            book.apply_snapshot([], [], 100)
            tracker._order_books[pair] = book
            tracker._tracking_message_queues[pair] = asyncio.Queue()
        tracker._order_books_initialized.set()
        self.tasks.extend(asyncio.create_task(coro) for coro in [
            self.source.listen_for_order_book_diffs(asyncio.get_running_loop(), tracker._order_book_diff_stream),
            tracker._order_book_diff_router(),
            tracker._order_book_snapshot_router(),
            *(tracker._track_single_book(pair) for pair in self.pairs),
        ])

        async def snapshot_response(trading_pair):
            return self.snapshot(source_snapshots[trading_pair])

        with patch.object(self.source, "_request_order_book_snapshot", side_effect=snapshot_response) as request:
            await self.source._request_order_book_snapshots(tracker._order_book_snapshot_stream)
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in snapshots_applied.values())), 1)
            self.assertEqual(source_snapshots, self.source._last_diff_update_ids)
            self.source._message_queue[self.source._diff_messages_queue_key].put_nowait(self.diff())
            await asyncio.wait_for(diffs_applied[self.pairs[0]].wait(), 1)
            self.assertEqual([], list(tracker._order_books[self.pairs[0]].bid_entries()))
            self.assertEqual(3, list(tracker._order_books[self.pairs[0]].ask_entries())[0].amount)
            other_book = tracker._order_books[self.pairs[1]]
            self.assertEqual((520, 10, 20), (
                other_book.snapshot_uid, list(other_book.bid_entries())[0].amount, list(other_book.ask_entries())[0].amount,
            ))
            self.assertFalse(diffs_applied[self.pairs[1]].is_set())
            self.source._message_queue[self.source._diff_messages_queue_key].put_nowait(self.diff(521, 525, self.symbols[1]))
            await asyncio.wait_for(diffs_applied[self.pairs[1]].wait(), 1)
            self.assertEqual((520, 525, 3), (other_book.snapshot_uid, other_book.last_diff_uid, list(other_book.ask_entries())[0].amount))
            self.assertEqual({self.pairs[0]: 123, self.pairs[1]: 525}, self.source._last_diff_update_ids)
            self.assertEqual(2, request.await_count)

    async def test_periodic_snapshot_freshness_is_checked_when_diff_consumer_receives_it(self):
        output = asyncio.Queue()
        self.source._trading_pairs = [self.pairs[0]]
        with patch.object(self.source, "_request_order_book_snapshot", return_value=self.snapshot(120)):
            await self.source._request_order_book_snapshots(asyncio.Queue())
        self.source._last_diff_update_ids.update({self.pairs[0]: 123, self.pairs[1]: 500})
        queued_snapshot = self.source._message_queue[self.source._diff_messages_queue_key].get_nowait()
        await self.source._parse_order_book_diff_message(queued_snapshot, output)
        self.assertTrue(output.empty())
        self.assertEqual({self.pairs[0]: 123, self.pairs[1]: 500}, self.source._last_diff_update_ids)

    async def test_periodic_snapshot_request_preserves_native_retry_and_cancellation(self):
        self.source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 0
        with patch.object(self.source, "_request_order_book_snapshot", side_effect=IOError("snapshot failed")) as request, patch.object(
            self.source, "_sleep", side_effect=asyncio.CancelledError
        ) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await self.source.listen_for_order_book_snapshots(asyncio.get_running_loop(), asyncio.Queue())
        request.assert_awaited_once()
        sleep.assert_awaited_once_with(1.0)
        with patch.object(self.source, "_request_order_book_snapshot", side_effect=asyncio.CancelledError), patch.object(
            self.source, "_sleep"
        ) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await self.source.listen_for_order_book_snapshots(asyncio.get_running_loop(), asyncio.Queue())
        sleep.assert_not_awaited()

    async def test_dynamic_subscriptions_update_trading_pairs(self):
        self.source._ws_assistant = AsyncMock()
        self.source.remove_trading_pair(self.pairs[1])
        self.assertTrue(await self.source.subscribe_to_trading_pair(self.pairs[1]))
        self.assertIn(self.pairs[1], self.source._trading_pairs)
        self.assertTrue(await self.source.unsubscribe_from_trading_pair(self.pairs[1]))
        self.assertNotIn(self.pairs[1], self.source._trading_pairs)
        self.assertEqual("unsubscribe", self.source._ws_assistant.send.call_args.args[0].payload["method"])

    async def test_subscription_failure_and_cancellation_propagate(self):
        ws = AsyncMock()
        ws.send.side_effect = IOError("send failed")
        with self.assertRaises(IOError):
            await self.source._subscribe_channels(ws)
        ws.send.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.source._subscribe_channels(ws)

    async def test_subscription_error_frame_raises(self):
        with self.assertRaises(IOError):
            await self.source._process_message_for_unknown_channel({"code": 1, "msg": "invalid topic"}, AsyncMock())

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._process_websocket_messages", new_callable=AsyncMock)
    async def test_heartbeat_sends_plain_text_ping_and_propagates_send_failure(self, process):
        process.side_effect = asyncio.TimeoutError
        ws = AsyncMock()
        ws.send.side_effect = IOError("send failed")
        with self.assertRaises(IOError):
            await self.source._process_websocket_messages(ws)
        self.assertEqual("ping", ws.send.call_args.args[0].payload)

    async def test_native_loop_retries_and_disconnects_after_processing_error(self):
        ws = AsyncMock()
        with patch.object(self.source, "_connected_websocket_assistant", return_value=ws), patch.object(self.source, "_subscribe_channels"), patch.object(self.source, "_process_websocket_messages", side_effect=IOError("bad frame")), patch.object(self.source, "_sleep", side_effect=asyncio.CancelledError) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await self.source.listen_for_subscriptions()
        sleep.assert_awaited_once()
        ws.disconnect.assert_awaited_once()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._process_websocket_messages", new_callable=AsyncMock)
    async def test_processing_returns_when_native_stream_ends(self, process):
        await asyncio.wait_for(self.source._process_websocket_messages(AsyncMock()), 1)
        process.assert_awaited_once()
