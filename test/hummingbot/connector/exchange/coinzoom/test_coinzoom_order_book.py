import dateutil.parser
from unittest import TestCase

from hummingbot.connector.exchange.coinzoom.coinzoom_order_book import CoinzoomOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinzoomOrderBookTests(TestCase):

    def test_trade_message_from_exchange(self):
        date_time = "2020-01-16T21:02:23Z"
        message = CoinzoomOrderBook.trade_message_from_exchange(["BTC-USDT", 8772.05, 0.01, date_time])
        expected_timestamp = int(dateutil.parser.parse(date_time).timestamp() * 1e3)

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual(expected_timestamp, message.timestamp)
        self.assertEqual("BTC-USDT", message.content["trading_pair"])
        self.assertEqual(8772.05, message.content["price"])
        self.assertEqual(0.01, message.content["amount"])
        self.assertEqual(None, message.content["trade_type"])
