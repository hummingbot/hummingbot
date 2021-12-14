from decimal import Decimal
from typing import (
    Any,
    Dict
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


cdef class HuobiInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "submitted"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state  # submitted, partial-filled, cancelling, filled, canceled, partial-canceled
        )

        self.trade_id_set = set()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "canceled", "partial-canceled"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"partial-canceled", "canceled"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"canceled"}

    @property
    def is_open(self) -> bool:
        return self.last_state in {"submitted", "partial-filled"}

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
        trade_id = trade_update["tradeId"]
        if str(trade_update["orderId"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            return False
        self.trade_id_set.add(trade_id)
        trade_amount = Decimal(str(trade_update["tradeVolume"]))
        trade_price = Decimal(str(trade_update["tradePrice"]))
        quote_amount = trade_amount * trade_price

        self.executed_amount_base += trade_amount
        self.executed_amount_quote += quote_amount
        self.fee_paid += Decimal(str(trade_update["transactFee"]))
        self.fee_asset = trade_update["feeCurrency"].upper()

        if self.is_open:
            self.last_state = trade_update["orderStatus"]

        self.check_filled_condition()

        return True
