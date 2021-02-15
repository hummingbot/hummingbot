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
        self._buffer = np.zeros(length)
        self._start_index = 0
        self._stop_index = 0
        self._is_full = False

    cdef c_add_value(self, float val):
        self._buffer[self._stop_index] = val
        self.c_increment_index()

    cdef c_increment_index(self):
        self._stop_index = (self._stop_index + 1) % self._length
        if(self._start_index == self._stop_index):
            self._is_full = True
            self._start_index = (self._start_index + 1) % self._length

    cdef double c_get_last_value(self):
        if self._stop_index==0:
            return self.c_get_array()[-1]
        else:
            return self.c_get_array()[self._stop_index-1]

    cdef bint c_is_full(self):
        return self._is_full

    cdef object c_get_array(self):
        return self._buffer

    cdef double c_mean_value(self):
        result = np.nan
        if self._is_full:
            result=np.mean(self.c_get_as_numpy_array())
        return result

    cdef double c_variance(self):
        result = np.nan
        if self._is_full:
            result = np.var(self.c_get_as_numpy_array())
        return result

    cdef double c_std_dev(self):
        result = np.nan
        if self._is_full:
            result = np.std(self.c_get_as_numpy_array())
        return result

    cdef object c_get_as_numpy_array(self):
        indexes = np.arange(self._start_index, stop=self._start_index + self._length) % self._length
        if not self._is_full:
            indexes = np.arange(self._start_index, stop=self._stop_index)
        return np.asarray(self.c_get_array())[indexes]
