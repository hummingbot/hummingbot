# distutils: language=c++

from hummingbot.core.event.events import TradeType
from decimal import Decimal

s_decimal_0 = Decimal(0.)

cdef str trade_direction_to_str(TradeDirection direction):
    return "Counter-Clocwise" if direction == TradeDirection.CClockwise else "Clockwise"

cdef class Node():
    def __init__(self, asset: str):
        self._asset = asset

    @property
    def asset(self):
        return self._asset

    def __str__(self):
        return f"{self.asset}"

cdef class Edge():
    def __init__(self, market_id, trading_pair: str, trade_type: TradeType, price: Decimal,
                 amount: Decimal = s_decimal_0, fee: Decimal = s_decimal_0
                 ):
        self._market_id = market_id
        self._trading_pair = trading_pair
        self._trade_type = trade_type
        self._price = price
        self._amount = amount
        self._fee = fee

    @property
    def trading_pair(self):
        return self._trading_pair

    @property
    def market_id(self):
        return self._market_id

    @property
    def trade_type(self):
        return self._trade_type

    @property
    def price(self):
        return self._price

    @price.setter
    def price(self, p):
        self._price = p

    @property
    def fee(self):
        return self._fee

    @fee.setter
    def fee(self, f):
        self._fee = f

    @property
    def amount(self):
        return self._amount

    @amount.setter
    def amount(self, a):
        self._amount = a

    def __str__(self):
        return f'mkt id: {self.market_id} pair: {self.trading_pair} type: {self.trade_type} price: {self.price:.6f} amount: {self.amount:.6f}'

cdef class TriangularArbitrage():
    def __init__(self,
                 top: Node = None,
                 left: Node = None,
                 right: Node = None,
                 left_edge: Edge = None,
                 cross_edge: Edge = None,
                 right_edge: Edge = None,
                 direction: TradeDirection = TradeDirection.CClockwise
                 ):
        self._top = top
        self._left = left
        self._right = right
        self._left_edge = left_edge
        self._cross_edge = cross_edge
        self._right_edge = right_edge
        self.direction = direction
        if direction == TradeDirection.CClockwise:
            self.trading_pairs = tuple([self._left_edge.trading_pair, self._cross_edge.trading_pair, self._right_edge.trading_pair])
            self.trade_types = tuple([self._left_edge.trade_type, self._cross_edge.trade_type, self._right_edge.trade_type])
        else:
            self.trading_pairs = tuple([self._right_edge.trading_pair, self._cross_edge.trading_pair, self._left_edge.trading_pair])
            self.trade_types = tuple([self._right_edge.trade_type, self._cross_edge.trade_type, self._left_edge.trade_type])

    @property
    def right_edge(self):
        return self._right_edge

    @property
    def cross_edge(self):
        return self._cross_edge

    @property
    def left_edge(self):
        return self._left_edge

    @property
    def top(self):
        return self._top

    @property
    def left(self):
        return self._left

    @property
    def right(self):
        return self._right

    def __str__(self):
        return "".join([f"trade direction: {trade_direction_to_str(self.direction)} ",
                        f"\ntop: {self.top} left: {self.left} right: {self.right} ",
                        f"\nleft_edge: {self.left_edge} ",
                        f"\ncross_edge: {self.cross_edge} "
                        f"\nright_edge: {self.right_edge} ",
                        f"\ntrading_pairs: {self.trading_pairs} ",
                        f"\ntrade_types: {self.trade_types}"])
