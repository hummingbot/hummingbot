from typing import Union

from .binance import BinanceConnector
from .binance_paper_trade import BinancePaperTradeConnector

Connector = Union[BinanceConnector, BinancePaperTradeConnector]

__all__ = [
    "BinanceConnector",
    "BinancePaperTradeConnector",
]
