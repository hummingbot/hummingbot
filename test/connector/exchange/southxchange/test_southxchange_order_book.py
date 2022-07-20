from unittest import TestCase
from hummingbot.connector.exchange.southxchange.southxchange_order_book import SouthXchangeOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.connector.exchange.southxchange.southxchange_utils import convert_bookWebSocket_to_bookApi


class AscendExOrderBookTests(TestCase):

    def test_trade_message_from_exchange(self):
        json_message = {
            "k": "trade",
            "v": [
                {
                    "m": 3,
                    "d": "2022-07-15T19:20:40",
                    "b": False,
                    "a": 0.100000000000000000,
                    "p": 118.750000000000000000
                },
                {
                    "m": 3,
                    "d": "2022-07-15T19:17:06Z",
                    "b": True,
                    "a": 0.20000000,
                    "p": 118.750000000000000000
                }
            ]
        }
        extra_metadata = {"trading_pair": "BTC=USDT"}

        message = SouthXchangeOrderBook.trade_message_from_exchange(msg=json_message["v"][0], timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual(-1, message.update_id)
        self.assertEqual(-1, message.first_update_id)
        self.assertEqual(1000, message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertFalse(message.has_update_id)
        self.assertTrue(message.has_trade_id)
        self.assertEqual(json_message["v"][0]["p"], message.content["price"])
        self.assertEqual(json_message["v"][0]["a"], message.content["amount"])
        self.assertEqual("sell", message.content["trade_type"])

    def test_snapshot_message_from_exchange(self):
        json_message = {"BuyOrders": [{"Index": '0', "Amount": '0.011', "Price": '93.6'}, {"Index": '1', "Amount": '1.0', "Price": '92.0'}], "SellOrders": [{"Index": '0', "Amount": '0.99', "Price": '93.6'}, {"Index": '1', "Amount": '9.9', "Price": '101.0'}]}
        extra_metadata = {"trading_pair": "BTC=USD"}

        message = SouthXchangeOrderBook.snapshot_message_from_exchange(msg=json_message, timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(1000, message.update_id)
        self.assertEqual(-1, message.first_update_id)
        self.assertEqual(-1, message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertTrue(message.has_update_id)
        self.assertFalse(message.has_trade_id)

        first_bid = message.bids[0]
        second_bid = message.bids[1]
        self.assertEqual(93.6, first_bid.price)
        self.assertEqual(0.011, first_bid.amount)
        self.assertEqual(message.update_id, first_bid.update_id)
        self.assertEqual(92.0, second_bid.price)
        self.assertEqual(1.0, second_bid.amount)
        self.assertEqual(message.update_id, second_bid.update_id)

        first_ask = message.asks[0]
        second_ask = message.asks[1]
        self.assertEqual(93.6, first_ask.price)
        self.assertEqual(0.99, first_ask.amount)
        self.assertEqual(message.update_id, first_ask.update_id)
        self.assertEqual(101.0, second_ask.price)
        self.assertEqual(9.9, second_ask.amount)
        self.assertEqual(message.update_id, second_ask.update_id)

    def test_diff_message_from_exchange(self):
        json_message = {
            "k": "bookdelta",
            "v": [
                {
                    "m": 3,
                    "p": 118.75,
                    "a": 1.000000000000000000,
                    "b": True
                },
                {
                    "m": 3,
                    "p": 120,
                    "a": 0.900000000000000000,
                    "b": False
                },
                {
                    "m": 3,
                    "p": 962.01,
                    "a": 0.1,
                    "b": False
                }
            ]
        }
        extra_metadata = {"trading_pair": "BTC=USD"}
        message = SouthXchangeOrderBook.diff_message_from_exchange(msg=convert_bookWebSocket_to_bookApi(json_message["v"]), timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual(1000, message.update_id)
        self.assertEqual(message.update_id, message.first_update_id)
        self.assertEqual(-1, message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertTrue(message.has_update_id)
        self.assertFalse(message.has_trade_id)

        first_bid = message.bids[0]
        self.assertEqual(1, len(message.bids))
        self.assertEqual(118.75, first_bid.price)
        self.assertEqual(1.0, first_bid.amount)
        self.assertEqual(message.update_id, first_bid.update_id)

        first_ask = message.asks[0]
        second_ask = message.asks[1]
        self.assertEqual(2, len(message.asks))
        self.assertEqual(120, first_ask.price)
        self.assertEqual(0.9, first_ask.amount)
        self.assertEqual(message.update_id, first_ask.update_id)
        self.assertEqual(962.01, second_ask.price)
        self.assertEqual(0.1, second_ask.amount)
        self.assertEqual(message.update_id, second_ask.update_id)
