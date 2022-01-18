from decimal import Decimal
from typing import (
    Any,
    Dict,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)


cdef class OkexInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "live",
                 creation_timestamp: int = -1):

        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state,  # submitted, partial-filled, cancelling, filled, canceled, partial-canceled
            creation_timestamp
        )

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "canceled"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"canceled"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"canceled"}

    @property
    def is_open(self) -> bool:
        return self.last_state in {"live", "partially_filled"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        return cls._baisc_from_json(data)
