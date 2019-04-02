cdef class EventListener:
    cdef object __weakref__
    cdef c_call(self, object arg)