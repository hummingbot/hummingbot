import math
import time
from typing import Optional

from hummingbot.core.data_type.limit_order import LimitOrder


def order_age(order: LimitOrder, current_time: Optional[float] = None) -> int:
    """
    Get the age of a limit order in second.
    :param order: the order to calculate the age for
    :param current_time: the current time in seconds. If not specified the function will take the machine time
    :return: number of seconds since the order was created until the current time
    """
    now = current_time if current_time is not None and not math.isnan(current_time) else _time()
    return int(now - (order.creation_timestamp / 1e6))


def _time() -> float:
    return time.time()
