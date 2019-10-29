from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.market.stablecoinswap.stablecoinswap_market import StablecoinswapMarket
from hummingbot.market.in_flight_order_base import InFlightOrderBase

s_decimal_0 = Decimal(0)


cdef class StablecoinswapInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 symbol: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 tx_hash: Optional[str] = None,
                 fee_asset: Optional[str] = None,
                 fee_percent: Optional[Decimal] = s_decimal_0,
                 initial_state: str = "open"):
        super().__init__(
            StablecoinswapMarket,
            client_order_id,
            exchange_order_id,
            symbol,
            order_type,
            trade_type,
            price,
            amount,
            initial_state,
        )
        self.tx_hash = tx_hash  # used for tracking market orders
        self.fee_asset = fee_asset
        self.fee_percent = fee_percent

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
               f"tx_hash={self.tx_hash}, " \
               f"fee_percent={self.fee_percent}, " \
               f"last_state='{self.last_state}')"

    @property
    def is_done(self) -> bool:
        return self.last_state == "done"

    @property
    def is_failure(self) -> bool:
        return self.last_state == "failure"

    @property
    def is_cancelled(self) -> bool:
        # couldn't be cancelled
        return False

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
            "tx_hash": self.tx_hash,
            "fee_percent": self.fee_percent,
            "last_state": self.last_state
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        cdef:
            StablecoinswapInFlightOrder retval = StablecoinswapInFlightOrder(
                client_order_id=data["client_order_id"],
                exchange_order_id=data["exchange_order_id"],
                symbol=data["symbol"],
                order_type=getattr(OrderType, data["order_type"]),
                trade_type=getattr(TradeType, data["trade_type"]),
                price=Decimal(data["price"]),
                amount=Decimal(data["amount"]),
                initial_state=data["last_state"],
                tx_hash=data["tx_hash"],
                fee_asset=data["fee_asset"],
                fee_percent=data["fee_percent"]
            )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_paid = Decimal(data["fee_paid"])
        return retval
