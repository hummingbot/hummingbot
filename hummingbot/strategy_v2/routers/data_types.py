from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    UNKNOWN = "unknown"
    RANGE_LOW_VOL = "range_low_vol"
    RANGE_HIGH_VOL = "range_high_vol"
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    BREAKOUT_UP = "breakout_up"
    BREAKOUT_DOWN = "breakout_down"
    EXTREME = "extreme"
    ARBITRAGE = "arbitrage"


class RouterAction(str, Enum):
    CONTINUE = "continue"
    REDUCE = "reduce"
    STOP = "stop"
    SWITCH = "switch"
    PROTECT = "protect"
    OBSERVE = "observe"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class StrategyFamily(str, Enum):
    GRID = "grid"
    MARKET_MAKING = "market_making"
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"
    HEDGE = "hedge"
    LP = "lp"
    PROTECT = "protect"
    OBSERVE = "observe"


class ReasonCode(str, Enum):
    NOT_ENOUGH_DATA = "not_enough_data"
    LOW_VOL_RANGE = "low_vol_range"
    HIGH_VOL_RANGE = "high_vol_range"
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE_BREAK_UP = "range_break_up"
    RANGE_BREAK_DOWN = "range_break_down"
    ATR_SPIKE = "atr_spike"
    VOLUME_SPIKE = "volume_spike"
    ACTIVE_LOSS_LIMIT = "active_loss_limit"
    STRATEGY_MISMATCH = "strategy_mismatch"
    NO_ACTIVE_STRATEGY = "no_active_strategy"
    COOLDOWN = "cooldown"
    SHORT_DISABLED = "short_disabled"


class MarketFeatures(BaseModel):
    timestamp: float = 0
    mid_price: float = 0
    close_price: float = 0
    atr_pct: float = 0
    bb_width_pct: float = 0
    ema_fast: float = 0
    ema_slow: float = 0
    ema_slope_pct: float = 0
    volume_zscore: float = 0
    range_high: float = 0
    range_low: float = 0
    range_position: float = 0.5
    active_executor_count: int = 0
    active_net_pnl_pct: float = 0
    active_strategy: Optional[str] = None
    enough_data: bool = False


class StrategyCandidate(BaseModel):
    name: str
    family: StrategyFamily
    controller_name: Optional[str] = None
    executor_type: Optional[str] = None
    supported_regimes: List[MarketRegime] = Field(default_factory=list)
    description: str = ""
    priority: int = 100
    enabled: bool = True


class StrategyScore(BaseModel):
    name: str
    family: StrategyFamily
    enabled: bool
    supported: bool = False
    score: float = 0
    reasons: List[str] = Field(default_factory=list)


class RouterDecision(BaseModel):
    timestamp: float = 0
    regime: MarketRegime = MarketRegime.UNKNOWN
    action: RouterAction = RouterAction.OBSERVE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    active_strategy: Optional[str] = None
    recommended_strategy: Optional[str] = None
    confidence: float = 0
    position_scale: float = 0
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    message: str = ""
