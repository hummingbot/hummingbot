from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase


cdef class CoinbaseProInFlightOrder(InFlightOrderBase):
    cdef:
        object trade_id_set
