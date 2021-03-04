from abc import ABC, abstractmethod
import numpy as np
import logging
from ..ring_buffer import RingBuffer

pmm_logger = None


class BaseTrailingIndicator(ABC):
    @classmethod
    def logger(cls):
        global pmm_logger
        if pmm_logger is None:
            pmm_logger = logging.getLogger(__name__)
        return pmm_logger

    def __init__(self, sampling_length: int = 30, processing_length: int = 15):
        self._sampling_length = sampling_length
        self._sampling_buffer = RingBuffer(sampling_length)
        self._processing_length = processing_length
        self._processing_buffer = RingBuffer(processing_length)

    def add_sample(self, value: float):
        self._sampling_buffer.add_value(value)
        indicator_value = self._indicator_calculation()
        self._processing_buffer.add_value(indicator_value)

    @abstractmethod
    def _indicator_calculation(self) -> float:
        raise NotImplementedError

    def _processing_calculation(self) -> float:
        """
        Processing of the processing buffer to return final value.
        Default behavior is buffer average
        """
        return np.mean(self._processing_buffer.get_as_numpy_array())

    @property
    def current_value(self) -> float:
        return self._processing_calculation()

    @property
    def is_sampling_buffer_full(self) -> bool:
        return self._sampling_buffer.is_full

    @property
    def is_processing_buffer_full(self) -> bool:
        return self._processing_buffer.is_full
