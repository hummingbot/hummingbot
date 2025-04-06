# distutils: language=c++
from hummingbot.core.data_type.order_book cimport OrderBook

cdef class CompositeOrderBook(OrderBook):
    cdef:
        OrderBook _traded_order_book

    cdef double c_get_price(self, bint is_buy) except? -1
