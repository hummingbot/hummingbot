from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase

cdef class LiquidInFlightOrder(InFlightOrderBase):
    cdef:
        object trade_id_set
