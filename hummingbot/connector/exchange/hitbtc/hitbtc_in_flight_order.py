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

s_decimal_0 = Decimal(0)


class HitbtcInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "new"):
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
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "canceled", "expired"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"suspended"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"canceled", "expired"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        retval = HitbtcInFlightOrder(
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

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        Example Trade:
        {
            "id": "4345697765",
            "clientOrderId": "53b7cf917963464a811a4af426102c19",
            "symbol": "ETHBTC",
            "side": "sell",
            "status": "filled",
            "type": "limit",
            "timeInForce": "GTC",
            "quantity": "0.001",
            "price": "0.053868",
            "cumQuantity": "0.001",
            "postOnly": false,
            "createdAt": "2017-10-20T12:20:05.952Z",
            "updatedAt": "2017-10-20T12:20:38.708Z",
            "reportType": "trade",
        }
        ... Trade variables are only included after fills.
        {
            "tradeQuantity": "0.001",
            "tradePrice": "0.053868",
            "tradeId": 55051694,
            "tradeFee": "-0.000000005"
        }
        """
        self.executed_amount_base = Decimal(str(trade_update["cumQuantity"]))
        if self.executed_amount_base <= s_decimal_0:
            # No trades executed yet.
            return False
        trade_id = trade_update["updatedAt"]
        if trade_id in self.trade_id_set:
            # trade already recorded
            return False
        self.trade_id_set.add(trade_id)
        self.fee_paid += Decimal(str(trade_update.get("tradeFee", "0")))
        self.executed_amount_quote += (Decimal(str(trade_update.get("tradePrice", "0"))) *
                                       Decimal(str(trade_update.get("tradeQuantity", "0"))))
        if not self.fee_asset:
            self.fee_asset = self.quote_asset
        return True
