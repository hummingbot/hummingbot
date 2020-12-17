cdef class DydxFillReport:
    cdef:
        public str id
        public object amount
        public object price
        public object fee
