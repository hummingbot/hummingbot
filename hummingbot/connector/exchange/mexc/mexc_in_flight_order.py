from decimal import Decimal

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType


class MexcInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 initial_state: str = "NEW"):
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
