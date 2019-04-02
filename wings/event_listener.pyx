cdef class EventListener:
    def __call__(self, arg: any):
        raise NotImplementedError

    cdef c_call(self, object arg):
        self(arg)
