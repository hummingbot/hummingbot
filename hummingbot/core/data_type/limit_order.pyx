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
            list columns = ["Order_Id", "Price", "Quantity", "Spread"]
            list data = [[
                limit_order.client_order_id,
                float(limit_order.price),
                float(limit_order.quantity),
                float(limit_order.spread)
            ] for limit_order in limit_orders]

        return pd.DataFrame(data=data, columns=columns)

    def __init__(self,
                 client_order_id: str,
                 price: Decimal,
                 quantity: Decimal,
                 spread: Decimal
                 ):
        cdef:
            string cpp_client_order_id = client_order_id.encode("utf8")
        self._cpp_limit_order = CPPLimitOrder(cpp_client_order_id,
                                              <PyObject *> price,
                                              <PyObject *> quantity,
                                              <PyObject *> spread)

    @property
    def client_order_id(self) -> str:
        cdef:
            string cpp_client_order_id = self._cpp_limit_order.getClientOrderID()
            str retval = cpp_client_order_id.decode("utf8")
        return retval

    @property
    def price(self) -> Decimal:
        return <object>(self._cpp_limit_order.getPrice())

    @property
    def quantity(self) -> Decimal:
        return <object>(self._cpp_limit_order.getQuantity())

    @property
    def spread(self) -> Decimal:
        return <object>(self._cpp_limit_order.getSpread())

    def __repr__(self) -> str:
        return (f"LimitOrder('{self.client_order_id}', {self.price}, {self.quantity}, "
                f"{self.spread})")


cdef LimitOrder c_create_limit_order_from_cpp_limit_order(const CPPLimitOrder cpp_limit_order):
    cdef LimitOrder retval = LimitOrder.__new__(LimitOrder)
    retval._cpp_limit_order = cpp_limit_order
    return retval
