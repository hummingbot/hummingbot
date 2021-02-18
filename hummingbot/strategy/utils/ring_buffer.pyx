import numpy as np
import logging
cimport numpy as np


pmm_logger = None

cdef class RingBuffer:
    @classmethod
    def logger(cls):
        global pmm_logger
        if pmm_logger is None:
            pmm_logger = logging.getLogger(__name__)
        return pmm_logger

    def __cinit__(self, int length):
        self._length = length
        self._buffer = np.zeros(length, dtype=np.double)
        self._start_index = 0
        self._stop_index = 0
        self._is_full = False

    cpdef void add_value(self, float val):
        self._buffer[self._stop_index] = val
        self.increment_index()

    cpdef void increment_index(self):
        self._stop_index = (self._stop_index + 1) % self._length
        if(self._start_index == self._stop_index):
            self._is_full = True
            self._start_index = (self._start_index + 1) % self._length

    cpdef double get_last_value(self):
        if self._stop_index==0:
            return self._buffer[-1]
        else:
            return self._buffer[self._stop_index-1]

    cpdef bint is_full(self):
        return self._is_full

    cpdef double mean_value(self):
        result = np.nan
        if self._is_full:
            result=np.mean(self.get_as_numpy_array())
        return result

    cpdef double variance(self):
        result = np.nan
        if self._is_full:
            result = np.var(self.get_as_numpy_array())
        return result

    cpdef double std_dev(self):
        result = np.nan
        if self._is_full:
            result = np.std(self.get_as_numpy_array())
        return result

    cpdef np.ndarray[np.double_t, ndim=1] get_as_numpy_array(self):
        cdef np.ndarray[np.int16_t, ndim=1] indexes

        if not self._is_full:
            indexes = np.arange(self._start_index, stop=self._stop_index, dtype=np.int16)
        else:
            indexes = np.arange(self._start_index, stop=self._start_index + self._length,
                                dtype=np.int16) % self._length
        return np.asarray(self._buffer)[indexes]
