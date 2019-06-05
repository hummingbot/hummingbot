#!/usr/bin/env python

from collections import namedtuple
from typing import List
from datetime import datetime
import pandas as pd

from hummingbot.core.event.events import (
    TradeType,
    TradeFee,
    OrderType,
)


class Trade(namedtuple("_Trade", "symbol, side, price, amount, order_type, market, timestamp, trade_fee")):
    symbol: str
    side: TradeType
    price: float
    amount: float
    order_type: OrderType
    market: str
    timestamp: float
    trade_fee: TradeFee

    @classmethod
    def to_pandas(cls, trades: List):
        columns: List[str] = ["symbol",
                              "price",
                              "quantity",
                              "order_type",
                              "trade_side",
                              "market",
                              "timestamp",
                              "fee_percent",
                              "flat_fee / gas"]
        data = [[
            trade.symbol,
            trade.price,
            trade.amount,
            "market" if trade.order_type is OrderType.MARKET else "limit",
            "buy" if trade.side is TradeType.BUY else "sell",
            trade.market,
            datetime.fromtimestamp(trade.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            trade.trade_fee.percent,
            trade.trade_fee.flat_fees,
        ] for trade in trades]
        return pd.DataFrame(data=data, columns=columns)
