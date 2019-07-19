from libcpp.set cimport set as cpp_set
from libcpp.string cimport string
from libcpp.unordered_map cimport unordered_map
from libcpp.utility cimport pair

from hummingbot.core.data_type.LimitOrder cimport LimitOrder as CPPLimitOrder
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.event.events import MarketEvent, OrderType

from hummingbot.market.paper_trade import symbol_pair

from .market_config import (
    MarketConfig,
    AssetType
)

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
        dict _symbol_pairs
        dict _account_balance
        object _order_book_tracker
        object _config
        object _queued_orders
        dict _quantization_params
