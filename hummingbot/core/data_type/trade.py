#!/usr/bin/env python

from collections import namedtuple
from datetime import datetime
from typing import List

import pandas as pd

from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.common import OrderType, TradeType


class Trade(namedtuple("_Trade", "trading_pair, side, price, amount, order_type, market, timestamp, trade_fee")):
    trading_pair: str
    side: TradeType
    price: float
    amount: float
    order_type: OrderType
    market: str
    timestamp: float
    trade_fee: TradeFeeBase

    @classmethod
    def to_pandas(cls, trades: List):
        columns: List[str] = ["trading_pair",
                              "price",
                              "quantity",
                              "order_type",
                              "trade_side",
                              "market",
                              "timestamp",
                              "fee_percent",
                              "flat_fee / gas"]
        data = []
        for trade in trades:
            if len(trade.trade_fee.flat_fees) == 0:
                flat_fee_str = "None"
            else:
                fee_strs = [f"{fee_tuple[0]} {fee_tuple[1]}" for fee_tuple in trade.trade_fee.flat_fees]
                flat_fee_str = ",".join(fee_strs)

            data.append([
                trade.trading_pair,
                trade.price,
                trade.amount,
                trade.order_type.name.lower(),
                trade.side.name.lower(),
                trade.market,
                datetime.fromtimestamp(trade.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                trade.trade_fee.percent,
                flat_fee_str,
            ])

        return pd.DataFrame(data=data, columns=columns)

    @property
    def trade_type(self):
        return self.side.name
