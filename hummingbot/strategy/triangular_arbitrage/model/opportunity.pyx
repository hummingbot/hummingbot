# distutils: language=c++

from hummingbot.core.event.events import TradeType
from decimal import Decimal
from typing import List
from hummingbot.strategy.triangular_arbitrage.model.arbitrage cimport trade_direction_to_str

cdef class ModelOrder():
    def __init__(self,
                 market_id: int,
                 trading_pair: str,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal
                 ):
        self._market_id = market_id
        self._trading_pair = trading_pair
        self._trade_type = trade_type
        self._price = price
        self._amount = amount

    @property
    def trading_pair(self):
        return self._trading_pair

    @property
    def trade_type(self):
        return self._trade_type

    @property
    def price(self):
        return self._price

    @property
    def amount(self):
        return self._amount

    def __str__(self):
        type_str = "BUY" if self.trade_type == TradeType.BUY else "SELL"
        return f"pair: {self.trading_pair} type: {type_str} price: {self.price:.6g} amount: {self.amount:.6g}"

cdef class Opportunity():
    def __init__(self, orders: List[ModelOrder], direction: TradeDirection = TradeDirection.CClockwise, execute: bool = True):
        self._orders = orders
        self._direction = direction
        self._execute = execute

    @property
    def can_execute(self):
        return self._execute

    @property
    def direction(self):
        return self._direction

    @property
    def orders(self):
        return self._orders

    def __str__(self):
        str_ = ""
        if len(self._orders) > 0:
            for order in self._orders:
                str_ += f"[{order}]\n"
            str_ = "".join([f"Direction: {trade_direction_to_str(self._direction)} Execute: {self._execute}", f"\nOrders:\n{str_}"])
        else:
            str_ = "empty order list"
        return str_
