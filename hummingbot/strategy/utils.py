import time

from hummingbot.core.data_type.limit_order import LimitOrder


def order_age(order: LimitOrder) -> float:
    """
    Get the age of a limit order in second, not applicable to paper trade orders
    """
    if "//" not in order.client_order_id:
        return int(_time() - (order.creation_timestamp / 1e6))
    return -1.


def _time() -> float:
    return time.time()
