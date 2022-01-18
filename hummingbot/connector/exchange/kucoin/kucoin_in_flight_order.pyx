from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)


class KucoinInFlightOrderNotCreated(Exception):
    pass


cdef class KucoinInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "LOCAL",
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
        return self.last_state in {"DONE", "CANCEL"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"CANCEL"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCEL"}

    @property
    def is_local(self) -> bool:
        return self.last_state in {"LOCAL"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        return cls._basic_from_json(data)
