from hummingbot.market.in_flight_order_base cimport InFlightOrderBase

cdef class LoopringInFlightOrder(InFlightOrderBase):
   cdef:
        object market
        object status
        long long created_at
