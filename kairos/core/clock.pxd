# distutils: language=c++

cdef class Clock:
    cdef:
        object _clock_mode
        double _tick_size
        double _start_time
        double _end_time
        list _child_iterators
        list _current_context
        double _current_tick
        bint _started
