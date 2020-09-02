from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase


cdef class EterbaseInFlightOrder(InFlightOrderBase):
    cdef:
        public object fill_ids
        public object cost
        public object executed_cost_quote
