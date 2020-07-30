from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker

cdef class BinancePerpetualMarket(MarketBase):
    cdef:
        object _user_stream_tracker
        object _ev_loop

    cdef c_did_timout_tx(self, str tracking_id)
    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object trade_type,
                                object price,
                                object amount,
                                object order_type)
