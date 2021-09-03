from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)

WORKING_LOCAL_STATUS = "WorkingLocal"


class NdaxInFlightOrderNotCreated(Exception):
    pass


class NdaxInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = WORKING_LOCAL_STATUS):
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
        self.fee_asset = self.base_asset if self.trade_type is TradeType.BUY else self.quote_asset
        self.trade_id_set = set()

    @property
    def is_locally_working(self) -> bool:
        return self.last_state in {WORKING_LOCAL_STATUS}

    @property
    def is_working(self) -> bool:
        return self.last_state in {"Working"}

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FullyExecuted", "Canceled", "Rejected", "Expired"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"Rejected"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"Canceled", "Expired"}

    def mark_as_filled(self):
        self.last_state = "FullyExecuted"

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
        trade_id = trade_update["TradeId"]
        if str(trade_update["OrderId"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            return False
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(str(trade_update["Quantity"]))
        self.executed_amount_quote += Decimal(str(trade_update["Value"]))
        return True
