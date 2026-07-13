from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class EvolutionStage(str, Enum):
    COLLECTED = "collected"
    SHADOW = "shadow"
    BACKTEST_PASSED = "backtest_passed"
    PAPER_RUNNING = "paper_running"
    PAPER_PASSED = "paper_passed"
    LIVE_CANARY = "live_canary"
    LIVE_ENABLED = "live_enabled"
    ARCHIVED = "archived"


class StrategyRunStatus(str, Enum):
    IDLE = "idle"
    OBSERVING = "observing"
    EXPERIMENTING = "experimenting"
    PAPER_RUNNING = "paper_running"
    PAUSED = "paused"
    CIRCUIT_OPEN = "circuit_open"


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    MISSING = "missing"
    COLLECTING = "collecting"
    MANUAL = "manual"


class CycleStatus(str, Enum):
    ADVANCED = "advanced"
    OBSERVING = "observing"
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_human_review"
    CIRCUIT_OPEN = "circuit_open"
    ERROR = "error"


@dataclass(frozen=True)
class EvolutionPolicy:
    same_problem_limit: int = 3
    recovery_healthy_cycles: int = 2
    max_parameter_changes_per_cycle: int = 1
    minimum_challenger_improvement: float = 0.02
    maximum_drawdown_degradation: float = 0.0
    experiment_runtime: str = "host"
    docker_image: str = "hummingbot/hummingbot:latest"
    auto_start_paper_candidates: bool = False
    paper_startup_timeout_seconds: int = 600
    research_rejection_cooldown_seconds: int = 3600
    maximum_research_rejection_cooldown_seconds: int = 86400
    allow_live_actions: bool = False
    require_manual_canary: bool = True
    require_manual_live_release: bool = True


@dataclass(frozen=True)
class AutoActionSpec:
    action: str
    command: tuple[str, ...]
    artifact_json: str
    timeout_seconds: int = 1800


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    name: str
    family: str
    thesis: str
    target: str
    evidence_file: str
    walk_forward_file: str
    runtime_file: str | None = None
    database_file: str | None = None
    minimum_paper_hours: float = 24.0
    minimum_paper_fills: int = 20
    maximum_paper_loss_quote: float = -25.0
    maximum_evidence_age_hours: float = 168.0
    maximum_runtime_age_seconds: int = 120
    checks: tuple[tuple[str, ...], ...] = ()
    automation: tuple[AutoActionSpec, ...] = ()

    def auto_action(self, action: str) -> AutoActionSpec | None:
        return next((item for item in self.automation if item.action == action), None)


@dataclass
class EvidenceSnapshot:
    collected_at: str
    adapter_tests_passed: bool = False
    stop_path_verified: bool = False
    backtest_passed: bool = False
    walk_forward_passed: bool = False
    costs_included: bool = False
    paper_scorecard_passed: bool = False
    paper_scorecard_candidate_id: str | None = None
    canary_approved: bool = False
    canary_candidate_id: str | None = None
    live_release_approved: bool = False
    live_release_candidate_id: str | None = None
    recovery_verified: bool = False
    checks_executed: bool = False
    walk_forward_exists: bool = False
    walk_forward_age_hours: float | None = None
    runtime_exists: bool = False
    runtime_age_seconds: float | None = None
    runtime_fresh: bool = False
    paper_only: bool = False
    paper_hours: float = 0.0
    paper_orders: int = 0
    paper_fills: int = 0
    paper_pnl_quote: float = 0.0
    accepted_candidate_id: str | None = None
    runtime_candidate_id: str | None = None
    candidate_binding_valid: bool = False
    check_results: list[dict[str, Any]] = field(default_factory=list)
    source_errors: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GateResult:
    key: str
    label: str
    status: GateStatus
    actual: Any
    threshold: Any
    message: str
    blocks_automation: bool = False


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    strategy_id: str
    hypothesis: str
    action: str
    change_budget: int
    success_criteria: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    evidence_required: tuple[str, ...]
    auto_executable: bool = False


@dataclass(frozen=True)
class ExperimentOutcome:
    experiment_id: str
    strategy_id: str
    action: str
    status: str
    verdict: str
    artifact_json: str | None
    returncode: int | None
    elapsed_seconds: float
    summary: dict[str, Any]
    error: str | None = None
    candidate_id: str | None = None
    execution_runtime: str = "host"
    retry_after_seconds: int | None = None


@dataclass
class StrategyState:
    version: int = 3
    strategy_id: str = ""
    iteration: int = 0
    stage: EvolutionStage = EvolutionStage.COLLECTED
    highest_ever_stage: EvolutionStage = EvolutionStage.COLLECTED
    run_status: StrategyRunStatus = StrategyRunStatus.IDLE
    diagnostic_signature: str = "healthy"
    consecutive_same_problem: int = 0
    circuit_open: bool = False
    recovery_healthy_cycles: int = 0
    champion_candidate_id: str | None = None
    challenger_candidate_id: str | None = None
    active_paper_candidate_id: str | None = None
    previous_good_candidate_id: str | None = None
    in_flight_experiment_id: str | None = None
    in_flight_started_at: str | None = None
    last_experiment_id: str | None = None
    last_outcome_verdict: str | None = None
    experiment_failure_count: int = 0
    next_experiment_after: str | None = None
    updated_at: str = ""


@dataclass
class CycleResult:
    strategy_id: str
    strategy_name: str
    iteration: int
    stage_before: EvolutionStage
    stage_after: EvolutionStage
    run_status_before: StrategyRunStatus
    run_status_after: StrategyRunStatus
    status: CycleStatus
    diagnostic_signature: str
    gates: list[GateResult]
    evidence: EvidenceSnapshot
    experiment: ExperimentPlan
    next_step: str
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return _enum_values(asdict(self))


def _enum_values(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _enum_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_values(item) for item in value]
    return value
