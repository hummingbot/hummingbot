from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class ExchangePair(BaseModel):
    exchange: str
    trading_pair: str


class ArbitrageConfig(BaseModel):
    markets: list[ExchangePair]
    amount: Decimal
    min_profitability: Decimal


class ArbitrageOpportunity(BaseModel):
    buying_market: ExchangePair
    selling_market: ExchangePair


class ArbitrageExecutorStatus(Enum):
    NOT_STARTED = 1
    ACTIVE_ARBITRAGE = 2
    COMPLETED = 3
