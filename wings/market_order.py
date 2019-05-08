from typing import NamedTuple, List
import pandas as pd


class MarketOrder(NamedTuple):
    order_id: str
    symbol: str
    is_buy: bool
    base_asset: str
    quote_asset: str
    amount: float
    timestamp: float

    @classmethod
    def to_pandas(cls, market_orders: List["MarketOrder"]) -> pd.DataFrame:
        columns = ["order_id", "symbol", "is_buy", "base_asset", "quote_asset", "quantity"]
        data = [[
            limit_order.client_order_id,
            limit_order.symbol,
            limit_order.is_buy,
            limit_order.base_currency,
            limit_order.quote_currency,
            limit_order.quantity
        ] for limit_order in market_orders]
        return pd.DataFrame(data=data, columns=columns)
