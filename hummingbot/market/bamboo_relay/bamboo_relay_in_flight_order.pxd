from hummingbot.market.in_flight_order_base cimport InFlightOrderBase

cdef class BambooRelayInFlightOrder(InFlightOrderBase):
    cdef:
        public bint is_coordinated
        public int expires
        public object available_amount_base
        public object protocol_fee_amount
        public object taker_fee_amount
        public str tx_hash
        public object zero_ex_order