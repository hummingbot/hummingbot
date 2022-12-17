from collections import deque
from decimal import Decimal
from typing import Deque


class SimpleMovingAverage:
    """
    Calculated by taking the arithmetic mean of a given set of values over a specified period.
    """

    _prices: Deque[Decimal]
    _value: Decimal = Decimal("0.0")

    @property
    def value(self) -> Decimal:
        return self._value

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError(f"Period must be longer than zero; got {period}.")

        self._prices = deque(maxlen=period)

    def update(self, price: Decimal) -> Decimal:
        self._prices.append(price)
        self._value = sum(self._prices, Decimal("0.0")) / len(self._prices)
        return self._value
