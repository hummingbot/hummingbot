#!/usr/bin/env python

from collections import namedtuple
from typing import List
from datetime import datetime
import pandas as pd

from wings.events import (
    TradeType,
    OrderType,
)


class Trade(namedtuple("_Trade", "symbol, side, price, amount, order_type, market, timestamp")):
    symbol: str
    side: TradeType
    price: float
    amount: float
    order_type: OrderType
    market: str
    timestamp: float

    @classmethod
    def to_pandas(cls, trades: List):
        columns: List[str] = ["symbol", "price", "quantity", "order_type", "trade_side", "market", "timestamp"]
        data = [[
            trade.symbol,
            trade.price,
            trade.amount,
            "market" if trade.order_type is OrderType.MARKET else "limit",
            "buy" if trade.side is TradeType.BUY else "sell",
            trade.market,
            datetime.fromtimestamp(trade.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
        ] for trade in trades]
        return pd.DataFrame(data=data, columns=columns)
