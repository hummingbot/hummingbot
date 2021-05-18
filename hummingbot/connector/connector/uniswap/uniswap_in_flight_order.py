from decimal import Decimal
from typing import (
    Dict,
    Any,
    Optional,
)
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


class UniswapInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
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
            initial_state,
        )
        self.trade_id_set = set()
        self._gas_price = gas_price

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        retval = UniswapInFlightOrder(
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
        return retval

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"REJECTED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED", "EXPIRED"}

    @property
    def gas_price(self) -> Decimal:
        return self._gas_price

    @gas_price.setter
    def gas_price(self, gas_price):
        self._gas_price = gas_price
