# distutils: language=c++

from .time_iterator cimport TimeIterator


cdef class PyTimeIterator(TimeIterator):
    pass
