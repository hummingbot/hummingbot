from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class FtxInFlightOrder(InFlightOrderBase):
    cdef:
        public double created_at
        public object state
        object trade_id_set
