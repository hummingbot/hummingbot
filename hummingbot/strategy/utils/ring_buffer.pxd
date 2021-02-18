import numpy as np
from libc.stdint cimport int64_t
cimport numpy as np

cdef class RingBuffer:
    cdef:
        np.double_t[:] _buffer
        int64_t _start_index
        int64_t _stop_index
        int64_t _length
        bint _is_full

    cpdef void add_value(self, float val)
    cpdef void increment_index(self)
    cpdef double get_last_value(self)
    cpdef bint is_full(self)
    cpdef double mean_value(self)
    cpdef double variance(self)
    cpdef double std_dev(self)
    cpdef np.ndarray[np.double_t, ndim=1] get_as_numpy_array(self)
