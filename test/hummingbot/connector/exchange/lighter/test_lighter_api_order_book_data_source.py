import asyncio
import sys
import types
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

if "hummingbot.core.data_type.order_book" not in sys.modules:
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

    async def test_subscribe_channels_subscribes_order_book_and_trade(self):
        ws = MagicMock()
        ws.send = AsyncMock()

        await self.data_source._subscribe_channels(ws)

        self.assertEqual(2, ws.send.await_count)
        sent_payloads = [call.args[0].payload for call in ws.send.await_args_list]
        self.assertEqual({"type": "subscribe", "channel": "order_book/2048"}, sent_payloads[0])
        self.assertEqual({"type": "subscribe", "channel": "trade/2048"}, sent_payloads[1])

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
