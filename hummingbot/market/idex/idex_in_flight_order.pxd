from hummingbot.market.in_flight_order_base cimport InFlightOrderBase

cdef class IDEXInFlightOrder(InFlightOrderBase):
    cdef:
        public object available_amount_base
        public object gas_fee_amount
        public double created_timestamp
        public object created_timestamp_update_event
