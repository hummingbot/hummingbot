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


class TradeFills(namedtuple("_TradeFill", "symbol, side, price, amount, order_type, market, timestamp, trade_fee")):
    symbol: str
    trade_type: TradeType
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
                              "amount",
                              "order_type",
                              "trade_type",
                              "market",
                              "timestamp",
                              "fee_percent",
                              "flat_fee / gas"]
        data = []
        for trade in trades:
            flat_fee_str = "None"
            if len(trade.trade_fee['flat_fees']) == 0:
                flat_fee_str = "None"
            else:
                fee_strs = [f"{fee_tuple[0]} {fee_tuple[1]}" for fee_tuple in trade.trade_fee.flat_fees]
                flat_fee_str = ",".join(fee_strs)

            data.append([
                trade.symbol,
                trade.price,
                trade.amount,
                "market" if trade.order_type is OrderType.MARKET else "limit",
                "buy" if trade.trade_type is TradeType.BUY else "sell",
                trade.market,
                datetime.fromtimestamp(int(trade.timestamp/1e3)).strftime("%Y-%m-%d %H:%M:%S"),
                trade.trade_fee['percent'],
                flat_fee_str,
            ])

        return pd.DataFrame(data=data, columns=columns)
