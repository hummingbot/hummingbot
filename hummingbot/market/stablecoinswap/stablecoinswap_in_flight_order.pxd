from hummingbot.market.in_flight_order_base cimport InFlightOrderBase

cdef class StablecoinswapInFlightOrder(InFlightOrderBase):
    cdef:
        public str tx_hash
        public object fee_percent
