from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType


class PerpetualFinanceInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 leverage: int,
                 position: str,
                 initial_state: str = "OPEN"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            creation_timestamp,
            initial_state,
        )
        self.leverage = leverage
        self.position = position

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"REJECTED"}

    @property
    def is_canceled(self) -> bool:
        return self.last_state in {"CANCELED", "EXPIRED"}

    def to_json(self):
        json = super().to_json()
        json.update({
            "leverage": self.leverage,
            "position": self.position,
        })
        return json

    @classmethod
    def _instance_creation_parameters_from_json(cls, data: Dict[str, Any]) -> List[Any]:
        arguments: List[Any] = super()._instance_creation_parameters_from_json(data)
        arguments.insert(-1, int(data["leverage"]))
        arguments.insert(-1, data["position"])
        return arguments
