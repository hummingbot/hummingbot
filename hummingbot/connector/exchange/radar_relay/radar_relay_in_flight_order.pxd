from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class RadarRelayInFlightOrder(InFlightOrderBase):
    cdef:
        public object available_amount_base
        public object gas_fee_amount
        public str tx_hash
        public object zero_ex_order
