from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import PositionAction
from hummingbot.core.event.events import OrderType


@dataclass
class StrategyJobSpec:
    user_id: str
    account_id: str
    strategy_type: str
    params: Dict[str, Any]


@dataclass
class StrategyConfig:
    user_id: str
    account_id: str
    strategy_type: str
    connector_name: str
    trading_pair: str
    timeframe: str
    fast_ema: int
    slow_ema: int
    atr_period: int
    atr_threshold: Decimal
    risk_pct_per_trade: Decimal
    status: str = "pending"
    id: Optional[str] = None

    @classmethod
    def from_job(cls, job: StrategyJobSpec) -> "StrategyConfig":
        params = job.params
        return cls(
            user_id=job.user_id,
            account_id=job.account_id,
            strategy_type=job.strategy_type,
            connector_name=params["connector_name"],
            trading_pair=params["trading_pair"],
            timeframe=params["timeframe"],
            fast_ema=params["fast_ema"],
            slow_ema=params["slow_ema"],
            atr_period=params.get("atr_period", 14),
            atr_threshold=Decimal(str(params["atr_threshold"])),
            risk_pct_per_trade=Decimal(str(params["risk_pct_per_trade"])),
        )


@dataclass
class ConnectorConfig:
    name: str
    trading_pairs: list
    api_keys: Dict[str, str]
    trading_required: bool = True


@dataclass
class OrderIntent:
    trading_pair: str
    side: str  # "buy" or "sell"
    amount: Decimal
    order_type: OrderType = OrderType.MARKET
    price: Optional[Decimal] = None
    position_action: PositionAction = PositionAction.NIL


@dataclass
class ExecutionRiskLimits:
    max_notional: Optional[Decimal] = None
    max_leverage: Optional[Decimal] = None
    reduce_only: bool = False
