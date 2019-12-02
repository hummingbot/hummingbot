from decimal import Decimal
from typing import (
    Any,
    Dict,
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.in_flight_order_base import InFlightOrderBase

s_decimal_0 = Decimal(0)


cdef class DDEXInFlightOrder(InFlightOrderBase):
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
            DDEXMarket,
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state
        )
        self.pending_amount_base = s_decimal_0
        self.gas_fee_amount = s_decimal_0
        self.available_amount_base = amount
        self.trade_id_set = set()

    def __repr__(self) -> str:
        return f"DDEXInFlightOrder(" \
               f"client_order_id='{self.client_order_id}', " \
               f"exchange_order_id='{self.exchange_order_id}', " \
               f"trading_pair='{self.trading_pair}', " \
               f"order_type={self.order_type}, " \
               f"trade_type={self.trade_type}, " \
               f"price={self.price}, " \
               f"amount={self.amount}, " \
               f"executed_amount_base={self.executed_amount_base}, " \
               f"executed_amount_quote={self.executed_amount_quote}, " \
               f"last_state='{self.last_state}', " \
               f"available_amount_base={self.available_amount_base}, " \
               f"gas_fee_amount={self.gas_fee_amount})"

    @property
    def is_done(self) -> bool:
        return self.available_amount_base == self.pending_amount_base == s_decimal_0

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"canceled"}

    @property
    def is_failure(self) -> bool:
        # Does not have any 'expiry" or "rejected" order statuses
        # Ref: https://docs.ddex.io/#place-order-synchronously
        # Currently not in use
        return self.last_state in {"partially_filled", "canceled"}

    def to_json(self) -> Dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "available_amount_base": str(self.available_amount_base),
            "last_state": self.last_state,
            "pending_amount_base": str(self.pending_amount_base),
            "gas_fee_amount": str(self.gas_fee_amount)
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        cdef:
            DDEXInFlightOrder retval = DDEXInFlightOrder(
                client_order_id=data["client_order_id"],
                exchange_order_id=data["exchange_order_id"],
                trading_pair=data["trading_pair"],
                order_type=getattr(OrderType, data["order_type"]),
                trade_type=getattr(TradeType, data["trade_type"]),
                price=Decimal(data["price"]),
                amount=Decimal(data["amount"]),
                initial_state=data["last_state"]
            )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.available_amount_base = Decimal(data["available_amount_base"])
        retval.last_state = data["last_state"]
        retval.pending_amount_base = Decimal(data["pending_amount_base"])
        retval.gas_fee_amount = Decimal(data["gas_fee_amount"])
        return retval

    def update_with_trade_update(self, trade_update: Dict[str, Any]):
        trade_id = trade_update["transactionId"]
        if (trade_update["makerOrderId"] != self.exchange_order_id and
                trade_update["takerOrderId"] != self.exchange_order_id) or trade_id in self.trade_id_set:
            # trade already recorded
            return
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(trade_update["amount"])
        self.available_amount_base -= Decimal(trade_update["amount"])
        self.executed_amount_quote += Decimal(trade_update["amount"]) * Decimal(trade_update["price"])
        self.fee_paid += Decimal(trade_update["feeAmount"])
        return trade_update
