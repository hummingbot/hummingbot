from .base_trailing_indicator import BaseTrailingIndicator
import numpy as np

class PriceRangeIndicator(BaseTrailingIndicator):
    def __init__(self, sampling_length: int = 30, processing_length: int = 15):
        super().__init__(sampling_length, processing_length)

    def _indicator_calculation(self) -> float:
        np_sampling_buffer = self._sampling_buffer.get_as_numpy_array()
        high = np.max(np_sampling_buffer)
        low = np.min(np_sampling_buffer)
        calculated = high - low
        return calculated

    def _processing_calculation(self) -> float:
        # Only the last calculated value, not an average of multiple past values
        return self._processing_buffer.get_last_value()

    def _high(self) -> float:
        np_sampling_buffer = self._sampling_buffer.get_as_numpy_array()
        if np_sampling_buffer.size == 0:
            return 0
        high = np.max(np_sampling_buffer)
        return high

    def _low(self) -> float:
        np_sampling_buffer = self._sampling_buffer.get_as_numpy_array()
        if np_sampling_buffer.size == 0:
            return 0
        low = np.min(np_sampling_buffer)
        return low

    def _buffer_size(self) -> int:
        buffer_len = len(self._sampling_buffer.get_as_numpy_array())
        return buffer_len

    @property
    def high(self) -> float:
        return self._high()

    @property
    def low(self) -> float:
        return self._low()

    @property
    def buffer_size(self) -> int:
        return self._buffer_size()
