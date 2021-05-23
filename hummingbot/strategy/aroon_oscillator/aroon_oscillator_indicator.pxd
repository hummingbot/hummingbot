# distutils: language=c++

cdef class OscillatorPeriod:
    cdef:
        object _high
        object _low
        double _start
        double _end

    cdef c_add_tick(self, object price)


cdef class AroonOscillatorIndicator:
    cdef:
        int _period_length
        int _period_duration
        double _last_time_period
        double _next_time_period
        list _oscillator_periods
        OscillatorPeriod _current_period

    cdef c_add_tick(self, double tick_stamp, object last_trade_price)
    cdef bint c_full(self)
    cdef object c_aroon_osc(self)
    cdef object c_aroon_up(self)
    cdef object c_aroon_down(self)
    cdef list c_aroon_periods(self)
    cdef int c_aroon_period_count(self)
    cdef OscillatorPeriod c_last_period(self)
