# distutils: language=c++

cdef class OrderBookQueryResult:
    def __cinit__(self, double query_price, double query_volume, double result_price, double result_volume):
        self.query_price = query_price
        self.query_volume = query_volume
        self.result_price = result_price
        self.result_volume = result_volume
