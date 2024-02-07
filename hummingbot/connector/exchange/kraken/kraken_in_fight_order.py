import copy
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate


class KrakenInFlightOrder(InFlightOrder):
    def __init__(
            self,
            client_order_id: str,
            trading_pair: str,
            order_type: OrderType,
            trade_type: TradeType,
            amount: Decimal,
            creation_timestamp: float,
            userref: int,
            price: Optional[Decimal] = None,
            exchange_order_id: Optional[str] = None,
            initial_state: OrderState = OrderState.PENDING_CREATE,
            leverage: int = 1,
            position: PositionAction = PositionAction.NIL,

    ) -> None:
        super().__init__(
            client_order_id,
            trading_pair,
            order_type,
            trade_type,
            amount,
            creation_timestamp,
            price,
            exchange_order_id,
            initial_state,
            leverage,
            position,
        )
        self.userref = userref

    @property
    def attributes(self) -> Tuple[Any]:
        return copy.deepcopy(
            (
                self.client_order_id,
                self.trading_pair,
                self.order_type,
                self.trade_type,
                self.price,
                self.amount,
                self.exchange_order_id,
                self.current_state,
                self.leverage,
                self.position,
                self.userref,
                self.executed_amount_base,
                self.executed_amount_quote,
                self.creation_timestamp,
                self.last_update_timestamp,
            )
        )

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "InFlightOrder":
        """
        Initialize an InFlightOrder using a JSON object
        :param data: JSON data
        :return: Formatted InFlightOrder
        """
        order = KrakenInFlightOrder(
            client_order_id=data["client_order_id"],
            trading_pair=data["trading_pair"],
            order_type=getattr(OrderType, data["order_type"]),
            trade_type=getattr(TradeType, data["trade_type"]),
            amount=Decimal(data["amount"]),
            price=Decimal(data["price"]),
            exchange_order_id=data["exchange_order_id"],
            initial_state=OrderState(int(data["last_state"])),
            leverage=int(data["leverage"]),
            position=PositionAction(data["position"]),
            creation_timestamp=data.get("creation_timestamp", -1),
            userref=data.get("userref", 0)
        )
        order.executed_amount_base = Decimal(data["executed_amount_base"])
        order.executed_amount_quote = Decimal(data["executed_amount_quote"])
        order.order_fills.update({key: TradeUpdate.from_json(value)
                                  for key, value
                                  in data.get("order_fills", {}).items()})
        order.last_update_timestamp = data.get("last_update_timestamp", order.creation_timestamp)

        order.check_filled_condition()
        order.check_processed_by_exchange_condition()

        return order

    def to_json(self) -> Dict[str, Any]:
        """
        Returns this InFlightOrder as a JSON object.
        :return: JSON object
        """
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "last_state": str(self.current_state.value),
            "leverage": str(self.leverage),
            "position": self.position.value,
            "userref": self.userref,
            "creation_timestamp": self.creation_timestamp,
            "last_update_timestamp": self.last_update_timestamp,
            "order_fills": {key: fill.to_json() for key, fill in self.order_fills.items()}
        }
