from hummingbot.market.in_flight_order_base cimport InFlightOrderBase

cdef class DDEXInFlightOrder(InFlightOrderBase):
    cdef:
        public object available_amount_base
        public object pending_amount_base
        public object gas_fee_amount
        public object trade_id_set
