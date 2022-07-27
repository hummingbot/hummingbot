import asyncio
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.exchange.k2.k2_utils import convert_from_exchange_trading_pair
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType


class K2InFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: int,
                 initial_state: str = "New",
                 ):
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
        self.last_executed_amount_base = Decimal("nan")
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"Filled", "Cancelled"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"No Balance"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"Cancelled", "Expired"}

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Update the InFlightOrder with the trade update from Private/GetHistory API endpoint
        return: True if the order gets updated successfully otherwise False
        """
        trade_id: str = str(trade_update["id"])
        trade_order_id: str = str(trade_update["orderid"])

        if trade_order_id != self.exchange_order_id or trade_id in self.trade_id_set:
            return False

        self.trade_id_set.add(trade_id)

        trade_price: Decimal = Decimal(str(trade_update["price"]))
        trade_amount: Decimal = Decimal(str(trade_update["amount"]))

        if trade_update["type"] == "Buy":
            self.executed_amount_base += trade_amount
            self.executed_amount_quote += trade_price * trade_amount
        else:
            self.executed_amount_quote += trade_amount
            self.executed_amount_base += trade_amount / trade_price

        self.fee_paid += Decimal(str(trade_update["fee"]))

        if not self.fee_asset:
            base, quote = convert_from_exchange_trading_pair(trade_update["symbol"]).split("-")
            self.fee_asset = base if trade_update["type"] == "Buy" else quote

        return True
