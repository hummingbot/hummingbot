from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class ExchangePair(BaseModel):
    exchange: str
    trading_pair: str


class ArbitrageConfig(BaseModel):
    buying_market: ExchangePair
    selling_market: ExchangePair
    order_amount: Decimal
    min_profitability: Decimal
    max_retries: int = 3


class ArbitrageExecutorStatus(Enum):
    NOT_STARTED = 1
    ACTIVE_ARBITRAGE = 2
    COMPLETED = 3
    FAILED = 4
