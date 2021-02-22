from decimal import Decimal
from typing import Dict, Any

from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


class BinancePerpetualsInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 leverage: int,
                 position: str,
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
        self.leverage = leverage
        self.position = position

    @property
    def is_done(self):
        return self.last_state in {"FILLED", "CANCELED", "PENDING_CANCEL", "REJECTED", "EXPIRED"}

    @property
    def is_cancelled(self):
        return self.last_state == "CANCELED"

    @property
    def is_failure(self):
        return self.last_state in {"CANCELED", "PENDING_CANCEL", "REJECTED", "EXPIRED"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]):
        return_val: BinancePerpetualsInFlightOrder = BinancePerpetualsInFlightOrder(
            client_order_id=data["client_order_id"],
            exchange_order_id=data["exchange_order_id"],
            trading_pair=data["trading_pair"],
            order_type=getattr(OrderType, data["order_type"]),
            trade_type=getattr(TradeType, data["trade_type"]),
            price=Decimal(data["price"]),
            amount=Decimal(data["amount"]),
            initial_state=data["last_state"]
        )
        return_val.executed_amount_base = Decimal(data["executed_amount_base"])
        return_val.executed_amount_quote = Decimal(data["executed_amount_quote"])
        return_val.fee_asset = data["fee_asset"]
        return_val.fee_paid = Decimal(data["fee_paid"])
        return return_val

    def update_with_execution_report(self, execution_report: Dict[str, Any]):
        order_report = execution_report.get("o")
        trade_id = order_report.get("t")
        if trade_id in self.trade_id_set:
            return
        self.trade_id_set.add(trade_id)
        last_executed_quantity = Decimal(order_report.get("l"))
        last_commission_amount = Decimal(order_report.get("n", "0"))
        last_commission_asset = order_report.get("N")
        last_order_state = order_report.get("X")
        last_executed_price = Decimal(order_report.get("L"))
        executed_amount_quote = last_executed_price * last_executed_quantity
        self.executed_amount_base += last_executed_quantity
        self.executed_amount_quote += executed_amount_quote
        if last_commission_asset is not None:
            self.fee_asset = last_commission_asset
        self.fee_paid += last_commission_amount
        self.last_state = last_order_state

    def update_with_trade_updates(self, trade_update: Dict[str, Any]):
        trade_id = trade_update.get("id")
        if str(trade_update.get("order_id")) != self.exchange_order_id or trade_id in self.trade_id_set:
            return
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(trade_update.get("qty"))
        self.executed_amount_quote += Decimal(trade_update.get("quoteQty"))
        self.fee_paid += Decimal(trade_update.get("commission"))
        if not self.fee_asset:
            self.fee_asset = trade_update.get("commissionAsset")
        return trade_update
