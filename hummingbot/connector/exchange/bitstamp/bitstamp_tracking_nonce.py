import time

_last_tracking_nonce: int = int(time.time() * 1e6)


def get_tracking_nonce() -> str:
    global _last_tracking_nonce
    _last_tracking_nonce += 1
    return str(_last_tracking_nonce)
