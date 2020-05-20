from typing import NamedTuple, List
import pandas as pd


class MarketOrder(NamedTuple):
    order_id: str
    trading_pair: str
    is_buy: bool
    base_asset: str
    quote_asset: str
    amount: float
    timestamp: float

    @classmethod
    def to_pandas(cls, market_orders: List["MarketOrder"]) -> pd.DataFrame:
        columns = ["order_id", "trading_pair", "is_buy", "base_asset", "quote_asset", "quantity", "timestamp"]
        data = [[
            market_order.order_id,
            market_order.trading_pair,
            market_order.is_buy,
            market_order.base_asset,
            market_order.quote_asset,
            market_order.amount,
            pd.Timestamp(market_order.timestamp, unit='s', tz='UTC').strftime('%Y-%m-%d %H:%M:%S')
        ] for market_order in market_orders]
        return pd.DataFrame(data=data, columns=columns)
