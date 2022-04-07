from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType


class BalancerInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 gas_price: Decimal,
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
        self.trade_id_set = set()
        self._gas_price = gas_price

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"REJECTED"}

    @property
    def is_canceled(self) -> bool:
        return self.last_state in {"CANCELED", "EXPIRED"}

    @property
    def gas_price(self) -> Decimal:
        return self._gas_price

    @gas_price.setter
    def gas_price(self, gas_price) -> Decimal:
        self._gas_price = gas_price

    @classmethod
    def _instance_creation_parameters_from_json(cls, data: Dict[str, Any]) -> List[Any]:
        arguments: List[Any] = super()._instance_creation_parameters_from_json(data)
        arguments.insert(-1, None)
        return arguments
