from libcpp.set cimport set as cpp_set
from libcpp.string cimport string
from libcpp.unordered_map cimport unordered_map
from libcpp.utility cimport pair

from hummingbot.core.data_type.LimitOrder cimport LimitOrder as CPPLimitOrder

ctypedef cpp_set[CPPLimitOrder] SingleSymbolLimitOrders
ctypedef unordered_map[string, SingleSymbolLimitOrders].iterator LimitOrdersIterator
ctypedef pair[string, SingleSymbolLimitOrders] LimitOrdersPair
ctypedef unordered_map[string, SingleSymbolLimitOrders] LimitOrders
ctypedef cpp_set[CPPLimitOrder].iterator SingleSymbolLimitOrdersIterator
ctypedef cpp_set[CPPLimitOrder].reverse_iterator SingleSymbolLimitOrdersRIterator


cdef class PaperTradeMarket(MarketBase):
    cdef:
        LimitOrders _bid_limit_orders
        LimitOrders _ask_limit_orders