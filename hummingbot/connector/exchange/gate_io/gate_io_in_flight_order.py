import asyncio
from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import OrderType, TradeType

s_decimal_0 = Decimal(0)


class GateIoInFlightOrder(InFlightOrderBase):
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
        self.trade_update_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"closed", "filled", "finish", "failed", "cancelled", "expired"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"failed"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"cancelled", "expired"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        retval = GateIoInFlightOrder(
            data["client_order_id"],
            data["exchange_order_id"],
            data["trading_pair"],
            getattr(OrderType, data["order_type"]),
            getattr(TradeType, data["trade_type"]),
            Decimal(data["price"]),
            Decimal(data["amount"]),
            data["last_state"],
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
            "id": 1234567890,
            "user_id": 1234567,
            "order_id": "96780687179",
            "currency_pair": "ETH_USDT",
            "create_time": 1637764970,
            "create_time_ms": "1637764970928.48",
            "side": "buy",
            "amount": "0.005",
            "role": "maker",
            "price": "4191.1",
            "fee": "0.000009",
            "fee_currency": "ETH",
            "point_fee": "0",
            "gt_fee": "0",
            "text": "t-HBOT-B-EHUT1637764969004024",
        }
        """

        trade_id = str(trade_update["id"])
        if trade_id in self.trade_update_id_set:
            # trade already recorded
            return False

        self.trade_update_id_set.add(trade_id)

        # Set executed amounts
        trade_executed_base = Decimal(str(trade_update.get("amount", "0")))
        self.executed_amount_base += trade_executed_base
        if self.executed_amount_base <= s_decimal_0:
            # No trades executed yet.
            return False
        self.fee_paid += Decimal(str(trade_update.get("fee", "0")))
        self.executed_amount_quote += Decimal(str(trade_update.get("price", "0"))) * trade_executed_base
        self.fee_asset = trade_update["fee_currency"]
        return True
