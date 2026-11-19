import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_api_order_book_data_source import (
    ReyaPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType

PAIR, SYMBOL = "BTC-RUSD", "BTCRUSDPERP"


class MockWSAssistant:
    def __init__(self):
        self.sent = []

    async def send(self, request):
        self.sent.append(request.payload)


class ReyaPerpetualAPIOrderBookDataSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connector = SimpleNamespace(
            exchange_symbol_associated_to_pair=AsyncMock(return_value=SYMBOL),
            trading_pair_associated_to_exchange_symbol=AsyncMock(return_value=PAIR),
            _api_get=AsyncMock(),
        )
        self.data_source = ReyaPerpetualAPIOrderBookDataSource([PAIR], self.connector, SimpleNamespace())

    @staticmethod
    def depth(kind, bids, asks):
        return {"symbol": SYMBOL, "type": kind, "bids": bids, "asks": asks, "updatedAt": 1700000000000}

    async def test_subscribes_to_depth_trades_and_summary(self):
        ws = MockWSAssistant()
        await self.data_source._subscribe_channels(ws)
        self.assertEqual([f"/v2/market/{SYMBOL}/depth", f"/v2/market/{SYMBOL}/perpExecutions",
                          f"/v2/perpMarket/{SYMBOL}/summary"], [payload["channel"] for payload in ws.sent])
        self.assertTrue(all(payload["type"] == "subscribe" for payload in ws.sent))

    async def test_depth_snapshot_and_updates_keep_arrival_order(self):
        snapshot = {"type": "subscribed", "channel": f"/v2/market/{SYMBOL}/depth",
                    "contents": self.depth("SNAPSHOT", [{"px": "100", "qty": "1"}], [{"px": "101", "qty": "2"}])}
        update = {"type": "channel_data", "channel": f"/v2/market/{SYMBOL}/depth",
                  "data": self.depth("UPDATE", [{"px": "100", "qty": "0"}], [])}
        self.assertEqual(self.data_source._snapshot_messages_queue_key,
                         self.data_source._channel_originating_message(snapshot))
        self.assertEqual(self.data_source._diff_messages_queue_key,
                         self.data_source._channel_originating_message(update))
        self.assertLess(snapshot["update_id"], update["update_id"])

        output = asyncio.Queue()
        await self.data_source._parse_order_book_snapshot_message(snapshot, output)
        await self.data_source._parse_order_book_diff_message(update, output)
        snapshot_message, diff_message = output.get_nowait(), output.get_nowait()
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual([(100.0, 1.0)], [(row.price, row.amount) for row in snapshot_message.bids])
        self.assertEqual(OrderBookMessageType.DIFF, diff_message.type)
        # Quantities are absolute; zero removes the level.
        self.assertEqual([(100.0, 0.0)], [(row.price, row.amount) for row in diff_message.bids])

    async def test_only_new_trades_are_emitted(self):
        trade = {"symbol": SYMBOL, "side": "A", "price": "100", "qty": "0.5", "timestamp": 1700000000000,
                 "sequenceNumber": 9}
        replay = {"type": "subscribed", "channel": f"/v2/market/{SYMBOL}/perpExecutions", "contents": {"data": [trade]}}
        live = {"type": "channel_data", "channel": f"/v2/market/{SYMBOL}/perpExecutions", "data": [trade]}
        self.assertEqual("", self.data_source._channel_originating_message(replay))
        self.assertEqual(self.data_source._trade_messages_queue_key,
                         self.data_source._channel_originating_message(live))

        output = asyncio.Queue()
        await self.data_source._parse_trade_message(live, output)
        message = output.get_nowait()
        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual("9", message.trade_id)

    async def test_funding_rate_is_converted_from_percentage_points(self):
        summary = {"symbol": SYMBOL, "markPrice": "101", "oraclePrice": "100", "fundingRate": "0.01"}
        self.connector._api_get.return_value = summary
        info = await self.data_source.get_funding_info(PAIR)
        self.assertEqual(Decimal("0.0001"), info.rate)
        self.assertEqual(Decimal("101"), info.mark_price)

        output = asyncio.Queue()
        await self.data_source._parse_funding_info_message(
            {"type": "channel_data", "channel": f"/v2/perpMarket/{SYMBOL}/summary", "data": summary}, output)
        update = output.get_nowait()
        self.assertEqual(Decimal("0.0001"), update.rate)
        self.assertEqual(Decimal("100"), update.index_price)

    async def test_rest_snapshot_matches_the_streamed_depth_view(self):
        self.connector._api_get.return_value = self.depth("SNAPSHOT", [{"px": "100", "qty": "1"}], [])
        message = await self.data_source._order_book_snapshot(PAIR)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual({"limit": 100}, self.connector._api_get.call_args.kwargs["params"])

    def test_rejected_subscriptions_are_not_routed(self):
        self.assertEqual("", self.data_source._channel_originating_message(
            {"type": "error", "channel": f"/v2/market/{SYMBOL}/depth", "message": "Unknown market"}))
