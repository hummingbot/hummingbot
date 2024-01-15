import math
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType

s_decimal_0 = Decimal(0)


class KrakenInFlightOrderNotCreated(Exception):
    pass


cdef class KrakenInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 userref: int,
                 initial_state: str = "local"):
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
        self.userref = userref

    @property
    def is_local(self) -> bool:
        return self.last_state in {"local"}

    @property
    def is_done(self) -> bool:
        return self.last_state in {"closed", "canceled", "expired"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"canceled", "expired"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"canceled"}

    @classmethod
    def _instance_creation_parameters_from_json(cls, data: Dict[str, Any]) -> List[Any]:
        arguments: List[Any] = super()._instance_creation_parameters_from_json(data)
        arguments.insert(-1, data["userref"])
        return arguments

    def to_json(self):
        json = super().to_json()
        json.update({"userref": self.userref})
        return json

    def update_exchange_order_id(self, exchange_id: str):
        super().update_exchange_order_id(exchange_id)
        self.last_state = "new"

    def _mark_as_filled(self):
        """
        Updates the status of the InFlightOrder as filled.
        Note: Should only be called when order is completely filled.
        """
        self.last_state = "closed"

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updartes the InFlightOrder with the trade update (from WebSocket API ownTrades stream)
        :return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["trade_id"]
        if str(trade_update["ordertxid"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            # trade already recorded
            return False
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(trade_update["vol"])
        self.fee_paid += Decimal(trade_update["fee"])
        self.executed_amount_quote += Decimal(trade_update["vol"]) * Decimal(trade_update["price"])
        if not self.fee_asset:
            self.fee_asset = self.quote_asset
        if (math.isclose(self.executed_amount_base, self.amount) or self.executed_amount_base >= self.amount):
            self._mark_as_filled()
        return True
