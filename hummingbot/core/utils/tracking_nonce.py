import time

_last_tracking_nonce: int = 0
_last_tracking_nonce_low_res: int = 0
_last_tracking_nonce_short: int = 0

nonce_multiplier_power = 2  # a power of 2 allows the creation of 100 unique order IDs in a given second
_nonce_multiplier = 10 ** nonce_multiplier_power


def get_tracking_nonce() -> int:
    global _last_tracking_nonce
    nonce = int(time.time() * 1e6)
    _last_tracking_nonce = nonce if nonce > _last_tracking_nonce else _last_tracking_nonce + 1
    return _last_tracking_nonce


def get_tracking_nonce_low_res() -> int:
    global _last_tracking_nonce_low_res
    nonce = int(time.time() * 1e3)
    _last_tracking_nonce_low_res = nonce if nonce > _last_tracking_nonce_low_res else _last_tracking_nonce_low_res + 1
    return _last_tracking_nonce_low_res


def get_tracking_nonce_short() -> int:
    global _last_tracking_nonce_short
    nonce = int(int(_time()) * _nonce_multiplier)
    _last_tracking_nonce_short = nonce if nonce > _last_tracking_nonce_short else _last_tracking_nonce_short + 1
    return _last_tracking_nonce_short


def _time():
    """For mocking in unit-tests."""
    return time.time()
