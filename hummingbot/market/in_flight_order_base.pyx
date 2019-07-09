from decimal import Decimal
from typing import (
    Any,
    Dict
)

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base import MarketBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)

s_decimal_0 = Decimal(0)


cdef class InFlightOrderBase:
    def __init__(self,
                 market_class: MarketBase,
                 client_order_id: str,
                 exchange_order_id: str,
                 symbol: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str):

        self.market_class = market_class
        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.symbol = symbol
        self.order_type = order_type
        self.trade_type = trade_type
        self.price = price
        self.amount = amount
        self.executed_amount_base = s_decimal_0
        self.executed_amount_quote = s_decimal_0
        self.fee_asset = None
        self.fee_paid = s_decimal_0
        self.last_state = initial_state

    def __repr__(self) -> str:
        return f"InFlightOrder(" \
               f"client_order_id='{self.client_order_id}', " \
               f"exchange_order_id='{self.exchange_order_id}', " \
               f"symbol='{self.symbol}', " \
               f"order_type='{self.order_type}', " \
               f"trade_type={self.trade_type}, " \
               f"price={self.price}, " \
               f"amount={self.amount}, " \
               f"executed_amount_base={self.executed_amount_base}, " \
               f"executed_amount_quote={self.executed_amount_quote}, " \
               f"fee_asset='{self.fee_asset}', " \
               f"fee_paid={self.fee_paid}, " \
               f"last_state='{self.last_state}')"

    @property
    def is_done(self) -> bool:
        raise NotImplementedError

    @property
    def is_failure(self) -> bool:
        raise NotImplementedError

    @property
    def base_asset(self) -> str:
        return self.market_class.split_symbol(self.symbol)[0]

    @property
    def quote_asset(self) -> str:
        return self.market_class.split_symbol(self.symbol)[1]

    def to_limit_order(self) -> LimitOrder:
        return LimitOrder(
            self.client_order_id,
            self.symbol,
            self.trade_type,
            self.base_asset,
            self.quote_asset,
            self.price,
            self.amount
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "symbol": self.symbol,
            "order_type": self.order_type.name,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "fee_asset": self.fee_asset,
            "fee_paid": str(self.fee_paid),
            "last_state": self.last_state
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "InFlightOrderBase":
        raise NotImplementedError
