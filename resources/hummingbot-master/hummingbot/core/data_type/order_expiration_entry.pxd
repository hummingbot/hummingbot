# distutils: language=c++

from hummingbot.core.data_type.OrderExpirationEntry cimport OrderExpirationEntry as CPPOrderExpirationEntry


cdef class OrderExpirationEntry:
    cdef:
        CPPOrderExpirationEntry _cpp_order_expiration_entry


cdef OrderExpirationEntry c_create_order_expiration_from_cpp_order_expiration(const CPPOrderExpirationEntry cpp_order_expiration_entry)
