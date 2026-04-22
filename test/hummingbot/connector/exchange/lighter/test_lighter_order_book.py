from unittest import TestCase

from hummingbot.connector.exchange.lighter.lighter_order_book import LighterOrderBook
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class LighterOrderBookTests(TestCase):
    def test_snapshot_message_from_exchange(self):
        message = LighterOrderBook.snapshot_message_from_exchange(
            msg={
                "update_id": 123,
                "bids": [["100.0", "1.2"]],
                "asks": [["101.0", "2.3"]],
            },
            timestamp=1700000000.0,
            metadata={"trading_pair": "ETH-USDC"},
        )

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual("ETH-USDC", message.trading_pair)
        self.assertEqual(123, message.update_id)
        self.assertEqual(100.0, message.bids[0].price)
        self.assertEqual(1.2, message.bids[0].amount)
        self.assertEqual(101.0, message.asks[0].price)
        self.assertEqual(2.3, message.asks[0].amount)

    def test_diff_message_from_exchange(self):
        message = LighterOrderBook.diff_message_from_exchange(
            msg={
                "first_update_id": 200,
                "update_id": 220,
                "bids": [["99.9", "0.5"]],
                "asks": [["100.1", "0.6"]],
            },
            timestamp=1700000001.0,
            metadata={"trading_pair": "ETH-USDC"},
        )

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual("ETH-USDC", message.trading_pair)
        self.assertEqual(220, message.update_id)
        self.assertEqual(200, message.first_update_id)

    def test_trade_message_from_exchange(self):
        buy_trade = LighterOrderBook.trade_message_from_exchange(
            msg={
                "trade_id": "t1",
                "nonce": 7,
                "price": "100.0",
                "size": "0.25",
                "is_maker_ask": True,
            },
            timestamp=1700000002.0,
            metadata={"trading_pair": "ETH-USDC"},
        )

        sell_trade = LighterOrderBook.trade_message_from_exchange(
            msg={
                "trade_id": "t2",
                "nonce": 8,
                "price": "101.0",
                "size": "0.35",
                "is_maker_ask": False,
            },
            timestamp=1700000003.0,
            metadata={"trading_pair": "ETH-USDC"},
        )

        self.assertEqual(OrderBookMessageType.TRADE, buy_trade.type)
        self.assertEqual("t1", buy_trade.trade_id)
        self.assertEqual(float(TradeType.BUY.value), buy_trade.content["trade_type"])
        self.assertEqual(float(TradeType.SELL.value), sell_trade.content["trade_type"])
