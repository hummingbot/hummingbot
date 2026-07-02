import asyncio
import unittest

from hummingbot.connector.exchange.twofinance.twofinance_api_order_book_data_source import (
    TwoFinanceAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class FakeWSAssistant:
    def __init__(self):
        self.sent = []

    async def send(self, request):
        self.sent.append(dict(request.payload))


class FakeAPIFactory:
    def __init__(self):
        self.ws = FakeWSAssistant()

    async def get_ws_assistant(self):
        return self.ws


class FakeConnector:
    _symbol_metadata = {
        "BTC-USDT": {"symbol_id": 1},
        "ETH-USDT": {"symbol_id": 2},
    }


class TwoFinanceAPIOrderBookDataSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api_factory = FakeAPIFactory()
        self.data_source = TwoFinanceAPIOrderBookDataSource(
            trading_pairs=["BTC-USDT"],
            connector=FakeConnector(),
            api_factory=self.api_factory,
        )

    async def test_parse_snapshot_event_message(self):
        queue = asyncio.Queue()

        await self.data_source._parse_order_book_snapshot_message(
            {
                "schema": "matchengine.event.v1",
                "sequence": 10,
                "event_id": "engine:10",
                "event_type": "ORDER_BOOK_SNAPSHOT",
                "market": "BTC/USDT",
                "payload": {
                    "bids": [["100", "1"]],
                    "asks": [["101", "2"]],
                    "timestamp": 123,
                },
            },
            queue,
        )

        message = queue.get_nowait()
        self.assertEqual(message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(message.trading_pair, "BTC-USDT")
        self.assertEqual(message.update_id, 10)
        self.assertEqual(message.bids[0].price, 100)
        self.assertEqual(message.asks[0].amount, 2)

    async def test_parse_diff_and_trade_messages(self):
        diff_queue = asyncio.Queue()
        trade_queue = asyncio.Queue()

        await self.data_source._parse_order_book_diff_message(
            {
                "schema": "matchengine.event.v1",
                "sequence": 11,
                "event_id": "engine:11",
                "event_type": "ORDER_BOOK_DIFF",
                "market": "BTC/USDT",
                "payload": {"bids": [{"price": "100", "quantity": "0"}], "asks": [["101", "3"]]},
            },
            diff_queue,
        )
        await self.data_source._parse_trade_message(
            {
                "schema": "matchengine.event.v1",
                "sequence": 12,
                "event_id": "engine:12",
                "event_type": "TRADE_EXECUTED",
                "market": "BTC/USDT",
                "payload": {"trade_id": 44, "side": "SELL", "price": "100.5", "quantity": "0.25"},
            },
            trade_queue,
        )

        diff_message = diff_queue.get_nowait()
        trade_message = trade_queue.get_nowait()
        self.assertEqual(diff_message.type, OrderBookMessageType.DIFF)
        self.assertEqual(diff_message.trading_pair, "BTC-USDT")
        self.assertEqual(diff_message.update_id, 11)
        self.assertEqual(diff_message.content["asks"], [["101", "3"]])
        self.assertEqual(trade_message.type, OrderBookMessageType.TRADE)
        self.assertEqual(trade_message.trading_pair, "BTC-USDT")
        self.assertEqual(trade_message.trade_id, 44)
        self.assertEqual(trade_message.content["trade_type"], 2.0)

    async def test_dynamic_subscribe_and_unsubscribe(self):
        self.data_source._ws_assistant = self.api_factory.ws

        subscribed = await self.data_source.subscribe_to_trading_pair("ETH-USDT")
        unsubscribed = await self.data_source.unsubscribe_from_trading_pair("ETH-USDT")

        self.assertTrue(subscribed)
        self.assertTrue(unsubscribed)
        self.assertEqual(self.api_factory.ws.sent[0], {"method": "subscribe", "params": ["2@BOOK", "2@TRADE", "2@LEVEL"]})
        self.assertEqual(self.api_factory.ws.sent[1], {"method": "unsubscribe", "params": ["2@BOOK", "2@TRADE", "2@LEVEL"]})

    async def test_initial_subscribe_uses_matchengine_symbol_params(self):
        await self.data_source._subscribe_channels(self.api_factory.ws)

        self.assertEqual(self.api_factory.ws.sent[0], {"method": "subscribe", "params": ["1@BOOK", "1@TRADE", "1@LEVEL"]})


if __name__ == "__main__":
    unittest.main()
