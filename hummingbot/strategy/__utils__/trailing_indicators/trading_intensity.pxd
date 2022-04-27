# distutils: language=c++

from libc.stdint cimport int64_t
from libcpp.set cimport set

from hummingbot.core.data_type.OrderBookEntry cimport OrderBookEntry
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.event_listener cimport EventListener

cdef class TradingIntensityIndicator:
    cdef:
        double _alpha
        double _kappa
        dict _trade_samples
        list _current_trade_sample
        object _trades_forwarder
        OrderBook _order_book
        object _price_delegate
        list _last_quotes
        int _sampling_length
        int _samples_length

    cdef c_calculate(self, timestamp)
    cdef c_register_trade(self, object trade)
    cdef c_estimate_intensity(self)

cdef class TradesForwarder(EventListener):
    cdef:
        TradingIntensityIndicator _indicator
