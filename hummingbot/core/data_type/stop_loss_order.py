from decimal import Decimal
from typing import NamedTuple

import pandas as pd

from hummingbot.core.data_type.common import OrderType, PositionAction


class StopLossOrder(NamedTuple):
    order_id: str
    trading_pair: str
    is_buy: bool
    base_asset: str
    quote_asset: str
    placed_price: float
    trigger_price: float
    amount: float
    timestamp: float
    position: PositionAction = PositionAction.NIL

    @classmethod
    def to_pandas(cls, stop_loss_orders: list["StopLossOrder"]) -> pd.DataFrame:
        columns = [
            "order_id", "trading_pair", "is_buy", "base_asset",
            "quote_asset", "placed_price", "trigger_price", "quantity", "timestamp"
        ]
        data = [[
            order.order_id,
            order.trading_pair,
            order.is_buy,
            order.base_asset,
            order.quote_asset,
            order.placed_price,
            order.trigger_price,
            order.amount,
            pd.Timestamp(order.timestamp, unit='s', tz='UTC').strftime('%Y-%m-%d %H:%M:%S')
        ] for order in stop_loss_orders]
        return pd.DataFrame(data=data, columns=columns)

    @property
    def client_order_id(self) -> str:
        return self.order_id

    @property
    def quantity(self) -> Decimal:
        return Decimal(self.amount)

    @property
    def price(self) -> Decimal:
        """The price at which the stop loss will trigger"""
        return Decimal(self.trigger_price)

    def order_type(self) -> OrderType:
        return OrderType.STOP_LOSS

    def copy_with_id(self, client_order_id: str) -> "StopLossOrder":
        return StopLossOrder(
            order_id=client_order_id,
            trading_pair=self.trading_pair,
            is_buy=self.is_buy,
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            placed_price=self.placed_price,
            trigger_price=self.trigger_price,
            amount=self.amount,
            timestamp=self.timestamp,
            position=self.position,
        )
