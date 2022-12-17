from time import time
from typing import Callable

from tenacity import RetryCallState
from tenacity.stop import stop_base
from tenacity.wait import wait_base, wait_chain, wait_exponential, wait_none


class stop_after_attempt_with_reset(stop_base):
    """
    Stop when the previous attempt >= max_attempt. Reset attempt count after time_to_reset seconds.
    """

    def __init__(
        self,
        max_attempt_number: int,
        time_to_reset: float,
        get_time: Callable[[], float] = time,
    ) -> None:
        self._max_attempt_number = max_attempt_number
        self._time_to_reset = time_to_reset
        self._get_time = get_time
        self._last_attempt_at = 0.0
        self._attempt_offset = 0

    def __call__(self, retry_state: RetryCallState) -> bool:
        now = self._get_time()
        if now - self._last_attempt_at >= self._time_to_reset:
            self._attempt_offset = retry_state.attempt_number - 1
        self._last_attempt_at = now
        return retry_state.attempt_number - self._attempt_offset >= self._max_attempt_number


def wait_none_then_exponential() -> wait_base:
    return wait_chain(wait_none(), wait_exponential())
