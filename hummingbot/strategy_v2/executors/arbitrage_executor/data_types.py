from decimal import Decimal
from enum import Enum

from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase


class ArbitrageExecutorConfig(ExecutorConfigBase):
    type = "arbitrage_executor"
    buying_market: ConnectorPair
    selling_market: ConnectorPair
    order_amount: Decimal
    min_profitability: Decimal
    max_retries: int = 3


class ArbitrageExecutorStatus(Enum):
    NOT_STARTED = 1
    ACTIVE_ARBITRAGE = 2
    COMPLETED = 3
    FAILED = 4
