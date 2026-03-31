import asyncio
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


def _ensure_limit_order_stub():
    module_name = "hummingbot.core.data_type.limit_order"
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class LimitOrder:
        pass

    stub_module.LimitOrder = LimitOrder
    sys.modules[module_name] = stub_module


def _ensure_order_book_stub():
    module_name = "hummingbot.core.data_type.order_book"
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
            "data": {
                "s": "BTC",
                "l": [[{"p": "100", "a": "1"}], [{"p": "101", "a": "2"}]],
                "t": 1700000000000,
            },
        })

        result = await self.data_source._request_order_book_snapshot("BTC-USDC")

        self.assertEqual("BTC", result["s"])
        self.rest_assistant.execute_request.assert_awaited_once()
        call_kwargs = self.rest_assistant.execute_request.call_args.kwargs
        self.assertEqual({"symbol": "BTC"}, call_kwargs["params"])
        self.assertEqual({"X-Api-Key": "api-key"}, call_kwargs["headers"])
        self.assertEqual(self.constants.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, call_kwargs["throttler_limit_id"])

    async def test_order_book_snapshot_builds_snapshot_message(self):
        self.data_source._request_order_book_snapshot = AsyncMock(return_value={
            "s": "BTC",
            "l": [[{"p": "100", "a": "1.5"}], [{"p": "101", "a": "2.5"}]],
            "t": 1700000000000,
        })

        message = await self.data_source._order_book_snapshot("BTC-USDC")

        self.assertEqual("BTC-USDC", message.content["trading_pair"])
        self.assertEqual([("100", "1.5")], message.content["bids"])
        self.assertEqual([("101", "2.5")], message.content["asks"])
        self.assertEqual(1700000000.0, message.timestamp)

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
        self.assertEqual(
            {
                "method": "subscribe",
                "params": {"source": "book", "symbol": "BTC", "agg_level": 1},
            },
            payloads[0],
        )
        self.assertEqual(
            {
                "method": "subscribe",
                "params": {"source": "trades", "symbol": "BTC"},
            },
            payloads[1],
        )
        self.assertEqual(
            {
                "method": "subscribe",
                "params": {"source": "prices"},
            },
            payloads[2],
        )

    async def test_parse_order_book_snapshot_message_emits_snapshot(self):
        queue = asyncio.Queue()

        await self.data_source._parse_order_book_snapshot_message(
            {
                "data": {
                    "l": [[{"p": "100", "a": "1"}], [{"p": "101", "a": "2"}]],
                    "s": "BTC",
                    "t": 1700000000000,
                    "li": 123,
                }
            },
            queue,
        )

        message = queue.get_nowait()
        self.assertEqual("BTC-USDC", message.content["trading_pair"])
        self.assertEqual(123, message.update_id)
        self.assertEqual([("100", "1")], message.content["bids"])
        self.assertEqual([("101", "2")], message.content["asks"])

    async def test_parse_trade_message_emits_buy_and_sell_messages(self):
        queue = asyncio.Queue()

        await self.data_source._parse_trade_message(
            {
                "data": [
                    {"h": 1, "li": 11, "s": "BTC", "d": "open_long", "a": "0.1", "p": "100", "t": 1700000000000},
                    {"h": 2, "li": 12, "s": "BTC", "d": "open_short", "a": "0.2", "p": "99", "t": 1700000001000},
                ]
            },
            queue,
        )

        buy_message = queue.get_nowait()
        sell_message = queue.get_nowait()
        self.assertEqual(1.0, buy_message.content["trade_type"])
        self.assertEqual(2.0, sell_message.content["trade_type"])
        self.assertEqual("0.1", buy_message.content["amount"])
        self.assertEqual("99", sell_message.content["price"])

    async def test_parse_funding_info_message_updates_queue_and_cached_prices(self):
        queue = asyncio.Queue()

        await self.data_source._parse_funding_info_message(
            {
                "data": [
                    {"symbol": "BTC", "oracle": "100", "mark": "101", "funding": "0.0001", "timestamp": 1700000000000},
                    {"symbol": "ETH", "oracle": "200", "mark": "201", "funding": "0.0002", "timestamp": 1700000000000},
                ]
            },
            queue,
        )

        update = queue.get_nowait()
        self.assertEqual("BTC-USDC", update.trading_pair)
        self.assertEqual(Decimal("100"), update.index_price)
        self.assertEqual(Decimal("101"), update.mark_price)
        self.connector.set_LIGHTER_price.assert_called_once_with(
            "BTC-USDC",
            timestamp=1700000000.0,
            index_price=Decimal("100"),
            mark_price=Decimal("101"),
        )

    def test_channel_originating_message_routes_known_channels(self):
        self.assertEqual(
            self.data_source._snapshot_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "book", "data": {}}),
        )
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "trades", "data": {}}),
        )
        self.assertEqual(
            self.data_source._funding_info_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "prices", "data": {}}),
        )
        self.assertEqual("", self.data_source._channel_originating_message({"channel": "other"}))

    async def test_subscribe_and_unsubscribe_trading_pair_send_expected_messages(self):
        self.data_source._ws_assistant = self.ws_assistant

        subscribed = await self.data_source.subscribe_to_trading_pair("BTC-USDC")
        unsubscribed = await self.data_source.unsubscribe_from_trading_pair("BTC-USDC")

        self.assertTrue(subscribed)
        self.assertTrue(unsubscribed)
        payloads = [call.args[0].payload for call in self.ws_assistant.send.call_args_list]
        self.assertEqual("subscribe", payloads[0]["method"])
        self.assertEqual("unsubscribe", payloads[2]["method"])
        self.assertEqual("book", payloads[0]["params"]["source"])
        self.assertEqual("trades", payloads[1]["params"]["source"])
        self.assertEqual("book", payloads[2]["params"]["source"])
        self.assertEqual("trades", payloads[3]["params"]["source"])

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
