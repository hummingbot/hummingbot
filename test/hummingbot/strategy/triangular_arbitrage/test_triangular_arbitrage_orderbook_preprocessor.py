import unittest
from collections import namedtuple
from decimal import Decimal
import numpy as np
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.core.event.events import TradeType
from hummingbot.strategy.triangular_arbitrage.model.arbitrage import TriangularArbitrage, Node, Edge
from hummingbot.strategy.triangular_arbitrage.optimizer.order_book_preprocessor import OrderBookPreprocessor

TestBook = namedtuple('TestBook', 'bids asks')


def trade_type_to_str_f(t):
    return "BUY" if t == TradeType.BUY else "SELL"


def reverse_trade_type_f(t):
    return TradeType.SELL if t == TradeType.BUY else TradeType.BUY


def price_amt_f(x):
    return [(float(i.price), float(i.amount)) for i in x]


class TestOrderBookPreprocessor(unittest.TestCase):
    def setUp(self):
        self.arbitrage = TriangularArbitrage(
            top = Node('ETH'),
            left = Node('USD'),
            right = Node('BTC'),
            left_edge = Edge(0, 'ETH-USDT', TradeType.SELL, Decimal(0)),
            cross_edge = Edge(1, 'BTC-USDT', TradeType.BUY, Decimal(0)),
            right_edge = Edge(2, 'ETH-BTC', TradeType.BUY, Decimal(0))
        )

        self._preprocessor = OrderBookPreprocessor(self.arbitrage)

        self.left_bids = [
            ClientOrderBookRow(Decimal('100'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('99'), Decimal('0.78'), 0),
            ClientOrderBookRow(Decimal('98'), Decimal('2.1'), 0)
        ]
        self.left_asks = [
            ClientOrderBookRow(Decimal('98'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('99'), Decimal('0.78'), 0),
            ClientOrderBookRow(Decimal('100'), Decimal('2.1'), 0)
        ]

        self.cross_bids = [
            ClientOrderBookRow(Decimal('1002'), Decimal('0.078'), 0),
            ClientOrderBookRow(Decimal('1001'), Decimal('0.001'), 0),
            ClientOrderBookRow(Decimal('1000'), Decimal('0.03'), 0),
        ]
        self.cross_asks = [
            ClientOrderBookRow(Decimal('1000'), Decimal('0.078'), 0),
            ClientOrderBookRow(Decimal('1001'), Decimal('0.001'), 0),
            ClientOrderBookRow(Decimal('1002'), Decimal('0.03'), 0),
        ]

        self.right_bids = [
            ClientOrderBookRow(Decimal('0.13'), Decimal('1'), 0),
            ClientOrderBookRow(Decimal('0.12'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('0.1'), Decimal('2'), 0),
        ]
        self.right_asks = [
            ClientOrderBookRow(Decimal('0.1'), Decimal('1'), 0),
            ClientOrderBookRow(Decimal('0.12'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('0.13'), Decimal('2'), 0),
        ]

        self.wallets = [Decimal('0.5'), Decimal('100'), Decimal('0.05')]
        self.fee = Decimal('0.004')

    def test_preprocess_cclockwise(self):
        print("test_preprocess_cclockwise entry trade sequence: "
              f"{trade_type_to_str_f(self.arbitrage.left_edge.trade_type)}->"
              f"{trade_type_to_str_f(self.arbitrage.cross_edge.trade_type)}->"
              f"{trade_type_to_str_f(self.arbitrage.right_edge.trade_type)}")

        # note that this structure is made so that the tuple has 'bids' and 'asks'
        book_1 = TestBook(self.left_bids, self.left_asks)
        book_2 = TestBook(self.cross_bids, self.cross_asks)
        book_3 = TestBook(self.right_bids, self.right_asks)

        """ Get sum amounts of bids/asks"""
        book_1_bid_amts = np.sum([float(i.amount) for i in book_1.bids])
        book_1_ask_amts = np.sum([float(i.amount) for i in book_1.asks])
        book_2_bid_amts = np.sum([float(i.amount) for i in book_2.bids])
        book_2_ask_amts = np.sum([float(i.amount) for i in book_2.asks])
        book_3_bid_amts = np.sum([float(i.amount) for i in book_3.bids])
        book_3_ask_amts = np.sum([float(i.amount) for i in book_3.asks])

        print(f"\nwallets: {np.array(self.wallets).astype(float)}")
        print(f"\nraw book_1 bids: {price_amt_f(book_1.bids)} asks:{price_amt_f(book_1.asks)}")
        print(f"raw book_2 bids: {price_amt_f(book_2.bids)} asks:{price_amt_f(book_2.asks)}")
        print(f"raw book_3 bids: {price_amt_f(book_3.bids)} asks:{price_amt_f(book_3.asks)}")

        """ Generate pre-processed orderbooks based on wallet contents.
            Takes tuple of PreprocessSequence instances """
        (left_book, cross_book, right_book) = self._preprocessor.preprocess_cclockwise(
            book_1, book_2, book_3, self.wallets, self.fee
        )

        left_preproc_amts = np.sum([float(e.amount) for e in left_book])
        cross_preproc_amts = np.sum([float(e.amount) for e in cross_book])
        right_preproc_amts = np.sum([float(e.amount) for e in right_book])

        """ Check pre-processed orderbook against raw orderbooks """
        book_1_amts = book_1_ask_amts if self.arbitrage.left_edge.trade_type == TradeType.BUY else book_1_bid_amts
        print(f"\nleft book (pre-processed amts: {left_preproc_amts}) <= (book_1_amts: {book_1_amts})")
        self.assertTrue(left_preproc_amts <= book_1_amts)
        # this should hold for first trades
        self.assertTrue(left_preproc_amts <= self.wallets[0])

        book_2_amts = book_2_ask_amts if self.arbitrage.cross_edge.trade_type == TradeType.BUY else book_2_bid_amts
        print(f"cross book (pre-processed amts: {cross_preproc_amts}) <= (book_2_amts: {book_2_amts})")
        self.assertTrue(cross_preproc_amts <= book_2_amts)

        book_3_amts = book_3_ask_amts if self.arbitrage.cross_edge.trade_type == TradeType.BUY else book_3_bid_amts
        print(f"right book (pre-processed amts: {right_preproc_amts}) <= (book_3_amts: {book_3_amts})")
        self.assertTrue(right_preproc_amts <= book_3_amts)

        print("test_preprocess_cclockwise exit")

    def test_preprocess_clockwise(self):
        print("test_preprocess_clockwise entry trade sequence: "
              f"{trade_type_to_str_f(reverse_trade_type_f(self.arbitrage.right_edge.trade_type))}->"
              f"{trade_type_to_str_f(reverse_trade_type_f(self.arbitrage.cross_edge.trade_type))}->"
              f"{trade_type_to_str_f(reverse_trade_type_f(self.arbitrage.left_edge.trade_type))}")

        # note the order of the books here
        book_1 = TestBook(self.right_bids, self.right_asks)
        book_2 = TestBook(self.cross_bids, self.cross_asks)
        book_3 = TestBook(self.left_bids, self.left_asks)

        """ Get sum amounts of bids/asks"""
        book_1_bid_amts = np.sum([float(i.amount) for i in book_1.bids])
        book_1_ask_amts = np.sum([float(i.amount) for i in book_1.asks])
        book_2_bid_amts = np.sum([float(i.amount) for i in book_2.bids])
        book_2_ask_amts = np.sum([float(i.amount) for i in book_2.asks])
        book_3_bid_amts = np.sum([float(i.amount) for i in book_3.bids])
        book_3_ask_amts = np.sum([float(i.amount) for i in book_3.asks])

        print(f"\nwallets: {np.array(self.wallets).astype(float)}")
        print(f"\nraw book_1 bids: {price_amt_f(book_1.bids)} asks:{price_amt_f(book_1.asks)}")
        print(f"raw book_2 bids: {price_amt_f(book_2.bids)} asks:{price_amt_f(book_2.asks)}")
        print(f"raw book_3 bids: {price_amt_f(book_3.bids)} asks:{price_amt_f(book_3.asks)}")

        """ Generate pre-processed orderbooks based on wallet contents.
            Takes tuple of PreprocessSequence instances """
        (left_book, cross_book, right_book) = self._preprocessor.preprocess_cclockwise(
            book_1, book_2, book_3, self.wallets, self.fee
        )

        left_preproc_amts = np.sum([float(e.amount) for e in left_book])
        cross_preproc_amts = np.sum([float(e.amount) for e in cross_book])
        right_preproc_amts = np.sum([float(e.amount) for e in right_book])

        """ Check pre-processed orderbook against raw orderbooks """
        book_1_amts = book_1_ask_amts if self.arbitrage.left_edge.trade_type == TradeType.BUY else book_1_bid_amts
        print(f"\nleft book (pre-processed amts: {left_preproc_amts}) <= (book_1_amts: {book_1_amts})")
        self.assertTrue(left_preproc_amts <= book_1_amts)
        # this should hold for first trades
        self.assertTrue(left_preproc_amts <= self.wallets[0])

        book_2_amts = book_2_ask_amts if self.arbitrage.cross_edge.trade_type == TradeType.BUY else book_2_bid_amts
        print(f"cross book (pre-processed amts: {cross_preproc_amts}) <= (book_2_amts: {book_2_amts})")
        self.assertTrue(cross_preproc_amts <= book_2_amts)

        book_3_amts = book_3_ask_amts if self.arbitrage.cross_edge.trade_type == TradeType.BUY else book_3_bid_amts
        print(f"right book (pre-processed amts: {right_preproc_amts}) <= (book_3_amts: {book_3_amts})")
        self.assertTrue(right_preproc_amts <= book_3_amts)

        print("test_preprocess_clockwise exit")
