from decimal import Decimal
from typing import Optional

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import (
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
                 creation_timestamp: float,
                 initial_state: str = "LOCAL"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            creation_timestamp,
            initial_state,  # submitted, partial-filled, cancelling, filled, canceled, partial-canceled
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
