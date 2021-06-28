from .base_trailing_indicator import BaseTrailingIndicator
import numpy as np
from decimal import Decimal

s_decimal_0 = Decimal("0")


class HistoricalVolatilityIndicator(BaseTrailingIndicator):
    def __init__(self, sampling_length: int = 30, processing_length: int = 15):
        super().__init__(sampling_length, processing_length)
        self._previous_sample = s_decimal_0

    def add_sample(self, value: float):
        self._previous_sample = self._sampling_buffer.get_last_value()
        self._sampling_buffer.add_value(value)
        indicator_value = self._indicator_calculation()
        if indicator_value:
            self._processing_buffer.add_value(indicator_value)

    def _indicator_calculation(self) -> float:
        if self._previous_sample:
            current_value = self._sampling_buffer.get_last_value()
            return (current_value / self._previous_sample) - 1

    def _processing_calculation(self) -> Decimal:
        return np.std(self._processing_buffer.get_as_numpy_array())
