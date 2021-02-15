import numpy as np
from libc.stdint cimport int64_t
cimport numpy as np

cdef class RingBuffer:
    cdef:
        np.float64_t[:] _buffer
        int64_t _start_index
        int64_t _stop_index
        int64_t _length
        bint _is_full

    cdef c_add_value(self, float val)
    cdef c_increment_index(self)
    cdef double c_get_last_value(self)
    cdef bint c_is_full(self)
    cdef object c_get_array(self)
    cdef double c_mean_value(self)
    cdef double c_variance(self)
    cdef double c_std_dev(self)
    cdef object c_get_as_numpy_array(self)
