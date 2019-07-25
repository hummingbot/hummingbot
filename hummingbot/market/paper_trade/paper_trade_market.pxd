from libcpp.set cimport set as cpp_set
from libcpp.string cimport string
from libcpp.unordered_map cimport unordered_map
from libcpp.utility cimport pair

from hummingbot.core.data_type.LimitOrder cimport LimitOrder as CPPLimitOrder
from hummingbot.core.data_type.OrderExpirationEntry cimport OrderExpirationEntry as CPPOrderExpirationEntry
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.event.events import MarketEvent, OrderType

from hummingbot.market.paper_trade.symbol_pair import SymbolPair

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
ctypedef cpp_set[CPPOrderExpirationEntry] LimitOrderExpirationSet
ctypedef cpp_set[CPPOrderExpirationEntry].iterator LimitOrderExpirationSetIterator


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
        LimitOrderExpirationSet _limit_order_expiration_set
        object _order_tracker_task

    cdef c_execute_buy(self, str order_id, str symbol, double amount)
    cdef c_execute_sell(self, str order_id, str symbol, double amount)
    cdef c_process_market_orders(self)
    cdef c_set_balance(self, str currency, double amount)
    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price)