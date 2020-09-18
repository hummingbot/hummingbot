from decimal import Decimal
from typing import (
    Any,
    Dict
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


cdef class DuedexInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
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
            initial_state  # new, partiallyFilled, filled, cancelled, untriggered
        )

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "cancelled"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"cancelled"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"cancelled"}

    @property
    def is_open(self) -> bool:
        return self.last_state in {"new", "partiallyFilled", "untriggered"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        # {'amount': '20.00000000', 'client_order_id': 'buy-BTC-USD-1600323206002475', 'exchange_order_id': '17', 'executed_amount_base': '0', 'executed_amount_quote': '0', 'fee_asset': None, 'fee_paid': '0', 'last_state': 'new', 'order_type': 'LIMIT', 'price': '9454.50', 'trade_type': 'BUY', 'trading_pair': 'BTC-USD'}
        cdef:
            DuedexInFlightOrder retval = DuedexInFlightOrder(
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
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        retval.last_state = data["last_state"]
        return retval
