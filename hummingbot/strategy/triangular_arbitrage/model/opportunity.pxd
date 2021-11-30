# distutils: language=c++

from hummingbot.strategy.triangular_arbitrage.model.arbitrage cimport TradeDirection


cdef class ModelOrder():
    cdef:
        int _market_id
        str _trading_pair
        object _trade_type
        object _amount
        object _price

cdef class Opportunity():
    cdef:
        list _orders
        TradeDirection _direction
        bint _execute

