from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class BeaxyInFlightOrder(InFlightOrderBase):
    cdef:
        public object created_at
