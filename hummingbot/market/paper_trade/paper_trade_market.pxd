from libcpp.set cimport set as cpp_set
from libcpp.unordered_map cimport unordered_map
from libcpp.string cimport string

ctypedef cpp_set[CPPLimitOrder] SingleSymbolLimitOrders
ctypedef unordered_map[string, SingleSymbolLimitOrders].iterator LimitOrdersIterator
ctypedef cpp_set[CPPLimitOrder].iterator SingleSymbolLimitOrdersIterator
ctypedef cpp_set[CPPLimitOrder].reverse_iterator SingleSymbolLimitOrdersRIterator