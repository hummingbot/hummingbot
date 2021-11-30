# distutils: language=c++


cdef class ModelBook:
    cdef:
        public list bids
        public list asks
        int _level_size

