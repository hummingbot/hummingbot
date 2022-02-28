from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class BittrexInFlightOrder(InFlightOrderBase):
    cdef:
        object trade_id_set
