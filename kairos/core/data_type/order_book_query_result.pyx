# distutils: language=c++

cdef class OrderBookQueryResult:
    def __cinit__(self, double query_price, double query_volume, double result_price, double result_volume):
        self.query_price = query_price
        self.query_volume = query_volume
        self.result_price = result_price
        self.result_volume = result_volume


cdef class ClientOrderBookQueryResult:
    def __cinit__(self, object query_price, object query_volume, object result_price, object result_volume):
        self.query_price = query_price
        self.query_volume = query_volume
        self.result_price = result_price
        self.result_volume = result_volume
