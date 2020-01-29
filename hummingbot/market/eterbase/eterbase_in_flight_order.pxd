from hummingbot.market.in_flight_order_base cimport InFlightOrderBase


cdef class EterbaseInFlightOrder(InFlightOrderBase):
    cdef:
        public object fill_ids
