# distutils: language=c++

from kairos.core.time_iterator cimport TimeIterator


cdef class PyTimeIterator(TimeIterator):
    pass
