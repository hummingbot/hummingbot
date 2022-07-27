from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class LoopringInFlightOrder(InFlightOrderBase):
    cdef:
        public object status
