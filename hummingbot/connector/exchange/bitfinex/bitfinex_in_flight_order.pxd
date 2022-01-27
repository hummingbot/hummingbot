from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class BitfinexInFlightOrder(InFlightOrderBase):
    cdef:
        object trade_id_set
