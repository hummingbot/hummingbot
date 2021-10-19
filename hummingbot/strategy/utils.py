import time

from hummingbot.core.data_type.limit_order import LimitOrder


def order_age(order: LimitOrder) -> float:
    """
    Get the age of a limit order in second, not applicable to paper trade orders
    """
    if "//" not in order.client_order_id:
        return int(time.time()) - int(order.client_order_id[-16:]) / 1e6
    return -1.
