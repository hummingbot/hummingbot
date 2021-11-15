from unittest import TestCase

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book import BybitPerpetualOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.event.events import TradeType


class BybitPerpetualOrderBookTests(TestCase):

    def test_trade_message_from_exchange(self):
        json_message = {'trade_time_ms': 1628618168965,
                        'timestamp': '2021-08-10T17:56:08.000Z',
                        'symbol': 'BTCUSDT',
                        'side': 'Buy',
                        'size': 5,
                        'price': 45011,
                        'tick_direction': 'PlusTick',
                        'trade_id': '6b78ccb1-b967-5b55-b237-025f8ce38f3f',
                        'cross_seq': 8926514939}
        extra_metadata = {"trading_pair": "BTC=USDT"}

        message = BybitPerpetualOrderBook.trade_message_from_exchange(msg=json_message, timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual(-1, message.update_id)
        self.assertEqual(-1, message.first_update_id)
        self.assertEqual(json_message["trade_id"], message.trade_id)
        self.assertEqual(extra_metadata["trading_pair"], message.trading_pair)
        self.assertEqual([], message.asks)
        self.assertEqual([], message.bids)
        self.assertFalse(message.has_update_id)
        self.assertTrue(message.has_trade_id)
        self.assertEqual(json_message["price"], message.content["price"])
        self.assertEqual(json_message["size"], message.content["amount"])
        self.assertEqual(float(TradeType.BUY.value), message.content["trade_type"])

    def test_snapshot_message_from_exchange(self):
        json_message = {'topic': 'orderBook_200.100ms.BTCUSD',
                        'type': 'snapshot',
                        'data': [{'price': '44896.00',
                                  'symbol': 'BTCUSD',
                                  'id': 448960000,
                                  'side': 'Buy',
                                  'size': 2},
                                 {'price': '44896.50',
                                  'symbol': 'BTCUSD',
                                  'id': 448965000,
                                  'side': 'Buy',
                                  'size': 300009},
                                 {'price': '45011.00',
                                  'symbol': 'BTCUSD',
                                  'id': 450110000,
                                  'side': 'Sell',
                                  'size': 73405},
                                 {'price': '45011.50',
                                  'symbol': 'BTCUSD',
                                  'id': 450115000,
                                  'side': 'Sell',
                                  'size': 390053}],
                        'cross_seq': 8926514747,
                        'timestamp_e6': 1628618166211259}
        extra_metadata = {"trading_pair": "BTC=USD"}

        message = BybitPerpetualOrderBook.snapshot_message_from_exchange(msg=json_message, timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(json_message["timestamp_e6"], message.update_id)
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
        json_message = {'topic': 'orderBook_200.100ms.BTCUSD',
                        'type': 'delta',
                        'data': {
                            'delete': [
                                {'price': '45962.00',
                                 'symbol': 'BTCUSD',
                                 'id': 459620000,
                                 'side': 'Sell'}],
                            'update': [
                                {'price': '45949.50',
                                 'symbol': 'BTCUSD',
                                 'id': 459495000,
                                 'side': 'Buy',
                                 'size': 4947162},
                                {'price': '45950.50',
                                 'symbol': 'BTCUSD',
                                 'id': 459505000,
                                 'side': 'Sell',
                                 'size': 1115}],
                            'insert': [
                                {'price': '46055.50',
                                 'symbol': 'BTCUSD',
                                 'id': 460555000,
                                 'side': 'Sell',
                                 'size': 515}],
                            'transactTimeE6': 0},
                        'cross_seq': 8940905578,
                        'timestamp_e6': 1628685006311131}
        extra_metadata = {"trading_pair": "BTC=USD"}

        message = BybitPerpetualOrderBook.diff_message_from_exchange(msg=json_message, timestamp=1000, metadata=extra_metadata)

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual(json_message["timestamp_e6"], message.update_id)
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
