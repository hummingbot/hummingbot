from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Environment(str, Enum):
    PAPER = "paper"
    CANARY = "canary"
    LIVE = "live"


class AccountKind(str, Enum):
    MASTER = "master"
    SUBACCOUNT = "subaccount"
    INDEPENDENT = "independent"


class StrategySleeve(str, Enum):
    MARKET_MAKING = "market_making"
    DIRECTIONAL = "directional"
    RELATIVE_VALUE = "relative_value"
    HEDGE = "hedge"
    LIQUIDITY = "liquidity"
    RESERVE = "reserve"


class CompatibilityRelation(str, Enum):
    COMPATIBLE = "compatible"
    CONDITIONAL = "conditional"
    EXCLUSIVE = "exclusive"


class LifecycleState(str, Enum):
    STABLE = "stable"
    CANDIDATE = "candidate"
    CONFIRMING = "confirming"
    DRAINING_OLD = "draining_old"
    STARTING_NEW = "starting_new"
    CANARY = "canary"
    ROLLBACK = "rollback"
    PROTECT = "protect"


class LifecycleAction(str, Enum):
    HOLD = "hold"
    CONTINUE = "continue"
    START = "start"
    SWITCH = "switch"
    STOP = "stop"
    PROTECT = "protect"


class MarketState(StrictModel):
    timestamp: float
    symbol: str
    direction: str = "flat"
    trend_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    volatility_bucket: str = "normal"
    realized_volatility: float = Field(default=0.0, ge=0.0)
    liquidity_bucket: str = "healthy"
    spread_bps: float = Field(default=0.0, ge=0.0)
    depth_10bps_quote: float = Field(default=0.0, ge=0.0)
    breakout_up_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    breakout_down_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_reversion_score: float = Field(default=0.0, ge=0.0, le=1.0)
    funding_opportunity: bool = False
    basis_edge_bps_after_cost: float = 0.0
    data_fresh: bool = True
    risk_flags: List[str] = Field(default_factory=list)
    features: Dict[str, float] = Field(default_factory=dict)


class AccountSnapshot(StrictModel):
    account_id: str
    observed_at: float
    equity_quote: float = Field(ge=0.0)
    available_quote: float = Field(ge=0.0)
    gross_exposure_quote: float = Field(default=0.0, ge=0.0)
    net_exposure_quote: float = 0.0
    drawdown_quote: float = Field(default=0.0, ge=0.0)
    open_orders: int = Field(default=0, ge=0)
    worker_healthy: bool = True
    data_fresh: bool = True
    balances_fresh: bool = True
    positions_fresh: bool = True
    unreconciled_orders: bool = False
    transfer_locked: bool = False
    risk_halted: bool = False
    active_strategy_ids: List[str] = Field(default_factory=list)
    runtime_managed: bool = True


class FixedScoreComponents(StrictModel):
    regime_fit: float = Field(ge=0.0, le=1.0)
    expected_edge_after_cost: float = Field(ge=0.0, le=1.0)
    execution_quality: float = Field(ge=0.0, le=1.0)
    strategy_health: float = Field(ge=0.0, le=1.0)
    switch_cost_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    concentration_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    correlation_penalty: float = Field(default=0.0, ge=0.0, le=1.0)


class AIRoutingSignal(StrictModel):
    observed_at: float
    ttl_seconds: int = Field(default=300, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    abstain: bool = False
    strategy_adjustments: Dict[str, float] = Field(default_factory=dict)
    reason_codes: List[str] = Field(default_factory=list)
    model: Optional[str] = None
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None


class CandidateSignal(StrictModel):
    strategy_id: str
    candidate_id: Optional[str] = None
    config_hash: Optional[str] = None
    connector: Optional[str] = None
    trading_pair: str
    requested_capital_quote: float = Field(gt=0.0)
    score_components: FixedScoreComponents
    position_side: str = "BOTH"
    hard_blockers: List[str] = Field(default_factory=list)
    conditions_met: List[str] = Field(default_factory=list)


class CandidateEvaluation(StrictModel):
    strategy_id: str
    candidate_id: Optional[str] = None
    config_hash: Optional[str] = None
    connector: Optional[str] = None
    trading_pair: str
    sleeve: StrategySleeve
    eligible: bool
    blockers: List[str] = Field(default_factory=list)
    fixed_score: float = Field(default=0.0, ge=0.0, le=1.0)
    ai_adjustment: float = Field(default=0.0, ge=-1.0, le=1.0)
    final_score: float = Field(default=0.0, ge=0.0, le=1.0)
    requested_capital_quote: float = Field(default=0.0, ge=0.0)
    account_ids: List[str] = Field(default_factory=list)
    position_side: str = "BOTH"
    conditions_met: List[str] = Field(default_factory=list)


class RouteTarget(StrictModel):
    account_id: str
    sleeve: StrategySleeve
    strategy_id: str
    candidate_id: Optional[str] = None
    config_hash: Optional[str] = None
    trading_pair: str
    target_capital_quote: float = Field(gt=0.0)
    lifecycle_action: LifecycleAction = LifecycleAction.START
    score: float = Field(ge=0.0, le=1.0)
    position_side: str = "BOTH"


class BlockedCandidate(StrictModel):
    strategy_id: str
    trading_pair: str
    reason_codes: List[str]


class RoutePlan(StrictModel):
    decision_id: str
    generated_at: float
    effective_at: float
    expires_at: float
    environment: Environment
    allocations: List[RouteTarget] = Field(default_factory=list)
    reserve_quote: float = Field(default=0.0, ge=0.0)
    blocked_candidates: List[BlockedCandidate] = Field(default_factory=list)
    risk_blockers: List[str] = Field(default_factory=list)
    ai_applied: bool = False
    input_hash: str

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: float, info):
        generated_at = info.data.get("generated_at")
        if generated_at is not None and value <= generated_at:
            raise ValueError("expires_at must be later than generated_at")
        return value


class TransitionObservation(StrictModel):
    desired_strategy_id: Optional[str]
    score_delta: float = 0.0
    risk_triggered: bool = False
    risk_cleared: bool = False
    old_drained: bool = False
    new_started: bool = False
    canary_healthy: bool = True
    start_failed: bool = False
    rollback_completed: bool = False


class TransitionRecord(StrictModel):
    account_id: str
    sleeve: StrategySleeve
    trading_pair: str
    state: LifecycleState = LifecycleState.STABLE
    active_strategy_id: Optional[str] = None
    desired_strategy_id: Optional[str] = None
    previous_strategy_id: Optional[str] = None
    confirmation_cycles: int = Field(default=0, ge=0)
    state_entered_at: float = 0.0
    last_transition_at: float = 0.0
    last_error: Optional[str] = None
