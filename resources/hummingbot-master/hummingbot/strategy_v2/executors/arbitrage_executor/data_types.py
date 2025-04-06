from decimal import Decimal
from typing import Optional

from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase


class ArbitrageExecutorConfig(ExecutorConfigBase):
    type: str = "arbitrage_executor"
    buying_market: ConnectorPair
    selling_market: ConnectorPair
    order_amount: Decimal
    min_profitability: Decimal
    gas_conversion_price: Optional[Decimal] = None
    max_retries: int = 3
