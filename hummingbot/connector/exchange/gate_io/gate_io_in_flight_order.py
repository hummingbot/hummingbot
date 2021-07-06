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
        self.order_update_id_set = set()
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
            "id": 5736713,
            "user_id": 1000001,
            "order_id": "30784428",
            "currency_pair": "BTC_USDT",
            "create_time": 1605176741,
            "create_time_ms": "1605176741123.456",
            "side": "sell",
            "amount": "1.00000000",
            "role": "taker",
            "price": "10000.00000000",
            "fee": "0.00200000000000",
            "point_fee": "0",
            "gt_fee": "0"
        }
        """
        # Using time as ID here to avoid conflicts with order updates - order updates will take priority.
        trade_id_ms = str(str(trade_update["create_time_ms"]).split('.')[0])
        trade_id = str(trade_update["id"])
        if trade_id in self.trade_update_id_set or trade_id_ms in self.order_update_id_set:
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
        self.executed_amount_quote += (Decimal(str(trade_update.get("price", "0"))) *
                                       trade_executed_base)
        if not self.fee_asset:
            self.fee_asset = self.quote_asset
        return True

    def update_with_order_update(self, order_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with order update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        Example Order:
        {
            "id": "52109248977",
            "text": "3",
            "create_time": "1622638707",
            "update_time": "1622638807",
            "currency_pair": "BTC_USDT",
            "type": "limit",
            "account": "spot",
            "side": "buy",
            "amount": "0.001",
            "price": "1999.8",
            "time_in_force": "gtc",
            "left": "0.001",
            "filled_total": "0",
            "fee": "0",
            "fee_currency": "BTC",
            "point_fee": "0",
            "gt_fee": "0",
            "gt_discount": true,
            "rebated_fee": "0",
            "rebated_fee_currency": "BTC",
            "create_time_ms": "1622638707326",
            "update_time_ms": "1622638807635",
            ... optional params
            "status": "open",
            "event": "finish"
            "iceberg": "0",
            "fill_price": "0",
            "user": 5660412,
        }
        """
        # Update order execution status
        self.last_state = order_update.get("status", order_update.get("event"))

        if 'filled_total' not in order_update:
            return False

        trade_id_ms = str(str(order_update["update_time_ms"]).split('.')[0])
        if trade_id_ms in self.order_update_id_set:
            # trade already recorded
            return False

        # Set executed amounts
        executed_amount_quote = Decimal(str(order_update["filled_total"]))
        executed_price = Decimal(str(order_update.get("fill_price", "0")))
        if executed_amount_quote <= s_decimal_0 or executed_price <= s_decimal_0:
            # Skip these.
            return False

        self.order_update_id_set.add(trade_id_ms)

        self.executed_amount_quote = executed_amount_quote
        self.executed_amount_base = self.executed_amount_quote / executed_price
        self.fee_paid = Decimal(str(order_update.get("fee")))
        if not self.fee_asset:
            self.fee_asset = order_update.get("fee_currency", self.quote_asset)
        return True
