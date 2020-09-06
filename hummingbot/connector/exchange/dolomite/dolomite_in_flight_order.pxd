from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class DolomiteInFlightOrder(InFlightOrderBase):
    cdef:
        public object tracked_fill_ids
