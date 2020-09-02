from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional
)
from zero_ex.order_utils import Order as ZeroExOrder

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.connector.utils import (
    zrx_order_to_json,
    json_to_zrx_order
)

s_decimal_0 = Decimal(0)


cdef class BambooRelayInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 is_coordinated: bool,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 expires: int = None,
                 protocol_fee_amount: Optional[Decimal] = s_decimal_0,
                 taker_fee_amount: Optional[Decimal] = s_decimal_0,
                 initial_state: str = "OPEN",
                 tx_hash: Optional[str] = None,
                 zero_ex_order: Optional[ZeroExOrder] = None,
                 recorded_fills: Optional[[]] = [],
                 has_been_cancelled: Optional[bool] = False):
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
        self.is_coordinated = is_coordinated
        self.expires = expires
        self.protocol_fee_amount = protocol_fee_amount
        self.taker_fee_amount = taker_fee_amount
        self.available_amount_base = amount
        self.tx_hash = tx_hash  # used for tracking market orders
        self.zero_ex_order = zero_ex_order
        self.recorded_fills = recorded_fills
        self.has_been_cancelled = has_been_cancelled

    def __repr__(self) -> str:
        return f"BambooRelayInFlightOrder(" \
               f"client_order_id='{self.client_order_id}', " \
               f"exchange_order_id='{self.exchange_order_id}', " \
               f"trading_pair='{self.trading_pair}', " \
               f"order_type='{self.order_type}', " \
               f"is_coordinated='{self.is_coordinated}', " \
               f"trade_type={self.trade_type}, " \
               f"price={self.price}, " \
               f"amount={self.amount}, " \
               f"expires={self.expires}, " \
               f"executed_amount_base={self.executed_amount_base}, " \
               f"executed_amount_quote={self.executed_amount_quote}, " \
               f"last_state='{self.last_state}', " \
               f"available_amount_base={self.available_amount_base}, " \
               f"protocol_fee_amount={self.protocol_fee_amount}, " \
               f"taker_fee_amount={self.taker_fee_amount}, " \
               f"tx_hash='{self.tx_hash}', " \
               f"zero_ex_order='{self.zero_ex_order}', " \
               f"recorded_fills='{self.recorded_fills}', " \
               f"has_been_cancelled='{self.has_been_cancelled}')"

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED", "CANCELLED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"UNFUNDED"}

    @property
    def is_expired(self) -> bool:
        return self.last_state in {"EXPIRED"}

    def to_json(self) -> Dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "is_coordinated": self.is_coordinated,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "expires": self.expires,
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "last_state": self.last_state,
            "available_amount_base": str(self.available_amount_base),
            "protocol_fee_amount": str(self.protocol_fee_amount),
            "taker_fee_amount": str(self.taker_fee_amount),
            "tx_hash": self.tx_hash,
            "zero_ex_order": zrx_order_to_json(self.zero_ex_order),
            "recorded_fills": self.recorded_fills,
            "has_been_cancelled": self.has_been_cancelled
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        cdef:
            BambooRelayInFlightOrder retval = BambooRelayInFlightOrder(
                client_order_id=data["client_order_id"],
                exchange_order_id=data["exchange_order_id"],
                trading_pair=data["trading_pair"],
                order_type=getattr(OrderType, data["order_type"]),
                is_coordinated=bool(data["is_coordinated"]),
                trade_type=getattr(TradeType, data["trade_type"]),
                price=Decimal(data["price"]),
                amount=Decimal(data["amount"]),
                expires=data["expires"],
                protocol_fee_amount=Decimal(data["protocol_fee_amount"]),
                taker_fee_amount=Decimal(data["taker_fee_amount"]),
                initial_state=data["last_state"],
                tx_hash=data["tx_hash"],
                zero_ex_order=json_to_zrx_order(data["zero_ex_order"]),
                recorded_fills=data["recorded_fills"],
                has_been_cancelled=bool(data["has_been_cancelled"])
            )
        retval.available_amount_base = Decimal(data["available_amount_base"])
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        return retval
