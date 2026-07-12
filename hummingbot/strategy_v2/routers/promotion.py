from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class PromotionStage(str, Enum):
    COLLECTED = "collected"
    SHADOW = "shadow"
    BACKTEST_PASSED = "backtest_passed"
    PAPER_ENABLED = "paper_enabled"
    LIVE_CANARY = "live_canary"
    LIVE_ENABLED = "live_enabled"


class AdapterExecutionMode(str, Enum):
    CONTROLLER_PROFILE = "controller_profile"
    STRATEGY_SCRIPT = "strategy_script"


class PromotionEvidence(BaseModel):
    adapter_tests_passed: bool = False
    stop_path_verified: bool = False
    backtest_passed: bool = False
    walk_forward_passed: bool = False
    costs_included: bool = False
    paper_hours: float = Field(default=0, ge=0)
    paper_scorecard_passed: bool = False
    canary_approved: bool = False
    live_release_approved: bool = False
    evidence_refs: List[str] = Field(default_factory=list)


class StrategyAdapterSpec(BaseModel):
    name: str
    candidate_name: str
    target: str
    execution_mode: AdapterExecutionMode
    required_features: List[str]
    risk_controls: List[str]
    intended_regimes: List[str]
    minimum_paper_hours: int = Field(default=24, ge=1)


class PromotionAssessment(BaseModel):
    strategy: str
    adapter: str
    stage: PromotionStage
    live_enabled: bool
    completed_gates: List[str]
    blocking_gates: List[str]


class PromotionEngine:
    """Deterministic, fail-closed promotion gates shared by every adapter."""

    @staticmethod
    def assess(spec: StrategyAdapterSpec, evidence: PromotionEvidence) -> PromotionAssessment:
        completed: List[str] = []
        blocking: List[str] = []

        adapter_ready = evidence.adapter_tests_passed and evidence.stop_path_verified
        if evidence.adapter_tests_passed:
            completed.append("adapter_tests_passed")
        else:
            blocking.append("adapter_tests_required")
        if evidence.stop_path_verified:
            completed.append("stop_path_verified")
        else:
            blocking.append("stop_path_verification_required")

        backtest_ready = (
            evidence.backtest_passed
            and evidence.walk_forward_passed
            and evidence.costs_included
        )
        if backtest_ready:
            completed.append("backtest_and_walk_forward_passed")
        else:
            blocking.append("cost_adjusted_walk_forward_required")

        paper_ready = (
            evidence.paper_scorecard_passed
            and evidence.paper_hours >= spec.minimum_paper_hours
        )
        if paper_ready:
            completed.append("paper_scorecard_passed")
        else:
            blocking.append(f"paper_scorecard_{spec.minimum_paper_hours}h_required")

        stage = PromotionStage.SHADOW
        if adapter_ready and backtest_ready:
            stage = PromotionStage.BACKTEST_PASSED
        if stage == PromotionStage.BACKTEST_PASSED and paper_ready:
            stage = PromotionStage.PAPER_ENABLED
        if stage == PromotionStage.PAPER_ENABLED and evidence.canary_approved:
            stage = PromotionStage.LIVE_CANARY
            completed.append("canary_approved")
        elif not evidence.canary_approved:
            blocking.append("manual_canary_approval_required")
        if stage == PromotionStage.LIVE_CANARY and evidence.live_release_approved:
            stage = PromotionStage.LIVE_ENABLED
            completed.append("live_release_approved")
        elif not evidence.live_release_approved:
            blocking.append("manual_live_release_approval_required")

        return PromotionAssessment(
            strategy=spec.candidate_name,
            adapter=spec.name,
            stage=stage,
            live_enabled=stage == PromotionStage.LIVE_ENABLED,
            completed_gates=completed,
            blocking_gates=blocking,
        )


def assess_registry(
    adapters: Dict[str, "StrategyAdapter"],
    evidence: Dict[str, PromotionEvidence],
) -> Dict[str, PromotionAssessment]:
    return {
        name: adapter.assess(evidence.get(name, PromotionEvidence()))
        for name, adapter in adapters.items()
    }
