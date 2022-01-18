from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional, List,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)


class BybitPerpetualInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 leverage: int,
                 position: str,
                 initial_state: str = "Created"):
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
        self.fee_asset = self.quote_asset if self.quote_asset == "USDT" else self.base_asset
        self.trade_id_set = set()
        self.leverage = leverage
        self.position = position

    @property
    def is_done(self) -> bool:
        return self.last_state in {"Filled", "Canceled", "Rejected"}

    @property
    def is_failure(self) -> bool:
        return self.last_state == "Rejected"

    @property
    def is_cancelled(self) -> bool:
        return self.last_state == "Cancelled"

    @property
    def is_created(self) -> bool:
        return self.last_state == "Created"

    @property
    def is_new(self) -> bool:
        return self.last_state == "New"

    @property
    def is_filled(self) -> bool:
        return self.last_state == "Filled"

    def mark_as_filled(self):
        self.last_state = "Filled"

    def to_json(self) -> Dict[str, Any]:
        json = super().to_json()
        json.update({"leverage": str(self.leverage), "position": self.position})
        return json

    @classmethod
    def _instance_creation_parameters_from_json(cls, data: Dict[str, Any]) -> List[Any]:
        arguments: List[Any] = super()._instance_creation_parameters_from_json(data)
        arguments.insert(-1, int(data["leverage"]))
        arguments.insert(-1, data["position"])
        return arguments

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        return cls._basic_from_json(data)

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from GET /trade_history end point)
        return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["exec_id"]
        if str(trade_update["order_id"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            return False
        self.trade_id_set.add(trade_id)
        trade_amount = Decimal(str(trade_update["exec_qty"]))
        trade_price = (Decimal(str(trade_update["exec_price"]))
                       if "exec_price" in trade_update
                       else Decimal(str(trade_update["price"])))
        quote_amount = trade_amount * trade_price if self.quote_asset == "USDT" else trade_amount / trade_price

        self.executed_amount_base += trade_amount
        self.executed_amount_quote += quote_amount
        self.fee_paid += Decimal(str(trade_update.get("exec_fee")))
        return True
