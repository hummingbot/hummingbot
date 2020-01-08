import time

_last_tracking_nonce: int = 0


# This tracking nonce is needed bc resolution for time.time() on Windows is very low (16ms),
# not good enough to create unique order_id.
def get_tracking_nonce() -> int:
    global _last_tracking_nonce
    nonce = int(time.time() * 1e6)
    _last_tracking_nonce = nonce if nonce > _last_tracking_nonce else _last_tracking_nonce + 1
    return _last_tracking_nonce
