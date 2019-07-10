cdef class InFlightOrderBase:
    cdef:
        public object market_class
        public str client_order_id
        public str exchange_order_id
        public str symbol
        public object order_type
        public object trade_type
        public object price
        public object amount
        public object executed_amount_base
        public object executed_amount_quote
        public str fee_asset
        public object fee_paid
        public str last_state
