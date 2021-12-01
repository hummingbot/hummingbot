from typing import List
from collections import namedtuple
from decimal import Decimal

from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.core.event.events import TradeType

from hummingbot.strategy.triangular_arbitrage.model.arbitrage import TriangularArbitrage


PreprocessSequence = namedtuple('PreprocessSequence', 'f g h p1 p2')


class OrderBookPreprocessor():
    '''
    Initialized with the arbitrage triangle from the strategy. init determines and stores two
    functions which depend on whether currencies for different trading pairs match. These functions
    preprocess orderbooks based on current wallet states.
    '''
    def __init__(self, arb_triangle: TriangularArbitrage):
        self._clockwise_sequence = self._initialize_clockwise_function(arb_triangle)
        self._cclockwise_sequence = self._initialize_cclockwise_function(arb_triangle)

    def preprocess_clockwise(self, right_book, cross_book, left_book, wallets, fees):
        new_right_book = self._clockwise_sequence.f(right_book, wallets[0])
        proceeds_1 = self._clockwise_sequence.p1(new_right_book, fees)
        new_cross_book = self._clockwise_sequence.g(cross_book, wallets[1] + proceeds_1)
        proceeds_2 = self._clockwise_sequence.p2(new_cross_book, fees)
        new_left_book = self._clockwise_sequence.h(left_book, wallets[2] + proceeds_2)

        return new_right_book, new_cross_book, new_left_book

    def preprocess_cclockwise(self, left_book, cross_book, right_book, wallets, fees):
        new_left_book = self._cclockwise_sequence.f(left_book, wallets[0])
        proceeds_1 = self._cclockwise_sequence.p1(new_left_book, fees)
        new_cross_book = self._cclockwise_sequence.g(cross_book, wallets[1] + proceeds_1)
        proceeds_2 = self._cclockwise_sequence.p2(new_cross_book, fees)
        new_right_book = self._cclockwise_sequence.h(right_book, wallets[2] + proceeds_2)

        return new_left_book, new_cross_book, new_right_book

    def _initialize_clockwise_function(self, arb_triangle: TriangularArbitrage):
        first_base, first_quote = arb_triangle.right_edge.trading_pair.split('-')

        # trade types are oriented counter-clockwise in the arb triangle
        if arb_triangle.right_edge.trade_type == TradeType.BUY:
            f = self.preprocess_bids
            first_target = first_quote
            first_is_buy = False
        else:
            f = self.preprocess_asks
            first_target = first_base
            first_is_buy = True

        second_base, second_quote = arb_triangle.cross_edge.trading_pair.split('-')

        if arb_triangle.cross_edge.trade_type == TradeType.BUY:
            g = self.preprocess_bids
            second_origin = second_base
            second_target = second_quote
            second_is_buy = False
        else:
            g = self.preprocess_asks
            second_origin = second_quote
            second_target = second_base
            second_is_buy = True

        third_base, third_quote = arb_triangle.left_edge.trading_pair.split('-')

        if arb_triangle.left_edge.trade_type == TradeType.BUY:
            h = self.preprocess_bids
            third_origin = third_base
        else:
            h = self.preprocess_asks
            third_origin = third_quote

        if arb_triangle.right_edge.market_id == arb_triangle.cross_edge.market_id and first_target == second_origin:
            proceeds_1 = self.compute_proceeds_of_buy if first_is_buy else self.compute_proceeds_of_sell
        else:
            def proceeds_1(x, y):
                return Decimal('0')

        if arb_triangle.cross_edge.market_id == arb_triangle.left_edge.market_id and second_target == third_origin:
            proceeds_2 = self.compute_proceeds_of_buy if second_is_buy else self.compute_proceeds_of_sell
        else:
            def proceeds_2(x, y):
                return Decimal('0')

        return PreprocessSequence(f, g, h, proceeds_1, proceeds_2)

    def _initialize_cclockwise_function(self, arb_triangle: TriangularArbitrage):
        first_base, first_quote = arb_triangle.left_edge.trading_pair.split('-')

        if arb_triangle.left_edge.trade_type == TradeType.BUY:
            f = self.preprocess_asks
            first_target = first_base
            first_is_buy = True
        else:
            f = self.preprocess_bids
            first_target = first_quote
            first_is_buy = False

        second_base, second_quote = arb_triangle.cross_edge.trading_pair.split('-')

        if arb_triangle.cross_edge.trade_type == TradeType.BUY:
            g = self.preprocess_asks
            second_origin = second_quote
            second_target = second_base
            second_is_buy = True
        else:
            g = self.preprocess_bids
            second_origin = second_base
            second_target = second_quote
            second_is_buy = False

        third_base, third_quote = arb_triangle.right_edge.trading_pair.split('-')

        if arb_triangle.right_edge.trade_type == TradeType.BUY:
            h = self.preprocess_asks
            third_origin = third_quote
        else:
            h = self.preprocess_bids
            third_origin = third_base

        if arb_triangle.left_edge.market_id == arb_triangle.cross_edge.market_id and first_target == second_origin:
            proceeds_1 = self.compute_proceeds_of_buy if first_is_buy else self.compute_proceeds_of_sell
        else:
            def proceeds_1(x, y):
                return Decimal('0')

        if arb_triangle.cross_edge.market_id == arb_triangle.right_edge.market_id and second_target == third_origin:
            proceeds_2 = self.compute_proceeds_of_buy if second_is_buy else self.compute_proceeds_of_sell
        else:
            def proceeds_2(x, y):
                return Decimal('0')

        return PreprocessSequence(f, g, h, proceeds_1, proceeds_2)

    @staticmethod
    def compute_proceeds_of_buy(asks: List[ClientOrderBookRow], fee: Decimal):
        return sum([a.amount for a in asks]) * (Decimal('1') - fee)

    @staticmethod
    def compute_proceeds_of_sell(bids: List[ClientOrderBookRow], fee: Decimal):
        return sum([b.amount * b.price for b in bids]) * (Decimal('1') - fee)

    @staticmethod
    def preprocess_asks(book, total_funds: Decimal):
        total_required_funds = Decimal('0')
        asks = book.asks

        new_asks: List[ClientOrderBookRow] = []
        for ask in asks:
            total_ask_funds: Decimal = ask.price * ask.amount
            if (total_required_funds + total_ask_funds) < total_funds:
                new_asks.append(ask)
                total_required_funds += total_ask_funds
            else:
                new_ask_amount: Decimal = (total_funds - total_required_funds) / ask.price
                new_ask = ClientOrderBookRow(ask.price, new_ask_amount, 0)
                new_asks.append(new_ask)
                break
        return new_asks

    @staticmethod
    def preprocess_bids(book, total_funds: Decimal):
        total_required_funds = Decimal('0')
        bids = book.bids

        new_bids: List[ClientOrderBookRow] = []
        for bid in bids:
            total_bid_funds: Decimal = bid.amount
            if (total_required_funds + total_bid_funds) < total_funds:
                new_bids.append(bid)
                total_required_funds += total_bid_funds
            else:
                new_bid_amount: Decimal = (total_funds - total_required_funds)
                new_bid = ClientOrderBookRow(bid.price, new_bid_amount, 0)
                new_bids.append(new_bid)
                break
        return new_bids
