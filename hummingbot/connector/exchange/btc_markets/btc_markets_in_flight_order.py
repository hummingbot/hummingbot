import asyncio
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


class BtcMarketsInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
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
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"Fully Matched", "Cancelled", "REJECTED", "EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"Failed", "REJECTED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"Cancelled", "Partially Cancelled"}

    @property
    def is_open(self) -> bool:
        return self.last_state in {"Accepted", "Partially Matched"}

    # @property
    # def order_type_description(self) -> str:
    #     """
    #     :return: Order description string . One of ["limit buy" / "limit sell" / "market buy" / "market sell"]
    #     """
    #     order_type = "market" if self.order_type is OrderType.MARKET else "limit"
    #     side = "buy" if self.trade_type == TradeType.BUY else "sell"
    #     return f"{order_type} {side}"

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        """

        # trade_update["orderId"] is type int
        if str(trade_update["orderId"]) != self.exchange_order_id in self.trade_id_set:
            # trade already recorded
            return False

        if trade_update["status"] in ["Fully Matched", "Partially Matched"]:
            # if trade_update received via WS, may have multiple trades
            if trade_update["trades"]:
                for trade in trade_update["trades"]:
                    self.trade_id_set.add(trade["tradeId"])
                    self.executed_amount_base += Decimal(str(trade["volume"]))
                    if "fee" in trade:
                        self.fee_paid += Decimal(str(trade["fee"]))
                    self.executed_amount_quote += (Decimal(str(trade["price"])) *
                                                   Decimal(str(trade["volume"])))
            # if trade_update received via REST list orders, no trade break down
            # else:

        if self.is_open:
            self.last_state = trade_update["status"]

        self.check_filled_condition()
        return True
