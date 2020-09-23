from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class BitstampInFlightOrder(InFlightOrderBase):
    cdef:
        public int last_transaction_id
