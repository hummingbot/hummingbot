import asyncio
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import (
    OrderType,
    TradeType
)


class ProbitInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 initial_state: str = "open",
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
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "cancelled"}

    @property
    def is_failure(self) -> bool:
        # TODO: ProBit does not have a 'fail' order status.
        return NotImplementedError

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"cancelled"}

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from GET /trade_history end point)
        return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["id"]
        if str(trade_update["order_id"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            return False
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(str(trade_update["quantity"]))
        self.fee_paid += Decimal(str(trade_update["fee_amount"]))
        self.executed_amount_quote += Decimal(str(trade_update["cost"]))
        if not self.fee_asset:
            self.fee_asset = trade_update["fee_currency_id"]
        return True
