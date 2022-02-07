from decimal import Decimal
from typing import (
    Any,
    Dict,
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase


class MexcInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "NEW"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state  # submitted, partial-filled, cancelling, filled, canceled, partial-canceled
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
        retval = MexcInFlightOrder(
            client_order_id=data["client_order_id"],
            exchange_order_id=data["exchange_order_id"],
            trading_pair=data["trading_pair"],
            order_type=getattr(OrderType, data["order_type"]),
            trade_type=getattr(TradeType, data["trade_type"]),
            price=Decimal(data["price"]),
            amount=Decimal(data["amount"]),
            initial_state=data["last_state"]
        )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        retval.last_state = data["last_state"]
        return retval
