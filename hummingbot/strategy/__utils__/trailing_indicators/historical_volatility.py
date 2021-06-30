from .base_trailing_indicator import BaseTrailingIndicator
import numpy as np


class HistoricalVolatilityIndicator(BaseTrailingIndicator):
    def __init__(self, sampling_length: int = 30, processing_length: int = 15):
        super().__init__(sampling_length, processing_length)

    def _indicator_calculation(self) -> float:
        prices = self._sampling_buffer.get_as_numpy_array()
        if prices.size > 0:
            log_returns = np.diff(np.log(prices))
            return np.var(log_returns)

    def _processing_calculation(self) -> float:
        processing_array = self._processing_buffer.get_as_numpy_array()
        if processing_array.size > 0:
            return np.sqrt(np.mean(np.nan_to_num(processing_array)))
