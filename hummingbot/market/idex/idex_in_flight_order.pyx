import asyncio
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.market.idex.idex_market import IDEXMarket
from hummingbot.market.in_flight_order_base import InFlightOrderBase
s_decimal_0 = Decimal(0)


cdef class IDEXInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: Optional[str] = "open"):
        super().__init__(
            IDEXMarket,
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state
        )
        self.available_amount_base = amount
        self.gas_fee_amount = s_decimal_0
        self.created_timestamp = 0.0
        self.created_timestamp_update_event = asyncio.Event()

    def __repr__(self) -> str:
        return f"InFlightOrder(" \
               f"client_order_id='{self.client_order_id}', " \
               f"exchange_order_id='{self.exchange_order_id}', " \
               f"trading_pair='{self.trading_pair}', " \
               f"order_type='{self.order_type}', " \
               f"trade_type={self.trade_type}, " \
               f"price={self.price}, " \
               f"amount={self.amount}, " \
               f"executed_amount_base={self.executed_amount_base}, " \
               f"executed_amount_quote={self.executed_amount_quote}, " \
               f"last_state='{self.last_state}', " \
               f"available_amount_base={self.available_amount_base}, " \
               f"gas_fee_amount={self.gas_fee_amount}, " \
               f"created_timestamp={self.created_timestamp})"

    @property
    def is_done(self) -> bool:
        return self.available_amount_base == s_decimal_0 or self.last_state in ["complete", "cancelled"]

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"cancelled"}

    @property
    def is_failure(self) -> bool:
        # Currently not in use
        return self.last_state in {"cancelled"}

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
            "last_state": self.last_state,
            "available_amount_base": str(self.available_amount_base),
            "gas_fee_amount": str(self.gas_fee_amount),
            "created_timestamp": self.created_timestamp,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        cdef:
            IDEXInFlightOrder retval = IDEXInFlightOrder(
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
        retval.gas_fee_amount = Decimal(data["gas_fee_amount"])
        retval.created_timestamp = data["created_timestamp"]
        return retval

    def update_created_timestamp(self, created_timestamp: float):
        self.created_timestamp = created_timestamp
        self.created_timestamp_update_event.set()

    async def get_created_timestamp(self) -> float:
        if self.created_timestamp is None:
            await self.created_timestamp_update_event.wait()
        return self.created_timestamp
