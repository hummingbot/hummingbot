import math
from decimal import Decimal

# These classes are responsible for storing and calculating the state of the Aroon Indicators
# OscillatorPeriod: represents a single period in the Oscillator data. The class stores the high and low
#   trade executions in that period
#
# AroonOscillatorIndicator: the main class that stores and calculates the Indicator data.
#   The indicator class stores a list of OscillatorPeriods that it uses to calculate the indicators.
#   The strategy will use c_add_tick method to add the last_trade price data into the indicator.
#   The indicator will then create new OscillatorPeriods based on the configured period_durations.
#   It will fill up until it hits period_length, and then it acts like a FIFO queue.
#   Aroon Up indicator is a value of 0 to 100 indicating how recently the highest high
#     period occured in the data window. 100 indicates it has just hit the highest high.
#     the formula is: Aroon Up = 100 ∗ (period_length − "Periods Since 25 Period High") / period_length
#   Aroon Down indicator is a value of 0 to 100 indicating how recently the lowest low
#     period occured in the data window. 100 indicates it has just hit the lowest low.
#     the formula is: Aroon Down = 100 ∗ (period_length − "Periods Since 25 Period Low") / period_length
#   Aroon Oscillator indicator is the difference between the Up and Down indicator. The value ranges
#     from -100 to 100. A value of 100 strongly indicates a current uptrend, and -100 strongly indicates a
#     current downtrend.
#     formula is: Aroon Oscillator = Aroon Up - Aroon Down
#
#   More info on Aroon Indicators can be found at:
#       https://www.investopedia.com/terms/a/aroonoscillator.asp
#       https://school.stockcharts.com/doku.php?id=technical_indicators:aroon

cdef class OscillatorPeriod:

    def __init__(self, double start_tick, double end_tick):
        self._high = Decimal('-1')
        self._low = Decimal('Inf')
        self._start = start_tick
        self._end = end_tick

    cdef c_add_tick(self, object price):
        if math.isnan(price):
            return
        self._high = max(self._high, price)

        self._low = min(self._low, price)

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
        if self._current_period is None or tick_stamp >= self._current_period.end:
            if self.c_full():
                self._oscillator_periods.pop(0)

            end_time = tick_stamp + self._period_duration
            new_period = OscillatorPeriod(tick_stamp, end_time)
            self._oscillator_periods.append(new_period)
            self._current_period = new_period

        self._current_period.c_add_tick(last_trade_price)

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

    cdef int c_aroon_period_count(self):
        return len(self._oscillator_periods)

    cdef list c_aroon_periods(self):
        return self._oscillator_periods

    cdef OscillatorPeriod c_last_period(self):
        return self._current_period
