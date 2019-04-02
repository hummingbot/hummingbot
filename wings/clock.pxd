# distutils: language=c++

cdef class Clock:
    cdef:
        object _clock_mode
        double _tick_size
        double _start_time
        double _end_time
        object _child_iterators
        double _current_tick
        bint _started