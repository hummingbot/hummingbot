import asyncio

from decimal import Decimal
from typing import Any, Dict

from hummingbot.connector.exchange.idex.utils import from_idex_order_type, from_idex_trade_type
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


class IdexInFlightOrder(InFlightOrderBase):
    """
    TODO: Test it
    """

    def __init__(self,
                 order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "open"):
        """

        :param order_id:
        :param exchange_order_id:
        :param trading_pair:
        :param order_type:
        :param trade_type:
        :param price:
        :param amount:
        :param initial_state:  open, partiallyFilled, filled, canceled, rejected
        """
        super().__init__(
            order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state,
        )
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "canceled", "rejected"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"rejected", }

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"canceled", }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder

        TODO: Validate it
        """
        result = IdexInFlightOrder(
            data["orderId"],
            "",
            data["market"],
            from_idex_order_type(data["type"]),
            from_idex_trade_type(data["side"]),
            Decimal(data["price"]),
            Decimal(data["executedQuantity"]),
            data["status"]
        )

        # TODO: How to normalize fills array
        # TODO: Take gas into account, just add together
        # result.executed_amount_base = Decimal(data["executed_amount_base"])
        # result.executed_amount_quote = Decimal(data["executed_amount_quote"])
        # result.fee_asset = data["fee_asset"] # Asset is always same
        # result.fee_paid = Decimal(data["fee_paid"]) # Sum it
        # result.last_state = data["last_state"]
        return result

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["tradeId"]
        # trade_update["orderId"] is type int
        if str(trade_update["order_id"]) != self.order_id or trade_id in self.trade_id_set:
            # trade already recorded
            return False
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(str(trade_update["executedQuantity"]))
        self.fee_paid += Decimal(str(trade_update["fee"]))
        self.executed_amount_quote += (Decimal(str(trade_update["price"])) *
                                       Decimal(str(trade_update["executedQuantity"])))
        if not self.fee_asset:
            self.fee_asset = trade_update["fee_currency"]
        return True
