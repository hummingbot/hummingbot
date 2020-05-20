# distutils: language=c++

cdef class OrderBookQueryResult:
    cdef:
        public double query_price
        public double query_volume
        public double result_price
        public double result_volume


cdef class ClientOrderBookQueryResult:
    cdef:
        public object query_price
        public object query_volume
        public object result_price
        public object result_volume
