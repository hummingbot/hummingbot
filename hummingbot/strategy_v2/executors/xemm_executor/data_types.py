from decimal import Decimal

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase


class XEMMExecutorConfig(ExecutorConfigBase):
    type = "xemm_executor"
    buying_market: ConnectorPair
    selling_market: ConnectorPair
    maker_side: TradeType
    order_amount: Decimal
    min_profitability: Decimal
    target_profitability: Decimal
    max_profitability: Decimal
