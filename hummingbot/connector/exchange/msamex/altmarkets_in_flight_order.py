import asyncio
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType
from .msamex_constants import Constants

s_decimal_0 = Decimal(0)


class mSamexInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 initial_state: str = "local"):
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
        return self.last_state in Constants.ORDER_STATES['DONE']

    @property
    def is_failure(self) -> bool:
        return self.last_state in Constants.ORDER_STATES['FAIL']

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in Constants.ORDER_STATES['CANCEL']

    @property
    def is_local(self) -> bool:
        return self.last_state == "local"

    def update_exchange_order_id(self, exchange_id: str):
        super().update_exchange_order_id(exchange_id)
        if self.is_local:
            self.last_state = "submitted"

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
        # Check if trade fee has been sent
        reported_fee_pct = order_update.get("maker_fee")
        if reported_fee_pct:
            self.fee_paid = Decimal(str(reported_fee_pct)) * self.executed_amount_base
        else:
            self.fee_paid = order_update.get("trade_fee") * self.executed_amount_base
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
        # Check if trade fee has been sent
        reported_fee_pct = trade_update.get("fee")
        if reported_fee_pct:
            self.fee_paid = Decimal(str(reported_fee_pct)) * self.executed_amount_base
        else:
            self.fee_paid = trade_update.get("trade_fee") * self.executed_amount_base
        if not self.fee_asset:
            self.fee_asset = self.quote_asset
        return True
