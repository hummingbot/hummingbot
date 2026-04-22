import asyncio
import sys
import types
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

if "hummingbot.core.data_type.order_book" not in sys.modules:
    try:
        import hummingbot.core.data_type.order_book  # noqa: F401
    except Exception:
        fake_order_book = types.ModuleType("hummingbot.core.data_type.order_book")

        class OrderBook:
            def apply_snapshot(self, bids, asks, update_id):
                _ = bids
                _ = asks
                _ = update_id

        fake_order_book.OrderBook = OrderBook
        sys.modules["hummingbot.core.data_type.order_book"] = fake_order_book

from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource


class LighterAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.connector = MagicMock()
        self.connector.rest_api_key = ""
        self.connector.get_last_traded_prices = AsyncMock(return_value={"ETH-USDC": 2000.0})
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="ETH/USDC")
        self.connector._get_market_spec = AsyncMock(return_value=(2048, 4, 2, "ETH/USDC"))

        self.data_source = LighterAPIOrderBookDataSource(
            trading_pairs=["ETH-USDC"],
            connector=self.connector,
            api_factory=MagicMock(),
        )
        self.data_source._market_id_to_trading_pair[2048] = "ETH-USDC"

    async def test_get_last_traded_prices_delegates_to_connector(self):
        prices = await self.data_source.get_last_traded_prices(["ETH-USDC"])

        self.assertEqual({"ETH-USDC": 2000.0}, prices)
        self.connector.get_last_traded_prices.assert_awaited_once_with(trading_pairs=["ETH-USDC"])

    def test_get_headers_includes_api_key_when_present(self):
        self.connector.rest_api_key = "api-key"

        self.assertEqual({"X-Api-Key": "api-key"}, self.data_source._get_headers())

    async def test_request_order_book_snapshot_uses_rest_assistant(self):
        rest_assistant = MagicMock()
        rest_assistant.execute_request = AsyncMock(return_value={"success": True, "data": {"t": 1, "l": [[], []]}})
        self.data_source._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)
        self.connector.rest_api_key = "api-key"

        snapshot = await self.data_source._request_order_book_snapshot("ETH-USDC")

        self.assertEqual({"success": True, "data": {"t": 1, "l": [[], []]}}, snapshot)
        rest_assistant.execute_request.assert_awaited_once()
        self.assertEqual({}, rest_assistant.execute_request.call_args.kwargs["headers"])

    async def test_request_order_book_snapshot_accepts_code_200_without_success_flag(self):
        rest_assistant = MagicMock()
        rest_assistant.execute_request = AsyncMock(return_value={"code": 200, "data": {"t": 2, "l": [[], []]}})
        self.data_source._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        snapshot = await self.data_source._request_order_book_snapshot("ETH-USDC")

        self.assertEqual({"code": 200, "data": {"t": 2, "l": [[], []]}}, snapshot)

    async def test_request_order_book_snapshot_raises_on_unsuccessful_response(self):
        rest_assistant = MagicMock()
        rest_assistant.execute_request = AsyncMock(return_value={"success": False, "error": "boom"})
        self.data_source._api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        with self.assertRaises(ValueError):
            await self.data_source._request_order_book_snapshot("ETH-USDC")

    async def test_order_book_snapshot_formats_snapshot_message(self):
        self.data_source._request_order_book_snapshot = AsyncMock(return_value={
            "bids": [
                {"price": "1999", "remaining_base_amount": "1.2"},
            ],
            "asks": [
                {"price": "2001", "remaining_base_amount": "1.4"},
            ],
        })

        message = await self.data_source._order_book_snapshot("ETH-USDC")

        self.assertEqual("ETH-USDC", message.content["trading_pair"])
        self.assertEqual([(1999.0, 1.2)], [(float(p), float(a)) for p, a in message.content["bids"]])
        self.assertEqual([(2001.0, 1.4)], [(float(p), float(a)) for p, a in message.content["asks"]])

    async def test_connected_websocket_assistant_connects_with_headers(self):
        ws = MagicMock()
        ws.connect = AsyncMock()
        self.connector.rest_api_key = "api-key"
        self.data_source._api_factory.get_ws_assistant = AsyncMock(return_value=ws)

        connected_ws = await self.data_source._connected_websocket_assistant()

        self.assertIs(ws, connected_ws)
        ws.connect.assert_awaited_once_with(
            ws_url="wss://mainnet.zklighter.elliot.ai/stream",
            ws_headers={"X-Api-Key": "api-key"},
        )

    async def test_subscribe_channels_subscribes_order_book_and_trade(self):
        ws = MagicMock()
        ws.send = AsyncMock()

        await self.data_source._subscribe_channels(ws)

        self.assertEqual(2, ws.send.await_count)
        sent_payloads = [call.args[0].payload for call in ws.send.await_args_list]
        self.assertEqual({"type": "subscribe", "channel": "order_book/2048"}, sent_payloads[0])
        self.assertEqual({"type": "subscribe", "channel": "trade/2048"}, sent_payloads[1])

    async def test_subscribe_to_trading_pair_returns_false_without_websocket(self):
        self.data_source._ws_assistant = None

        subscribed = await self.data_source.subscribe_to_trading_pair("ETH-USDC")

        self.assertFalse(subscribed)

    async def test_subscribe_to_trading_pair_updates_market_map_and_sends_messages(self):
        ws = MagicMock()
        ws.send = AsyncMock()
        self.data_source._ws_assistant = ws

        subscribed = await self.data_source.subscribe_to_trading_pair("ETH-USDC")

        self.assertTrue(subscribed)
        self.assertEqual("ETH-USDC", self.data_source._market_id_to_trading_pair[2048])
        self.assertEqual(2, ws.send.await_count)

    async def test_unsubscribe_from_trading_pair_returns_false_without_websocket(self):
        self.data_source._ws_assistant = None

        unsubscribed = await self.data_source.unsubscribe_from_trading_pair("ETH-USDC")

        self.assertFalse(unsubscribed)

    async def test_unsubscribe_from_trading_pair_removes_market_map_and_sends_messages(self):
        ws = MagicMock()
        ws.send = AsyncMock()
        self.data_source._ws_assistant = ws

        unsubscribed = await self.data_source.unsubscribe_from_trading_pair("ETH-USDC")

        self.assertTrue(unsubscribed)
        self.assertNotIn(2048, self.data_source._market_id_to_trading_pair)
        self.assertEqual(2, ws.send.await_count)

    async def test_parse_order_book_snapshot_message(self):
        q = asyncio.Queue()
        raw_message = {
            "channel": "order_book:2048",
            "type": "subscribed/order_book",
            "timestamp": 1710000000000,
            "order_book": {
                "nonce": 12,
                "bids": [{"price": "1999", "size": "1.2"}],
                "asks": [{"price": "2001", "size": "1.4"}],
            },
        }

        await self.data_source._parse_order_book_snapshot_message(raw_message, q)
        msg = q.get_nowait()

        self.assertEqual("ETH-USDC", msg.content["trading_pair"])
        self.assertEqual(12, msg.content["update_id"])
        self.assertEqual([(1999.0, 1.2)], [(float(p), float(a)) for p, a in msg.content["bids"]])

    async def test_parse_order_book_snapshot_message_ignores_unknown_market(self):
        q = asyncio.Queue()

        await self.data_source._parse_order_book_snapshot_message({"channel": "order_book:9999", "order_book": {}}, q)

        self.assertTrue(q.empty())

    async def test_parse_order_book_snapshot_message_uses_fallback_update_id(self):
        q = asyncio.Queue()
        raw_message = {
            "channel": "order_book:2048",
            "timestamp": 1710000000000,
            "offset": 77,
            "order_book": {
                "nonce": 0,
                "bids": [],
                "asks": [],
            },
        }

        await self.data_source._parse_order_book_snapshot_message(raw_message, q)
        msg = q.get_nowait()

        self.assertEqual(77, msg.content["update_id"])

    async def test_parse_order_book_diff_message(self):
        q = asyncio.Queue()
        raw_message = {
            "channel": "order_book:2048",
            "type": "update/order_book",
            "timestamp": 1710000002000,
            "order_book": {
                "begin_nonce": 20,
                "nonce": 25,
                "bids": [{"price": "1998", "size": "2.0"}],
                "asks": [{"price": "2002", "size": "1.1"}],
            },
        }

        await self.data_source._parse_order_book_diff_message(raw_message, q)
        msg = q.get_nowait()

        self.assertEqual(25, msg.content["update_id"])
        self.assertEqual(20, msg.content["first_update_id"])

    async def test_parse_order_book_diff_message_uses_offset_when_nonce_missing(self):
        q = asyncio.Queue()
        raw_message = {
            "channel": "order_book:2048",
            "timestamp": 1710000002000,
            "offset": 33,
            "order_book": {
                "begin_nonce": 0,
                "nonce": 0,
                "bids": [],
                "asks": [],
            },
        }

        await self.data_source._parse_order_book_diff_message(raw_message, q)
        msg = q.get_nowait()

        self.assertEqual(33, msg.content["update_id"])
        self.assertEqual(33, msg.content["first_update_id"])

    async def test_parse_order_book_diff_message_ignores_unknown_market(self):
        q = asyncio.Queue()

        await self.data_source._parse_order_book_diff_message({"channel": "order_book:9999", "order_book": {}}, q)

        self.assertTrue(q.empty())

    async def test_parse_trade_message(self):
        q = asyncio.Queue()
        raw_message = {
            "channel": "trade:2048",
            "timestamp": 1710000003000,
            "trades": [{"trade_id": "abc", "price": "2000", "size": "0.4", "is_maker_ask": True}],
        }

        await self.data_source._parse_trade_message(raw_message, q)
        msg = q.get_nowait()

        self.assertEqual("abc", msg.trade_id)
        self.assertEqual("ETH-USDC", msg.content["trading_pair"])

    async def test_parse_trade_message_ignores_unknown_market(self):
        q = asyncio.Queue()

        await self.data_source._parse_trade_message({"channel": "trade:9999", "trades": []}, q)

        self.assertTrue(q.empty())

    def test_channel_originating_message(self):
        snapshot_channel = self.data_source._channel_originating_message(
            {"channel": "order_book:2048", "type": "subscribed/order_book"}
        )
        diff_channel = self.data_source._channel_originating_message(
            {"channel": "order_book:2048", "type": "update/order_book"}
        )
        trade_channel = self.data_source._channel_originating_message({"channel": "trade:2048", "type": "trade"})

        self.assertEqual(self.data_source._snapshot_messages_queue_key, snapshot_channel)
        self.assertEqual(self.data_source._diff_messages_queue_key, diff_channel)
        self.assertEqual(self.data_source._trade_messages_queue_key, trade_channel)

    def test_channel_originating_message_defaults_and_unknowns(self):
        fallback_snapshot = self.data_source._channel_originating_message(
            {"channel": "order_book:2048", "type": "other"}
        )
        missing_channel = self.data_source._channel_originating_message({"type": "trade"})
        unknown_channel = self.data_source._channel_originating_message({"channel": "other:2048", "type": "trade"})

        self.assertEqual(self.data_source._snapshot_messages_queue_key, fallback_snapshot)
        self.assertEqual("", missing_channel)
        self.assertEqual("", unknown_channel)
