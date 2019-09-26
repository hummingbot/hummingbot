from libc.stdint cimport int64_t

# from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.huobi.huobi_market cimport HuobiMarket
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class MockHuobiMarket(HuobiMarket):
    pass