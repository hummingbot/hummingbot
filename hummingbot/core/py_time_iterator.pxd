# distutils: language=c++

from hummingbot.core.time_iterator cimport TimeIterator


cdef class PyTimeIterator(TimeIterator):
    pass
