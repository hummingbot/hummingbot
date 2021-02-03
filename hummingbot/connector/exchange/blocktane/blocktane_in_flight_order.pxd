from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class BlocktaneInFlightOrder(InFlightOrderBase):
    cdef:
        public long long created_at
