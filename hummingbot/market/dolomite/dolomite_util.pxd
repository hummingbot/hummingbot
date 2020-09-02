from hummingbot.connector.trading_rule cimport TradingRule

cdef class DolomiteToken:
    cdef:
        public str ticker
        public int precision
        public str contract_address

cdef class DolomiteTradingRule(TradingRule):
    cdef:
        public DolomiteToken primary_token
        public DolomiteToken secondary_token
        public object amount_decimal_places
        public object price_decimal_places
