from base_trailing_indicator import BaseTrailingIndicator
import pandas as pd


class ExponentialMovingAverageIndicator(BaseTrailingIndicator):
    def __init__(self, sampling_length: int = 30, processing_length: int = 1):
        if processing_length != 1:
            raise Exception("Exponential moving average processing_length should be 1")
        super().__init__(sampling_length, processing_length)

    def _indicator_calculation(self) -> float:
        ema = pd.Series(self._sampling_buffer.get_as_numpy_array())\
            .ewm(span=self._sampling_length, adjust=True).mean()
        return ema[-1]

    def _processing_calculation(self) -> float:
        return self._processing_buffer.get_last_value()
