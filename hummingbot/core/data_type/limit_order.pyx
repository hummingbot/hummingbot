# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/LimitOrder.cpp

from cpython cimport PyObject
from libcpp.string cimport string

from decimal import Decimal
import pandas as pd
from typing import List
import time

from hummingbot.core.event.events import LimitOrderStatus

cdef class LimitOrder:
    @classmethod
    def to_pandas(cls, limit_orders: List[LimitOrder], mid_price: float = 0.0, hanging_ids: List[str] = None) \
            -> pd.DataFrame:
        cdef:
            list buys = [o for o in limit_orders if o.is_buy]
            list sells = [o for o in limit_orders if not o.is_buy]
        buys.sort(key=lambda x: x.price, reverse=True)
        sells.sort(key=lambda x: x.price, reverse=True)
        cdef:
            list orders
            list columns = ["Order ID", "Type", "Price", "Spread", "Amount", "Age", "Hang"]
            list data = []
            str order_id_txt, type_txt, price_txt, spread_txt, age_txt, hang_txt
            double quantity
            long age_seconds
        orders = sells.extend(buys)
        for order in orders:
            order_id_txt = f"...{order.client_order_id[-4:]}"
            type_txt = "buy" if order.is_buy else "sell"
            price_txt = float(order.price)
            spread_txt = f"{(0 if mid_price == 0 else abs(float(order.price) - mid_price) / mid_price):.2%}"
            quantity = float(order.quantity)
            age_txt = "n/a"
            age_seconds = order.age_seconds()
            if order.creation_timestamp >= 0:
                age_txt = pd.Timestamp(age_seconds, unit='s', tz='UTC').strftime('%H:%M:%S')
            hang_txt = "n/a" if hanging_ids is None else ("yes" if order.client_order_id in hanging_ids else "no")
            data.append([order_id_txt, type_txt, price_txt, spread_txt, quantity, age_txt, hang_txt])
        return pd.DataFrame(data=data, columns=columns)

    def __init__(self,
                 client_order_id: str,
                 trading_pair: str,
                 is_buy: bool,
                 base_currency: str,
                 quote_currency: str,
                 price: Decimal,
                 quantity: Decimal,
                 filled_quantity: Decimal = Decimal("NaN"),
                 creation_timestamp: int = 0.0,
                 status: LimitOrderStatus = LimitOrderStatus.UNKNOWN):
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
                                              <PyObject *> quantity,
                                              <PyObject *> filled_quantity,
                                              creation_timestamp,
                                              status.value)

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

    @property
    def filled_quantity(self) -> Decimal:
        return <object>(self._cpp_limit_order.getFilledQuantity())

    @property
    def creation_timestamp(self) -> float:
        return self._cpp_limit_order.getCreationTimestamp()

    @property
    def status(self) -> LimitOrderStatus:
        return LimitOrderStatus(self._cpp_limit_order.getStatus())

    cdef long c_age_seconds_since(self, unsigned long start_timestamp):
        print(f"start_time: {start_timestamp}")
        cdef unsigned long age = -1
        if self.creation_timestamp > 0:
            print(self.creation_timestamp)
            age = (start_timestamp - self.creation_timestamp) / 1e6
        elif len(self.client_order_id) > 16 and self.client_order_id[-16:].isnumeric():
            print(self.client_order_id)
            age = (start_timestamp - int(self.client_order_id[-16:])) / 1e6
        return age

    cdef long c_age_seconds(self):
        # return 0
        cdef unsigned long age = self.c_age_seconds_since(int(time.time() * 1e6))
        print(f"age: {age}")
        return age

    def age_seconds(self) -> int:
        return self.c_age_seconds()

    def age_seconds_since(self, start_timestamp: int) -> int:
        return self.c_age_seconds_since(start_timestamp)

    def __repr__(self) -> str:
        return (f"LimitOrder('{self.client_order_id}', '{self.trading_pair}', {self.is_buy}, '{self.base_currency}', "
                f"'{self.quote_currency}', {self.price}, {self.quantity}, {self.filled_quantity})")


cdef LimitOrder c_create_limit_order_from_cpp_limit_order(const CPPLimitOrder cpp_limit_order):
    cdef LimitOrder retval = LimitOrder.__new__(LimitOrder)
    retval._cpp_limit_order = cpp_limit_order
    return retval
