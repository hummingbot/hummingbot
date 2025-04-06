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
        self._buffer = np.zeros(length, dtype=np.float64)
        self._delimiter = 0
        self._is_full = False

    def __dealloc__(self):
        self._buffer = None

    cdef void c_add_value(self, float val):
        self._buffer[self._delimiter] = val
        self.c_increment_delimiter()

    cdef void c_increment_delimiter(self):
        self._delimiter = (self._delimiter + 1) % self._length
        if not self._is_full and self._delimiter == 0:
            self._is_full = True

    cdef bint c_is_empty(self):
        return (not self._is_full) and (0==self._delimiter)

    cdef double c_get_last_value(self):
        if self.c_is_empty():
            return np.nan
        return self._buffer[self._delimiter-1]

    cdef bint c_is_full(self):
        return self._is_full

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

    cdef np.ndarray[np.double_t, ndim=1] c_get_as_numpy_array(self):
        cdef np.ndarray[np.int16_t, ndim=1] indexes

        if not self._is_full:
            indexes = np.arange(0, stop=self._delimiter, dtype=np.int16)
        else:
            indexes = np.arange(self._delimiter, stop=self._delimiter + self._length,
                                dtype=np.int16) % self._length
        return np.asarray(self._buffer)[indexes]

    def __init__(self, length):
        self._length = length
        self._buffer = np.zeros(length, dtype=np.double)
        self._delimiter = 0
        self._is_full = False

    def add_value(self, val):
        self.c_add_value(val)

    def get_as_numpy_array(self):
        return self.c_get_as_numpy_array()

    def get_last_value(self):
        return self.c_get_last_value()

    @property
    def is_full(self):
        return self.c_is_full()

    @property
    def mean_value(self):
        return self.c_mean_value()

    @property
    def std_dev(self):
        return self.c_std_dev()

    @property
    def variance(self):
        return self.c_variance()

    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, value):
        data = self.get_as_numpy_array()

        self._length = value
        self._buffer = np.zeros(value, dtype=np.float64)
        self._delimiter = 0
        self._is_full = False

        for val in data[-value:]:
            self.add_value(val)
