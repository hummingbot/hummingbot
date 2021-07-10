# distutils: language=c++

from .LimitOrder cimport LimitOrder as CPPLimitOrder


cdef class LimitOrder:
    cdef:
        CPPLimitOrder _cpp_limit_order
    cdef long c_age(self)
    cdef long c_age_til(self, long start_timestamp)


cdef LimitOrder c_create_limit_order_from_cpp_limit_order(const CPPLimitOrder cpp_limit_order)
