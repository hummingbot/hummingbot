from unittest import TestCase

from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book import AscendExOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class AscendExOrderBookTests(TestCase):

    def test_trade_message_from_exchange(self):
        json_message = {'m': 'trades',
                        'symbol': 'BTC/USD',
                        'data': {"p": "0.068600",
                                 "q": "100.000",
                                 "ts": 1573069903254,
                                 "bm": False,
                                 "seqnum": 144115188077966308}
                        }
        extra_metadata = {"trading_pair": "BTC=USDT"}

        message = AscendExOrderBook.trade_message_from_exchange(msg=json_message["data"], timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual(-1, message.update_id)
        self.assertEqual(-1, message.first_update_id)
        self.assertEqual(1000, message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertFalse(message.has_update_id)
        self.assertTrue(message.has_trade_id)
        self.assertEqual(json_message["data"]["p"], message.content["price"])
        self.assertEqual(json_message["data"]["q"], message.content["amount"])
        self.assertEqual("sell", message.content["trade_type"])

    def test_snapshot_message_from_exchange(self):
        json_message = {'m': 'depth-snapshot',
                        'symbol': 'BTC/USD',
                        'data': {"seqnum": 3167819629,
                                 "ts": 1573142900389,
                                 "asks": [["45011.0", "73405"], ["45011.50", "390053"]],
                                 "bids": [["44896.0", "2"], ["44896.50", "300009"]]}
                        }
        extra_metadata = {"trading_pair": "BTC=USD"}

        message = AscendExOrderBook.snapshot_message_from_exchange(msg=json_message["data"], timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(1000, message.update_id)
        self.assertEqual(-1, message.first_update_id)
        self.assertEqual(-1, message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertTrue(message.has_update_id)
        self.assertFalse(message.has_trade_id)

        first_bid = message.bids[0]
        second_bid = message.bids[1]
        self.assertEqual(44896.00, first_bid.price)
        self.assertEqual(2.0, first_bid.amount)
        self.assertEqual(message.update_id, first_bid.update_id)
        self.assertEqual(44896.50, second_bid.price)
        self.assertEqual(300009.0, second_bid.amount)
        self.assertEqual(message.update_id, second_bid.update_id)

        first_ask = message.asks[0]
        second_ask = message.asks[1]
        self.assertEqual(45011.00, first_ask.price)
        self.assertEqual(73405.0, first_ask.amount)
        self.assertEqual(message.update_id, first_ask.update_id)
        self.assertEqual(45011.50, second_ask.price)
        self.assertEqual(390053.0, second_ask.amount)
        self.assertEqual(message.update_id, second_ask.update_id)

    def test_diff_message_from_exchange(self):
        json_message = {'m': 'depth',
                        'symbol': 'BTC/USD',
                        'data': {"seqnum": 1573069021376,
                                 "ts": 2097965,
                                 "asks": [["45950.50", "1115"], ["45962.00", "0"], ["46055.50", "515"]],
                                 "bids": [["45949.50", "4947162"]]}
                        }
        extra_metadata = {"trading_pair": "BTC=USD"}

        message = AscendExOrderBook.diff_message_from_exchange(msg=json_message["data"], timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual(1000, message.update_id)
        self.assertEqual(message.update_id, message.first_update_id)
        self.assertEqual(-1, message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertTrue(message.has_update_id)
        self.assertFalse(message.has_trade_id)

        first_bid = message.bids[0]
        self.assertEqual(1, len(message.bids))
        self.assertEqual(45949.50, first_bid.price)
        self.assertEqual(4947162.0, first_bid.amount)
        self.assertEqual(message.update_id, first_bid.update_id)

        first_ask = message.asks[0]
        second_ask = message.asks[1]
        third_ask = message.asks[2]
        self.assertEqual(3, len(message.asks))
        self.assertEqual(45950.50, first_ask.price)
        self.assertEqual(1115.0, first_ask.amount)
        self.assertEqual(message.update_id, first_ask.update_id)
        self.assertEqual(45962.00, second_ask.price)
        self.assertEqual(0.0, second_ask.amount)
        self.assertEqual(message.update_id, second_ask.update_id)
        self.assertEqual(46055.50, third_ask.price)
        self.assertEqual(515.0, third_ask.amount)
        self.assertEqual(message.update_id, third_ask.update_id)
