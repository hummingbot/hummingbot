#!/usr/bin/env python

from collections import namedtuple
from enum import Enum
from typing import (
    List,
    Dict
)

from wings.order_book_row import OrderBookRow


class TradeSide(Enum):
    BUY = 1
    SELL = 2


class Trade(namedtuple("_Trade", "symbol, side, price, amount")):
    symbol: str
    side: TradeSide
    price: float
    amount: float

    @classmethod
    def trades_from_order_book_rows(cls,
                                    symbol: str,
                                    side: TradeSide,
                                    order_book_rows: List[OrderBookRow]) -> List["Trade"]:
        return [Trade(symbol, side, r.price, r.amount) for r in order_book_rows]

    @classmethod
    def trade_from_binance_execution_report_event(cls, execution_report: Dict[str, any]) -> "Trade":
        execution_type: str = execution_report.get("x")
        if execution_type != "TRADE":
            raise ValueError(f"Invalid execution type '{execution_type}'.")
        return Trade(execution_report["s"],
                     TradeSide.BUY if execution_report["S"] == "BUY" else TradeSide.SELL,
                     float(execution_report["L"]),
                     float(execution_report["l"]))
