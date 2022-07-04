# Order States
from decimal import Decimal

from hummingbot.core.data_type.in_flight_order import OrderState

ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "CLOSED": OrderState.FILLED,
    "PARTIAL": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

MIN_ORDER_SIZE = Decimal(10.0)
MIN_PRICE = Decimal(10.0)
MIN_QTY = Decimal(10.0)


POLKADEX_SS58_PREFIX = 88

UPDATE_ORDER_STATUS_MIN_INTERVAL = 10
