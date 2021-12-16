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


cdef class LiquidInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "live"):
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

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "cancelled"}

    @property
    def is_failure(self) -> bool:
        # This is the only known canceled state
        return self.last_state == "cancelled"

    @property
    def is_cancelled(self) -> bool:
        return self.last_state == "cancelled"

    @property
    def order_type_description(self) -> str:
        """
        :return: Order description string . One of ["limit buy" / "limit sell" / "market buy" / "market sell"]
        """
        order_type = "limit_maker" if self.order_type is OrderType.LIMIT_MAKER else "limit"
        side = "buy" if self.trade_type == TradeType.BUY else "sell"
        return f"{order_type} {side}"

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
        :param trade_update: the event message received for the order fill (or trade event)
        :return: True if the order gets updated otherwise False
        """
        update_id = trade_update["updated_at"]
        total_filled_amount = Decimal(str(trade_update["filled_quantity"]))

        if update_id in self.trade_id_set or total_filled_amount <= self.executed_amount_base:
            return False

        self.trade_id_set.add(update_id)
        trade_amount = total_filled_amount - self.executed_amount_base
        trade_price = Decimal(str(trade_update["price"]))
        quote_amount = trade_amount * trade_price

        self.executed_amount_base += trade_amount
        self.executed_amount_quote += quote_amount
        # According to Liquid support team they inform fee in a cumulative way
        self.fee_paid = Decimal(str(trade_update["order_fee"]))
        self.fee_asset = trade_update["funding_currency"]

        return True
