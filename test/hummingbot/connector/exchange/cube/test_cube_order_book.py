from unittest import TestCase

from hummingbot.connector.exchange.cube.cube_order_book import CubeOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class BinanceOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = CubeOrderBook.snapshot_message_from_exchange(
            msg={'result': {
                'levels': [{'price': 17695, 'quantity': 16, 'side': 0}, {'price': 17694, 'quantity': 42, 'side': 0},
                           {'price': 17693, 'quantity': 55, 'side': 0}, {'price': 17692, 'quantity': 49, 'side': 0},
                           {'price': 17691, 'quantity': 51, 'side': 0}, {'price': 17690, 'quantity': 82, 'side': 0},
                           {'price': 17689, 'quantity': 141, 'side': 0}, {'price': 17688, 'quantity': 56, 'side': 0},
                           {'price': 17698, 'quantity': 20, 'side': 1}, {'price': 17699, 'quantity': 29, 'side': 1},
                           {'price': 17700, 'quantity': 3, 'side': 1}, {'price': 17701, 'quantity': 37, 'side': 1},
                           {'price': 17702, 'quantity': 27, 'side': 1}, {'price': 17703, 'quantity': 13, 'side': 1},
                           {'price': 17704, 'quantity': 4, 'side': 1}, {'price': 17705, 'quantity': 26, 'side': 1}],
                'lastTransactTime': 1710840543845664276, 'lastTradePrice': 17695, 'marketState': 'normalOperation'},
                'trading_pair': 'TSOL-TUSDC'},
            timestamp=1710840543845664276,
        )

        self.assertEqual("TSOL-TUSDC", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1710840543845664276, snapshot_message.timestamp)
        self.assertEqual(1710840543845664276, snapshot_message.update_id)
        self.assertEqual(8, len(snapshot_message.bids))
        self.assertEqual(17695, snapshot_message.bids[0].price)
        self.assertEqual(16, snapshot_message.bids[0].amount)
        self.assertEqual(1710840543845664276, snapshot_message.bids[0].update_id)
        self.assertEqual(8, len(snapshot_message.asks))
        self.assertEqual(17698, snapshot_message.asks[0].price)
        self.assertEqual(20, snapshot_message.asks[0].amount)
        self.assertEqual(1710840543845664276, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_bid_msg = CubeOrderBook.diff_message_from_exchange(
            msg={'trading_pair': 'TSOL-TUSDC',
                 'update_id': 1710840545,
                 'bids': [OrderBookRow(
                     price=171.92000000000002,
                     amount=0,
                     update_id=1710840545)],
                 'asks': []},
            timestamp=1710840545,
            metadata={"trading_pair": "TSOL-TUSDC"}
        )

        diff_ask_msg = CubeOrderBook.diff_message_from_exchange(
            msg={'trading_pair': 'TSOL-TUSDC',
                 'update_id': 1710840545, 'bids': [],
                 'asks': [OrderBookRow(price=176.92000000000002, amount=0.16, update_id=1710840545)]},
            timestamp=1710840545
        )

        self.assertEqual("TSOL-TUSDC", diff_bid_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_bid_msg.type)
        self.assertEqual(1710840545, diff_bid_msg.timestamp)
        self.assertEqual(1710840545, diff_bid_msg.update_id)
        self.assertEqual(1, len(diff_bid_msg.bids))
        self.assertEqual(171.92000000000002, diff_bid_msg.bids[0].price)
        self.assertEqual(0, diff_bid_msg.bids[0].amount)

        self.assertEqual(1710840545, diff_ask_msg.timestamp)
        self.assertEqual(1710840545, diff_ask_msg.update_id)
        self.assertEqual(1, len(diff_ask_msg.asks))
        self.assertEqual(176.92000000000002, diff_ask_msg.asks[0].price)
        self.assertEqual(0.16, diff_ask_msg.asks[0].amount)
        self.assertEqual(1710840545, diff_ask_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {'trading_pair': 'TSOL-TUSDC', 'price': 177.53, 'fill_quantity': 0.09,
                        'transact_time': 1710842905725833115,
                        'trade_id': 78151849, 'trade_type': 2.0, "timestamp": 1710842905725833115}

        trade_message = CubeOrderBook.trade_message_from_exchange(
            msg=trade_update
        )

        self.assertEqual("TSOL-TUSDC", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1710842905725833115, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(78151849, trade_message.trade_id)
