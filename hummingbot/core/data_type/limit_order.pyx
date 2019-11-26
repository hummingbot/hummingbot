# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/LimitOrder.cpp

from cpython cimport PyObject
from libcpp.string cimport string

from decimal import Decimal
import pandas as pd
from typing import List

cdef class LimitOrder:
    @classmethod
    def to_pandas(cls, limit_orders: List[LimitOrder]) -> pd.DataFrame:
        cdef:
            list columns = ["Order_Id", "is_buy", "Trading_Pair", "Base_Asset", "Quote_Asset", "Price", "Quantity"]
            list data = [[
                limit_order.client_order_id,
                limit_order.is_buy,
                limit_order.trading_pair,
                limit_order.base_currency,
                limit_order.quote_currency,
                float(limit_order.price),
                float(limit_order.quantity)
            ] for limit_order in limit_orders]

        return pd.DataFrame(data=data, columns=columns)

    def __init__(self,
                 client_order_id: str,
                 trading_pair: str,
                 is_buy: bool,
                 base_currency: str,
                 quote_currency: str,
                 price: Decimal,
                 quantity: Decimal):
        cdef:
            string cpp_client_order_id = client_order_id.encode("utf8")
            string cpp_trading_pair = trading_pair.encode("utf8")
            string cpp_base_currency = base_currency.encode("utf8")
            string cpp_quote_currency = quote_currency.encode("utf8")
        self._cpp_limit_order = CPPLimitOrder(cpp_client_order_id,
                                              cpp_trading_pair,
                                              is_buy,
                                              cpp_base_currency,
                                              cpp_quote_currency,
                                              <PyObject *> price,
                                              <PyObject *> quantity)

    @property
    def client_order_id(self) -> str:
        cdef:
            string cpp_client_order_id = self._cpp_limit_order.getClientOrderID()
            str retval = cpp_client_order_id.decode("utf8")
        return retval

    @property
    def trading_pair(self) -> str:
        cdef:
            string cpp_trading_pair = self._cpp_limit_order.getTradingPair()
            str retval = cpp_trading_pair.decode("utf8")
        return retval

    @property
    def is_buy(self) -> bool:
        return self._cpp_limit_order.getIsBuy()

    @property
    def base_currency(self) -> str:
        cdef:
            string cpp_base_currency = self._cpp_limit_order.getBaseCurrency()
            str retval = cpp_base_currency.decode("utf8")
        return retval

    @property
    def quote_currency(self) -> str:
        cdef:
            string cpp_quote_currency = self._cpp_limit_order.getQuoteCurrency()
            str retval = cpp_quote_currency.decode("utf8")
        return retval

    @property
    def price(self) -> Decimal:
        return <object>(self._cpp_limit_order.getPrice())

    @property
    def quantity(self) -> Decimal:
        return <object>(self._cpp_limit_order.getQuantity())

    def __repr__(self) -> str:
        return (f"LimitOrder('{self.client_order_id}', '{self.trading_pair}', {self.is_buy}, '{self.base_currency}', "
                f"'{self.quote_currency}', {self.price}, {self.quantity})")


cdef LimitOrder c_create_limit_order_from_cpp_limit_order(const CPPLimitOrder cpp_limit_order):
    cdef LimitOrder retval = LimitOrder.__new__(LimitOrder)
    retval._cpp_limit_order = cpp_limit_order
    return retval
