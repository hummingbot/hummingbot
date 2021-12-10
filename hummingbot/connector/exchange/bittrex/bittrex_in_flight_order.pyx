from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import OrderType, TradeType


cdef class BittrexInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "OPEN"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state
        )

        self.trade_id_set = set()
        self.fee_asset = self.quote_asset

    @property
    def is_done(self) -> bool:
        return self.last_state in {"CLOSED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"CANCELLED", "FAILURE"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELLED"}

    @property
    def order_type_description(self) -> str:
        order_type = "limit" if self.order_type is OrderType.LIMIT else "limit_maker"
        side = "buy" if self.trade_type is TradeType.BUY else "sell"
        return f"{order_type} {side}"

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        order = cls._basic_from_json(data)
        order.check_filled_condition()
        return order

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from GET /trade_history end point)
        :param trade_update: the event message received for the order fill (or trade event)
        :return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["id"]
        if str(trade_update["orderId"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            return False
        self.trade_id_set.add(trade_id)
        trade_amount = abs(Decimal(str(trade_update["quantity"])))
        trade_price = Decimal(str(trade_update["rate"]))
        quote_amount = trade_amount * trade_price

        self.executed_amount_base += trade_amount
        self.executed_amount_quote += quote_amount
        self.fee_paid += Decimal(str(trade_update["commission"]))

        self.check_filled_condition()

        return True
