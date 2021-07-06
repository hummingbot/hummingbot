from .base_trailing_indicator import BaseTrailingIndicator
import numpy as np


class InstantVolatilityIndicator(BaseTrailingIndicator):
    def __init__(self, sampling_length: int = 30, processing_length: int = 15):
        super().__init__(sampling_length, processing_length)

    def _indicator_calculation(self) -> float:
        return np.var(self._sampling_buffer.get_as_numpy_array())

    def _processing_calculation(self) -> float:
        processing_array = self._processing_buffer.get_as_numpy_array()
        return np.sqrt(np.mean(processing_array))
