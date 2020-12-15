from typing import NamedTuple
from decimal import Decimal
from hummingbot.core.event.events import OrderType


class OpenOrder(NamedTuple):
    client_order_id: str
    trading_pair: str
    price: Decimal
    amount: Decimal
    executed_amount: Decimal
    status: str
    order_type: OrderType
    is_buy: bool
    time: int
    exchange_order_id: str
