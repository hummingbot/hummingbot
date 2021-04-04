from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class KrakenInFlightOrder(InFlightOrderBase):
    cdef:
        public object trade_id_set
        public int userref
