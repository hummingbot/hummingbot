from decimal import Decimal
from enum import Enum
from typing import List, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop


class DCAMode(Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class DCAExecutorConfig(ExecutorConfigBase):
    type = "dca_executor"
    connector_name: str
    trading_pair: str
    side: TradeType
    leverage: int = 1
    amounts_quote: List[Decimal]
    prices: List[Decimal]
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    trailing_stop: Optional[TrailingStop] = None
    time_limit: Optional[int] = None
    mode: DCAMode = DCAMode.MAKER
    activation_bounds: Optional[List[Decimal]] = None
    level_id: Optional[str] = None
