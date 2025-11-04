from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder


class EvedexPerpetualInFlightOrder(InFlightOrder):
    def __init__(
        self,
        client_order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        creation_timestamp: float,
        initial_state: str = "OPEN",
        leverage: int = 1,
        position: str = "LONG",
    ):
        super().__init__(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=creation_timestamp,
            initial_state=initial_state,
        )
        
        self.leverage = leverage
        self.position = position
        
    @property
    def is_done(self) -> bool:
        return self.is_filled or self.is_cancelled or self.is_failed
    
    @property
    def is_failure(self) -> bool:
        return self.is_failed
    
    @property
    def is_cancelled(self) -> bool:
        return self.current_state in ["CANCELLED", "EXPIRED"]
    
    def to_json(self) -> Dict[str, Any]:
        data = super().to_json()
        data.update({
            "leverage": self.leverage,
            "position": self.position,
        })
        return data
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "EvedexPerpetualInFlightOrder":
        order = cls(
            client_order_id=data["client_order_id"],
            exchange_order_id=data.get("exchange_order_id"),
            trading_pair=data["trading_pair"],
            order_type=OrderType[data["order_type"]],
            trade_type=TradeType[data["trade_type"]],
            price=Decimal(data["price"]),
            amount=Decimal(data["amount"]),
            creation_timestamp=data["creation_timestamp"],
            initial_state=data.get("initial_state", "OPEN"),
            leverage=data.get("leverage", 1),
            position=data.get("position", "LONG"),
        )
        
        if "executed_amount_base" in data:
            order.executed_amount_base = Decimal(data["executed_amount_base"])
        if "executed_amount_quote" in data:
            order.executed_amount_quote = Decimal(data["executed_amount_quote"])
        
        return order
