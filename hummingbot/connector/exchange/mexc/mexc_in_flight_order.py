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


class MexcInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "NEW",
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
        self.fee_asset = self.quote_asset

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "PARTIALLY_CANCELED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED", "PARTIALLY_CANCELED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"CANCELED", "PARTIALLY_CANCELED"}

    @property
    def is_open(self) -> bool:
        return self.last_state in {"NEW", "PARTIALLY_FILLED"}

    def mark_as_filled(self):
        self.last_state = "FILLED"

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        return cls._basic_from_json(data)
