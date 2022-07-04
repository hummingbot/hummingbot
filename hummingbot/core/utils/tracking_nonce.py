import time
import warnings
from typing import Optional, Union


class NonceCreator:
    def __init__(self):
        self._last_tracking_nonce = 0
        self._last_tracking_nonce_low_res = 0

    def get_tracking_nonce(self, ts_us: Optional[Union[float, int]] = None) -> int:
        nonce = int(ts_us if ts_us is not None else self._time() * 1e6)
        self._last_tracking_nonce = nonce if nonce > self._last_tracking_nonce else self._last_tracking_nonce + 1
        return self._last_tracking_nonce

    def get_tracking_nonce_low_res(self, ts_us: Optional[Union[float, int]] = None) -> int:
        nonce = int(ts_us if ts_us is not None else self._time() * 1e3)
        self._last_tracking_nonce_low_res = (
            nonce if nonce > self._last_tracking_nonce_low_res else self._last_tracking_nonce_low_res + 1
        )
        return self._last_tracking_nonce_low_res

    @staticmethod
    def _time() -> float:
        """Mocked in test cases without affecting system `time.time()`."""
        return time.time()


_nonce_provider = NonceCreator()


def get_tracking_nonce() -> int:
    # todo: remove
    warnings.warn(
        message=f"This method has been deprecate in favor of {NonceCreator.__class__.__name__}.",
        category=DeprecationWarning,
    )
    ts_us = int(time.time() * 1e6)
    nonce = _nonce_provider.get_tracking_nonce(ts_us)
    return nonce


def get_tracking_nonce_low_res() -> int:
    # todo: remove
    warnings.warn(
        message=f"This method has been deprecate in favor of {NonceCreator.__class__.__name__}.",
        category=DeprecationWarning,
    )
    ts_us = int(time.time() * 1e3)
    nonce = _nonce_provider.get_tracking_nonce_low_res(ts_us)
    return nonce
