from decimal import Decimal
from typing import (
    Any,
    Dict
)

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)


class BinanceInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "NEW"):
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
        return self.last_state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"REJECTED", "EXPIRED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        return cls._basic_from_json(data)

    def update_with_execution_report(self, execution_report: Dict[str, Any]):
        trade_id = execution_report["t"]
        if trade_id in self.trade_id_set:
            # trade already recorded
            return False
        self.trade_id_set.add(trade_id)
        last_executed_quantity = Decimal(execution_report["l"])
        last_commission_amount = Decimal(execution_report["n"])
        last_commission_asset = execution_report["N"]
        last_order_state = execution_report["X"]
        last_executed_price = Decimal(execution_report["L"])
        executed_amount_quote = last_executed_price * last_executed_quantity
        self.executed_amount_base += last_executed_quantity
        self.executed_amount_quote += executed_amount_quote
        if last_commission_asset is not None:
            self.fee_asset = last_commission_asset
        self.fee_paid += last_commission_amount
        self.last_state = last_order_state
        return True

    def update_with_trade_update(self, trade_update: Dict[str, Any]):
        trade_id = trade_update["id"]
        # trade_update["orderId"] is type int
        if str(trade_update["orderId"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            # trade already recorded
            return
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(trade_update["qty"])
        self.fee_paid += Decimal(trade_update["commission"])
        self.executed_amount_quote += Decimal(trade_update["quoteQty"])
        if not self.fee_asset:
            self.fee_asset = trade_update["commissionAsset"]
        return trade_update
