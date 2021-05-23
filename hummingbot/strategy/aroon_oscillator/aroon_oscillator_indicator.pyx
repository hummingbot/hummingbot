from decimal import Decimal

cdef class OscillatorPeriod:
    def __init__(self):
        self._high = None
        self._low = None
        self._start = 0
        self._end = 0

    cdef c_add_tick(self, double tick_stamp, object price):
        if not self._start:
            self._start = tick_stamp
        self._end = tick_stamp

        self._high = max(self._high, price)
        self._low = min(self._high, price)

    @property
    def high(self) -> Decimal:
        return self._high

    @property
    def low(self) -> Decimal:
        return self._low

    @property
    def start(self) -> double:
        return self._start

    @property
    def end(self) -> double:
        return self._end


cdef class AroonOscillatorIndicator:

    def __init__(self, period_length, period_duration):
        self._period_length = period_length
        self._period_duration = period_duration
        self._oscillator_periods = []
        self._current_period =None

        super().__init__()

    cdef bint c_full(self):
        return len(self._oscillator_periods) >= self._period_length

    cdef c_add_tick(self, double tick_stamp, object last_trade_price):
        if self.c_full():
            self._oscillator_periods.pop(0)

        if not self._current_period or tick_stamp >= self._current_period.start + self._period_duration:
            self._current_period = OscillatorPeriod()
            self._oscillator_periods.append(self._current_period)

        self._current_period.c_add_tick(tick_stamp, last_trade_price)

    cdef object c_aroon_up(self):
        cdef:
            list highs = [p.high for p in self._oscillator_periods]
            int last_high_index = -1
            object m = Decimal("-1")

        for i, elem in enumerate(highs):
            if elem >= m:
                m, last_high_index = elem, i
        return ((last_high_index + 1) /self._period_length) * 100

    cdef object c_aroon_down(self):
        cdef:
            list lows = [p.low for p in self._oscillator_periods]
            int last_low_index = -1
            object m = Decimal("Inf")

        for i, elem in enumerate(lows):
            if elem <= m:
                m, last_low_index = elem, i
        return ((last_low_index + 1) / self._period_length) * 100

    cdef object c_aroon_osc(self):
        return self.c_aroon_up() - self.c_aroon_down()
