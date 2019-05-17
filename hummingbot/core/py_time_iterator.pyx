# distutils: language=c++


cdef class PyTimeIterator(TimeIterator):
    def tick(self, double timestamp):
        raise NotImplementedError

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.tick(timestamp)
