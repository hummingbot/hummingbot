#!/usr/bin/env python

from collections import namedtuple
from typing import (
    List,
    Dict
)
from datetime import datetime
import pandas as pd

from wings.order_book_row import OrderBookRow
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
    def trades_from_order_book_rows(cls,
                                    symbol: str,
                                    side: TradeType,
                                    order_book_rows: List[OrderBookRow]) -> List["Trade"]:
        return [Trade(symbol, side, r.price, r.amount) for r in order_book_rows]

    @classmethod
    def trade_from_binance_execution_report_event(cls, execution_report: Dict[str, any]) -> "Trade":
        execution_type: str = execution_report.get("x")
        if execution_type != "TRADE":
            raise ValueError(f"Invalid execution type '{execution_type}'.")
        return Trade(execution_report["s"],
                     TradeType.BUY if execution_report["S"] == "BUY" else TradeType.SELL,
                     float(execution_report["L"]),
                     float(execution_report["l"]))

    @classmethod
    def to_pandas(cls, trades: List):
        columns: List[str] = ["symbol", "trade_side", "price", "quantity", "order_type", "market", "timestamp"]
        data = [[
            trade.symbol,
            "BUY" if trade.side is TradeType.BUY else "SELL",
            trade.price,
            trade.amount,
            "MARKET" if trade.order_type is OrderType.MARKET else "LIMIT",
            trade.market,
            datetime.fromtimestamp(trade.timestamp).strftime("%Y-%m-%d-%H-%M-%S"),
        ] for trade in trades]
        return pd.DataFrame(data=data, columns=columns)
