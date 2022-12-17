from collections import deque
from decimal import Decimal
from typing import Deque, Literal, Optional

from juno.math import minmax
from juno.models import Candle

from .changed_filter import ChangedFilter
from .simple_moving_average import SimpleMovingAverage

Advice = Literal["Long", "Short", "Liquidate"]


class FourWeekRule:
    """
    The weekly rule, in its simplest form, buys when prices reach a new four-week high and sells when prices reach a
    new four-week low.
    """

    _changed_filter: ChangedFilter
    _moving_average: SimpleMovingAverage
    _prices: Deque[Decimal]

    def __init__(
        self,
        period: int = 28,
        # Moving average period is normally half the period.
        moving_average_period: int = 14,
    ) -> None:
        self._changed_filter = ChangedFilter()
        self._moving_average = SimpleMovingAverage(period=moving_average_period)
        self._prices = deque(maxlen=period)

    @property
    def value(self) -> Optional[Advice]:
        return self._changed_filter.value

    def update(self, candle: Candle) -> Optional[Advice]:
        price = candle.close

        self._moving_average.update(price)
        self._prices.append(price)

        value = None
        lowest, highest = minmax(self._prices)
        if price >= highest:
            value = "Long"
        elif price <= lowest:
            value = "Short"
        elif (self._changed_filter.prevailing_value == "Long" and price <= self._moving_average.value) or (
            self._changed_filter.prevailing_value == "Short" and price >= self._moving_average.value
        ):
            value = "Liquidate"
        return self._changed_filter.update(value)
