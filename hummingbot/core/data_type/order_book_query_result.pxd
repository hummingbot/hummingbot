# distutils: language=c++

cdef class OrderBookQueryResult:
    cdef:
        public double query_price
        public double query_volume
        public double result_price
        public double result_volume
