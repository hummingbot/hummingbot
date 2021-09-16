from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class PeatioInFlightOrder(InFlightOrderBase):
    cdef:
        public set trade_ids
