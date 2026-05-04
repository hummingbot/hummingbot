import asyncio
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


def _ensure_limit_order_stub():
    module_name = "hummingbot.core.data_type.limit_order"
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class LimitOrder:
        pass

    stub_module.LimitOrder = LimitOrder
    sys.modules[module_name] = stub_module


def _ensure_order_book_stub():
    module_name = "hummingbot.core.data_type.order_book"
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class OrderBook:
        pass

    stub_module.OrderBook = OrderBook
    sys.modules[module_name] = stub_module


class LighterPerpetualAPIOrderBookDataSourceTests(unittest.IsolatedAsyncioTestCase):

    data_source_cls = None
    constants = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_limit_order_stub()
        _ensure_order_book_stub()
        try:
            from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
            from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source import (
                LighterPerpetualAPIOrderBookDataSource,
            )

            cls.constants = CONSTANTS
            cls.data_source_cls = LighterPerpetualAPIOrderBookDataSource
        except ModuleNotFoundError:
            cls.data_source_cls = None

    def setUp(self):
        super().setUp()
        if self.data_source_cls is None:
            self.skipTest("Compiled hummingbot core modules are unavailable in this environment")

        self.connector = MagicMock()
        self.connector.rest_api_key = "api-key"
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._get_market_spec = AsyncMock(return_value=(1001, 4, 2, "BTC"))
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(
            side_effect=lambda symbol: {"BTC": "BTC-USDC", "ETH": "ETH-USDC"}[symbol]
        )
        self.connector.get_last_traded_prices = AsyncMock(return_value={"BTC-USDC": 101.2})
        self.connector.set_LIGHTER_price = MagicMock()

        self.rest_assistant = AsyncMock()
        self.ws_assistant = AsyncMock()
        self.api_factory = MagicMock()
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest_assistant)
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)

        self.data_source = self.data_source_cls(
            trading_pairs=["BTC-USDC"],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_request_order_book_snapshot_uses_expected_rest_request(self):
        self.rest_assistant.execute_request = AsyncMock(return_value={
            "success": True,
            "code": 200,
            "data": {
                "s": "BTC",
                "l": [[{"p": "100", "a": "1", "n": 1}], [{"p": "101", "a": "2", "n": 1}]],
                "li": 99,
                "t": 1700000000000,
            },
        })

        result = await self.data_source._request_order_book_snapshot("BTC-USDC")

        self.assertTrue(result["success"])
        self.rest_assistant.execute_request.assert_awaited_once()
        call_kwargs = self.rest_assistant.execute_request.call_args.kwargs
        self.assertEqual({"market_id": 1001, "limit": 250}, call_kwargs["params"])
        self.assertEqual({}, call_kwargs["headers"])
        self.assertEqual(self.constants.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, call_kwargs["throttler_limit_id"])

    async def test_order_book_snapshot_builds_snapshot_message(self):
        self.data_source._request_order_book_snapshot = AsyncMock(return_value={
            "success": True,
            "code": 200,
            "data": {
                "s": "BTC",
                "l": [[{"p": "100", "a": "1.5", "n": 1}], [{"p": "101", "a": "2.5", "n": 1}]],
                "li": 123,
                "t": 1700000000000,
            },
        })

        message = await self.data_source._order_book_snapshot("BTC-USDC")

        self.assertEqual("BTC-USDC", message.content["trading_pair"])
        self.assertEqual([("100", "1.5")], message.content["bids"])
        self.assertEqual([("101", "2.5")], message.content["asks"])
        self.assertEqual(123, message.content["update_id"])

    async def test_order_book_snapshot_builds_snapshot_message_from_legacy_payload(self):
        self.data_source._request_order_book_snapshot = AsyncMock(return_value={
            "code": 200,
            "bids": [{"price": "100", "remaining_base_amount": "1.5"}],
            "asks": [{"price": "101", "remaining_base_amount": "2.5"}],
        })

        message = await self.data_source._order_book_snapshot("BTC-USDC")

        self.assertEqual("BTC-USDC", message.content["trading_pair"])
        self.assertEqual([("100", "1.5")], message.content["bids"])
        self.assertEqual([("101", "2.5")], message.content["asks"])
        self.assertEqual(1, message.content["update_id"])

    async def test_get_funding_info_parses_price_entry(self):
        self.rest_assistant.execute_request = AsyncMock(return_value={
            "success": True,
            "data": [{
                "symbol": "BTC",
                "oracle": "100",
                "mark": "101",
                "funding": "0.0001",
            }],
        })

        funding_info = await self.data_source.get_funding_info("BTC-USDC")

        self.assertEqual("BTC-USDC", funding_info.trading_pair)
        self.assertEqual(Decimal("100"), funding_info.index_price)
        self.assertEqual(Decimal("101"), funding_info.mark_price)
        self.assertEqual(Decimal("0.0001"), funding_info.rate)

    async def test_get_funding_info_parses_order_book_stats_entry(self):
        self.rest_assistant.execute_request = AsyncMock(return_value={
            "code": 200,
            "total": 250,
            "order_book_stats": [{
                "symbol": "BTC",
                "oracle": "100",
                "mark": "101",
                "funding": "0.0001",
            }],
        })

        funding_info = await self.data_source.get_funding_info("BTC-USDC")

        self.assertEqual("BTC-USDC", funding_info.trading_pair)
        self.assertEqual(Decimal("100"), funding_info.index_price)
        self.assertEqual(Decimal("101"), funding_info.mark_price)
        self.assertEqual(Decimal("0.0001"), funding_info.rate)

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source.safe_ensure_future")
    async def test_connected_websocket_assistant_connects_and_starts_ping(self, safe_future_mock):
        safe_future_mock.side_effect = lambda coro: (coro.close(), MagicMock())[1]

        ws = await self.data_source._connected_websocket_assistant()

        self.assertIs(self.ws_assistant, ws)
        self.ws_assistant.connect.assert_awaited_once()
        connect_kwargs = self.ws_assistant.connect.call_args.kwargs
        self.assertEqual({"X-Api-Key": "api-key"}, connect_kwargs["ws_headers"])
        self.assertEqual(1, safe_future_mock.call_count)

    async def test_subscribe_channels_sends_book_trade_and_prices_requests(self):
        await self.data_source._subscribe_channels(self.ws_assistant)

        self.assertEqual(3, self.ws_assistant.send.await_count)
        payloads = [call.args[0].payload for call in self.ws_assistant.send.call_args_list]
        self.assertEqual({"type": "subscribe", "channel": "order_book/1001"}, payloads[0])
        self.assertEqual({"type": "subscribe", "channel": "trade/1001"}, payloads[1])
        self.assertEqual({"type": "subscribe", "channel": "market_stats/1001"}, payloads[2])
        # _market_id_to_trading_pair should be populated after subscription
        self.assertEqual("BTC-USDC", self.data_source._market_id_to_trading_pair[1001])

    async def test_parse_order_book_snapshot_message_emits_snapshot(self):
        queue = asyncio.Queue()
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"

        await self.data_source._parse_order_book_snapshot_message(
            {
                "channel": "order_book:1001",
                "type": "subscribed/order_book",
                "timestamp": 1700000000000,
                "order_book": {
                    "nonce": 123,
                    "bids": [{"price": "100", "size": "1"}],
                    "asks": [{"price": "101", "size": "2"}],
                },
            },
            queue,
        )

        message = queue.get_nowait()
        self.assertEqual("BTC-USDC", message.content["trading_pair"])
        self.assertEqual(123, message.update_id)
        self.assertEqual([("100", "1")], message.content["bids"])
        self.assertEqual([("101", "2")], message.content["asks"])

    async def test_parse_order_book_snapshot_message_supports_slash_channel(self):
        queue = asyncio.Queue()
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"

        await self.data_source._parse_order_book_snapshot_message(
            {
                "channel": "order_book/1001",
                "type": "subscribed/order_book",
                "timestamp": 1700000000000,
                "order_book": {
                    "nonce": 123,
                    "bids": [{"price": "100", "size": "1"}],
                    "asks": [{"price": "101", "size": "2"}],
                },
            },
            queue,
        )

        message = queue.get_nowait()
        self.assertEqual("BTC-USDC", message.content["trading_pair"])

    async def test_parse_trade_message_emits_buy_and_sell_messages(self):
        queue = asyncio.Queue()
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"

        await self.data_source._parse_trade_message(
            {
                "channel": "trade:1001",
                "timestamp": 1700000000000,
                "trades": [
                    {"price": "100", "size": "0.1", "is_maker_ask": True, "nonce": 1},
                    {"price": "99", "size": "0.2", "is_maker_ask": False, "nonce": 2},
                ],
            },
            queue,
        )

        buy_message = queue.get_nowait()
        sell_message = queue.get_nowait()
        self.assertEqual(1.0, buy_message.content["trade_type"])
        self.assertEqual(2.0, sell_message.content["trade_type"])
        self.assertEqual("0.1", buy_message.content["amount"])
        self.assertEqual("99", sell_message.content["price"])

    async def test_parse_trade_message_supports_slash_channel(self):
        queue = asyncio.Queue()
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"

        await self.data_source._parse_trade_message(
            {
                "channel": "trade/1001",
                "timestamp": 1700000000000,
                "trades": [
                    {"price": "100", "size": "0.1", "is_maker_ask": True, "nonce": 1},
                ],
            },
            queue,
        )

        message = queue.get_nowait()
        self.assertEqual("BTC-USDC", message.content["trading_pair"])

    async def test_parse_funding_info_message_updates_queue_and_cached_prices(self):
        queue = asyncio.Queue()
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"

        await self.data_source._parse_funding_info_message(
            {
                "channel": "market_stats:1001",
                "timestamp": 1700000000000,
                "market_stats": {
                    "symbol": "BTC",
                    "index_price": "100",
                    "mark_price": "101",
                    "current_funding_rate": "0.0001",
                    "funding_timestamp": 1700003600000,
                },
            },
            queue,
        )

        update = queue.get_nowait()
        self.assertEqual("BTC-USDC", update.trading_pair)
        self.assertEqual(Decimal("100"), update.index_price)
        self.assertEqual(Decimal("101"), update.mark_price)
        self.assertEqual(Decimal("0.0001"), update.rate)
        self.assertEqual(1700003600, update.next_funding_utc_timestamp)
        self.connector.set_LIGHTER_price.assert_called_once_with(
            "BTC-USDC",
            timestamp=1700000000.0,
            index_price=Decimal("100"),
            mark_price=Decimal("101"),
        )

    async def test_parse_funding_info_message_supports_slash_channel(self):
        queue = asyncio.Queue()
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"

        await self.data_source._parse_funding_info_message(
            {
                "channel": "market_stats/1001",
                "timestamp": 1700000000000,
                "market_stats": {
                    "symbol": "BTC",
                    "index_price": "100",
                    "mark_price": "101",
                    "current_funding_rate": "0.0001",
                    "funding_timestamp": 1700003600000,
                },
            },
            queue,
        )

        update = queue.get_nowait()
        self.assertEqual("BTC-USDC", update.trading_pair)

    def test_channel_originating_message_routes_known_channels(self):
        # Snapshot on initial subscription
        self.assertEqual(
            self.data_source._snapshot_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "order_book:1", "type": "subscribed/order_book"}),
        )
        # Diff on incremental update
        self.assertEqual(
            self.data_source._diff_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "order_book:1", "type": "update/order_book"}),
        )
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "trade:1", "type": "update/trade"}),
        )
        self.assertEqual(
            self.data_source._funding_info_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "market_stats:1", "type": "update/market_stats"}),
        )
        self.assertEqual(
            self.data_source._snapshot_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "order_book/1", "type": "subscribed/order_book"}),
        )
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "trade/1", "type": "update/trade"}),
        )
        self.assertEqual(
            self.data_source._funding_info_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "market_stats/1", "type": "update/market_stats"}),
        )
        self.assertEqual("", self.data_source._channel_originating_message({"channel": "other"}))
        self.assertEqual("", self.data_source._channel_originating_message({}))

    async def test_subscribe_and_unsubscribe_trading_pair_send_expected_messages(self):
        self.data_source._ws_assistant = self.ws_assistant

        subscribed = await self.data_source.subscribe_to_trading_pair("BTC-USDC")
        unsubscribed = await self.data_source.unsubscribe_from_trading_pair("BTC-USDC")

        self.assertTrue(subscribed)
        self.assertTrue(unsubscribed)
        payloads = [call.args[0].payload for call in self.ws_assistant.send.call_args_list]
        # 3 subscribe + 3 unsubscribe = 6 messages
        self.assertEqual(6, len(payloads))
        self.assertEqual({"type": "subscribe", "channel": "order_book/1001"}, payloads[0])
        self.assertEqual({"type": "subscribe", "channel": "trade/1001"}, payloads[1])
        self.assertEqual({"type": "subscribe", "channel": "market_stats/1001"}, payloads[2])
        self.assertEqual({"type": "unsubscribe", "channel": "order_book/1001"}, payloads[3])
        self.assertEqual({"type": "unsubscribe", "channel": "trade/1001"}, payloads[4])
        self.assertEqual({"type": "unsubscribe", "channel": "market_stats/1001"}, payloads[5])

    async def test_on_order_stream_interruption_cancels_ping_task(self):
        ping_task = MagicMock()
        self.data_source._ping_task = ping_task

        await self.data_source._on_order_stream_interruption()

        ping_task.cancel.assert_called_once()
        self.assertIsNone(self.data_source._ping_task)

    async def test_ping_loop_returns_when_ws_disconnects(self):
        self.ws_assistant.send.side_effect = RuntimeError("WS is not connected")

        with patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source.asyncio.sleep", new=AsyncMock()):
            result = await self.data_source._ping_loop(self.ws_assistant)

        self.assertIsNone(result)

    async def test_subscribe_channels_raises_on_send_error(self):
        self.ws_assistant.send.side_effect = Exception("boom")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(self.ws_assistant)

    async def test_get_new_order_book_successful(self):
        await self.test_order_book_snapshot_builds_snapshot_message()

    async def test_get_new_order_book_raises_exception(self):
        self.data_source._order_book_snapshot = AsyncMock(side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            await self.data_source.get_new_order_book("BTC-USDC")

    async def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs_and_funding_info(self):
        ws = MagicMock()
        ws.disconnect = AsyncMock()
        self.data_source._connected_websocket_assistant = AsyncMock(return_value=ws)
        self.data_source._subscribe_channels = AsyncMock()
        self.data_source._process_websocket_messages = AsyncMock(side_effect=asyncio.CancelledError())
        self.data_source._on_order_stream_interruption = AsyncMock()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    async def test_listen_for_subscriptions_raises_cancel_exception(self):
        self.data_source._connected_websocket_assistant = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    async def test_listen_for_subscriptions_logs_exception_details(self):
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.data_source._connected_websocket_assistant = AsyncMock(side_effect=[Exception("boom"), asyncio.CancelledError()])
        self.data_source._sleep = AsyncMock()
        self.data_source._on_order_stream_interruption = AsyncMock()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

        logger.exception.assert_called()

    async def test_subscribe_channels_raises_cancel_exception(self):
        self.connector._get_market_spec.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(self.ws_assistant)

    # ── listen_for_trades ──────────────────────────────────────────────────────

    async def test_listen_for_trades_successful(self):
        raw_msg = {"data": [{"h": 1, "li": 1, "s": "BTC", "d": "open_long", "a": "0.5", "p": "100", "t": 1700000000000}]}
        self.data_source._message_queue[self.data_source._trade_messages_queue_key].put_nowait(raw_msg)
        output = asyncio.Queue()

        async def _parse_trade_mock(raw_message, message_queue):
            message_queue.put_nowait(raw_message)
            raise asyncio.CancelledError()

        self.data_source._parse_trade_message = _parse_trade_mock

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=output)

        self.assertEqual(1, output.qsize())

    async def test_listen_for_trades_cancelled_when_listening(self):
        async def get_cancel():
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._trade_messages_queue_key].get = get_cancel

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=asyncio.Queue())

    async def test_listen_for_trades_logs_exception(self):
        raw_msg = {"data": []}
        self.data_source._message_queue[self.data_source._trade_messages_queue_key].put_nowait(raw_msg)

        call_count = 0

        async def _parse_trade_raises(raw_message, message_queue):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("parse error")
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._trade_messages_queue_key].put_nowait(raw_msg)
        self.data_source._parse_trade_message = _parse_trade_raises
        log_mock = MagicMock()
        self.data_source.logger = MagicMock(return_value=log_mock)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=asyncio.Queue())

        log_mock.exception.assert_called()

    # ── listen_for_order_book_diffs ────────────────────────────────────────────

    async def test_listen_for_order_book_diffs_successful(self):
        raw_msg = {"data": {"l": [[], []], "s": "BTC", "t": 1700000000000, "li": 1}}
        self.data_source._message_queue[self.data_source._diff_messages_queue_key].put_nowait(raw_msg)
        output = asyncio.Queue()

        async def _parse_diff_mock(raw_message, message_queue):
            message_queue.put_nowait(raw_message)
            raise asyncio.CancelledError()

        self.data_source._parse_order_book_diff_message = _parse_diff_mock

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=output)

        self.assertEqual(1, output.qsize())

    async def test_listen_for_order_book_diffs_cancelled(self):
        async def get_cancel():
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._diff_messages_queue_key].get = get_cancel

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=asyncio.Queue())

    async def test_listen_for_order_book_diffs_logs_exception(self):
        raw_msg = {}
        self.data_source._message_queue[self.data_source._diff_messages_queue_key].put_nowait(raw_msg)

        call_count = 0

        async def _parse_raises(raw_message, message_queue):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("diff parse error")
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._diff_messages_queue_key].put_nowait(raw_msg)
        self.data_source._parse_order_book_diff_message = _parse_raises
        log_mock = MagicMock()
        self.data_source.logger = MagicMock(return_value=log_mock)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=asyncio.Queue())

        log_mock.exception.assert_called()

    # ── listen_for_order_book_snapshots ───────────────────────────────────────

    async def test_listen_for_order_book_snapshots_successful(self):
        raw_msg = {"data": {"l": [[{"p": "100", "a": "1"}], [{"p": "101", "a": "2"}]], "s": "BTC", "t": 1700000000000, "li": 9}}
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].put_nowait(raw_msg)
        output = asyncio.Queue()

        parsed = []

        async def _parse_snap_mock(raw_message, message_queue):
            parsed.append(raw_message)
            raise asyncio.CancelledError()

        self.data_source._parse_order_book_snapshot_message = _parse_snap_mock

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(ev_loop=asyncio.get_event_loop(), output=output)

        self.assertEqual(1, len(parsed))

    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self):
        async def get_cancel(*args, **kwargs):
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].get = get_cancel

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(ev_loop=asyncio.get_event_loop(), output=asyncio.Queue())

    async def test_listen_for_order_book_snapshots_log_exception(self):
        raw_msg = {}
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].put_nowait(raw_msg)

        call_count = 0

        async def _parse_raises(raw_message, message_queue):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("snapshot parse error")
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].put_nowait(raw_msg)
        self.data_source._parse_order_book_snapshot_message = _parse_raises
        self.data_source._sleep = AsyncMock()
        log_mock = MagicMock()
        self.data_source.logger = MagicMock(return_value=log_mock)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(ev_loop=asyncio.get_event_loop(), output=asyncio.Queue())

        log_mock.exception.assert_called()

    # ── listen_for_funding_info ────────────────────────────────────────────────

    async def test_listen_for_funding_info_successful(self):
        raw_msg = {
            "data": [
                {"symbol": "BTC", "oracle": "100", "mark": "101", "funding": "0.0001", "timestamp": 1700000000000}
            ]
        }
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].put_nowait(raw_msg)
        output = asyncio.Queue()

        parsed = []
        original_parse = self.data_source._parse_funding_info_message

        async def _parse_funding_mock(raw_message, message_queue):
            await original_parse(raw_message, message_queue)
            parsed.append(raw_message)
            raise asyncio.CancelledError()

        self.data_source._parse_funding_info_message = _parse_funding_mock

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(output=output)

        self.assertEqual(1, len(parsed))

    async def test_listen_for_funding_info_cancelled_when_listening(self):
        async def get_cancel():
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].get = get_cancel

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(output=asyncio.Queue())

    async def test_listen_for_funding_info_logs_exception(self):
        raw_msg = {"data": []}
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].put_nowait(raw_msg)

        call_count = 0

        async def _parse_raises(raw_message, message_queue):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("funding info parse error")
            raise asyncio.CancelledError()

        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].put_nowait(raw_msg)
        self.data_source._parse_funding_info_message = _parse_raises
        log_mock = MagicMock()
        self.data_source.logger = MagicMock(return_value=log_mock)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(output=asyncio.Queue())

        log_mock.exception.assert_called()

    # ------------------------------------------------------------------
    # _market_id_from_channel
    # ------------------------------------------------------------------

    def test_market_id_from_channel_with_colon_separator(self):
        result = self.data_source_cls._market_id_from_channel("order_book:1001")
        self.assertEqual(1001, result)

    def test_market_id_from_channel_with_slash_separator(self):
        result = self.data_source_cls._market_id_from_channel("order_book/1001")
        self.assertEqual(1001, result)

    def test_market_id_from_channel_no_separator_returns_none(self):
        result = self.data_source_cls._market_id_from_channel("order_book")
        self.assertIsNone(result)

    def test_market_id_from_channel_non_int_tail_returns_none(self):
        result = self.data_source_cls._market_id_from_channel("order_book:abc")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # _parse_order_book_snapshot_message
    # ------------------------------------------------------------------

    async def test_parse_ob_snapshot_unknown_market_id_returns_early(self):
        q = asyncio.Queue()
        await self.data_source._parse_order_book_snapshot_message(
            {"channel": "order_book:9999", "order_book": {"bids": [], "asks": []}},
            q,
        )
        self.assertTrue(q.empty())

    async def test_parse_ob_snapshot_no_channel_returns_early(self):
        q = asyncio.Queue()
        await self.data_source._parse_order_book_snapshot_message({"order_book": {}}, q)
        self.assertTrue(q.empty())

    async def test_parse_ob_snapshot_puts_message_when_known(self):
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"
        q = asyncio.Queue()
        await self.data_source._parse_order_book_snapshot_message({
            "channel": "order_book:1001",
            "order_book": {"nonce": 42, "bids": [{"price": "100", "size": "1"}], "asks": []},
            "timestamp": 1700000000000,
        }, q)
        self.assertFalse(q.empty())
        msg = q.get_nowait()
        self.assertEqual("BTC-USDC", msg.content["trading_pair"])

    # ------------------------------------------------------------------
    # _parse_order_book_diff_message
    # ------------------------------------------------------------------

    async def test_parse_ob_diff_unknown_market_returns_early(self):
        q = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message(
            {"channel": "order_book:9999", "order_book": {}},
            q,
        )
        self.assertTrue(q.empty())

    async def test_parse_ob_diff_puts_diff_when_known(self):
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"
        q = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message({
            "channel": "order_book:1001",
            "order_book": {"nonce": 7, "begin_nonce": 6, "bids": [], "asks": [{"price": "101", "size": "2"}]},
            "timestamp": 1700000000000,
        }, q)
        self.assertFalse(q.empty())
        msg = q.get_nowait()
        self.assertEqual("BTC-USDC", msg.content["trading_pair"])

    # ------------------------------------------------------------------
    # subscribe_to_trading_pair / unsubscribe_from_trading_pair
    # ------------------------------------------------------------------

    async def test_subscribe_to_trading_pair_returns_false_when_no_ws(self):
        self.data_source._ws_assistant = None
        result = await self.data_source.subscribe_to_trading_pair("BTC-USDC")
        self.assertFalse(result)

    async def test_subscribe_to_trading_pair_sends_subscriptions(self):
        ws = AsyncMock()
        self.data_source._ws_assistant = ws
        result = await self.data_source.subscribe_to_trading_pair("BTC-USDC")
        self.assertTrue(result)
        self.assertEqual(3, ws.send.await_count)
        self.assertEqual("BTC-USDC", self.data_source._market_id_to_trading_pair[1001])

    async def test_unsubscribe_from_trading_pair_returns_false_when_no_ws(self):
        self.data_source._ws_assistant = None
        result = await self.data_source.unsubscribe_from_trading_pair("BTC-USDC")
        self.assertFalse(result)

    async def test_unsubscribe_from_trading_pair_sends_unsubscriptions(self):
        ws = AsyncMock()
        self.data_source._ws_assistant = ws
        self.data_source._market_id_to_trading_pair[1001] = "BTC-USDC"
        result = await self.data_source.unsubscribe_from_trading_pair("BTC-USDC")
        self.assertTrue(result)
        self.assertEqual(3, ws.send.await_count)
        self.assertNotIn(1001, self.data_source._market_id_to_trading_pair)

    # ------------------------------------------------------------------
    # _ping_loop
    # ------------------------------------------------------------------

    async def test_ping_loop_cancels_on_cancelled_error(self):
        ws = AsyncMock()
        ws.send = AsyncMock(side_effect=asyncio.CancelledError())

        with patch("asyncio.sleep", AsyncMock(return_value=None)):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source._ping_loop(ws)

    async def test_ping_loop_returns_on_ws_not_connected(self):
        ws = AsyncMock()
        ws.send = AsyncMock(side_effect=RuntimeError("WS is not connected"))

        with patch("asyncio.sleep", AsyncMock(return_value=None)):
            # Should return without raising
            await self.data_source._ping_loop(ws)
