from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)
import asyncio
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from .altmarkets_constants import Constants

s_decimal_0 = Decimal(0)


class AltmarketsInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
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
            initial_state,  # submitted, partial-filled, cancelling, filled, canceled, partial-canceled
        )
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in Constants.ORDER_STATES['DONE']

    @property
    def is_failure(self) -> bool:
        return self.last_state in Constants.ORDER_STATES['FAIL']

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in Constants.ORDER_STATES['CANCEL']

    # @property
    # def order_type_description(self) -> str:
    #     """
    #     :return: Order description string . One of ["limit buy" / "limit sell" / "market buy" / "market sell"]
    #     """
    #     order_type = "market" if self.order_type is OrderType.MARKET else "limit"
    #     side = "buy" if self.trade_type == TradeType.BUY else "sell"
    #     return f"{order_type} {side}"

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        retval = AltmarketsInFlightOrder(
            data["client_order_id"],
            data["exchange_order_id"],
            data["trading_pair"],
            getattr(OrderType, data["order_type"]),
            getattr(TradeType, data["trade_type"]),
            Decimal(data["price"]),
            Decimal(data["amount"]),
            data["last_state"]
        )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        retval.last_state = data["last_state"]
        return retval

    def update_with_order_update(self, order_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        Example Order:
        {
            "id": 9401,
            "market": "rogerbtc",
            "kind": "ask",
            "side": "sell",
            "ord_type": "limit",
            "price": "0.00000099",
            "avg_price": "0.00000099",
            "state": "wait",
            "origin_volume": "7000.0",
            "remaining_volume": "2810.1",
            "executed_volume": "4189.9",
            "at": 1596481983,
            "created_at": 1596481983,
            "updated_at": 1596553643,
            "trades_count": 272
        }
        """
        # Update order execution status
        self.last_state = order_update["state"]
        # Update order
        executed_price = Decimal(str(order_update.get("price")
                                     if order_update.get("price") is not None
                                     else order_update.get("avg_price", "0")))
        self.executed_amount_base = Decimal(str(order_update["executed_volume"]))
        self.executed_amount_quote = (executed_price * self.executed_amount_base) \
            if self.executed_amount_base > s_decimal_0 else s_decimal_0
        if self.executed_amount_base <= s_decimal_0:
            # No trades executed yet.
            return False
        trade_id = f"{order_update['id']}-{order_update['updated_at']}"
        if trade_id in self.trade_id_set:
            # trade already recorded
            return False
        self.trade_id_set.add(trade_id)
        self.fee_paid += order_update.get("trade_fee") * self.executed_amount_base
        if not self.fee_asset:
            self.fee_asset = self.quote_asset
        return True

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        Example Trade:
        {
            "amount":"1.0",
            "created_at":1615978645,
            "id":9618578,
            "market":"rogerbtc",
            "order_id":2324774,
            "price":"0.00000004",
            "side":"sell",
            "taker_type":"sell",
            "total":"0.00000004"
        }
        """
        self.executed_amount_base = Decimal(str(trade_update.get("amount", "0")))
        self.executed_amount_quote = Decimal(str(trade_update.get("total", "0")))
        if self.executed_amount_base <= s_decimal_0:
            # No trades executed yet.
            return False
        trade_id = f"{trade_update['order_id']}-{trade_update['created_at']}"
        if trade_id in self.trade_id_set:
            # trade already recorded
            return False
        trade_update["exchange_trade_id"] = trade_update["id"]
        self.trade_id_set.add(trade_id)
        self.fee_paid += trade_update.get("trade_fee") * self.executed_amount_base
        if not self.fee_asset:
            self.fee_asset = self.quote_asset
        return True
