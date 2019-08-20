from hummingbot.market.trading_rule cimport TradingRule

cdef class DolomiteToken:
    cdef:
        public str ticker
        public int precision
        public str contract_address

cdef class DolomiteTradingRule(TradingRule):
    cdef:
        public DolomiteToken primary_token
        public DolomiteToken secondary_token
        public DolomiteToken fee_token
        public object network_fee_per_fill
        