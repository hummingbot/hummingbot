from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hummingbot.strategy_v2.evolution.models import (
    AutoActionSpec,
    EvolutionPolicy,
    StrategySpec,
)


@dataclass(frozen=True)
class EvolutionConfig:
    root: Path
    policy: EvolutionPolicy
    strategies: tuple[StrategySpec, ...]

    def strategy(self, strategy_id: str) -> StrategySpec:
        for spec in self.strategies:
            if spec.strategy_id == strategy_id:
                return spec
        raise KeyError(f"unknown strategy: {strategy_id}")


def load_evolution_config(path: Path, *, root: Path | None = None) -> EvolutionConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("strategy evolution config must be an object")
    policy_payload = payload.get("policy") or {}
    policy = EvolutionPolicy(
        same_problem_limit=_positive_int(policy_payload, "same_problem_limit", 3),
        recovery_healthy_cycles=_positive_int(
            policy_payload, "recovery_healthy_cycles", 2
        ),
        max_parameter_changes_per_cycle=_positive_int(
            policy_payload, "max_parameter_changes_per_cycle", 1
        ),
        minimum_challenger_improvement=float(
            policy_payload.get("minimum_challenger_improvement", 0.02)
        ),
        maximum_drawdown_degradation=float(
            policy_payload.get("maximum_drawdown_degradation", 0.0)
        ),
        experiment_runtime=str(policy_payload.get("experiment_runtime", "host")),
        docker_image=str(
            policy_payload.get("docker_image", "hummingbot/hummingbot:latest")
        ),
        auto_start_paper_candidates=bool(
            policy_payload.get("auto_start_paper_candidates", False)
        ),
        paper_startup_timeout_seconds=_positive_int(
            policy_payload, "paper_startup_timeout_seconds", 600
        ),
        research_rejection_cooldown_seconds=_positive_int(
            policy_payload, "research_rejection_cooldown_seconds", 3600
        ),
        maximum_research_rejection_cooldown_seconds=_positive_int(
            policy_payload, "maximum_research_rejection_cooldown_seconds", 86400
        ),
        allow_live_actions=bool(policy_payload.get("allow_live_actions", False)),
        require_manual_canary=bool(policy_payload.get("require_manual_canary", True)),
        require_manual_live_release=bool(
            policy_payload.get("require_manual_live_release", True)
        ),
    )
    if policy.allow_live_actions:
        raise ValueError("the evolution supervisor does not permit live actions")
    if policy.minimum_challenger_improvement < 0:
        raise ValueError("minimum_challenger_improvement cannot be negative")
    if policy.maximum_drawdown_degradation < 0:
        raise ValueError("maximum_drawdown_degradation cannot be negative")
    if (
        policy.maximum_research_rejection_cooldown_seconds
        < policy.research_rejection_cooldown_seconds
    ):
        raise ValueError(
            "maximum_research_rejection_cooldown_seconds cannot be smaller than the initial cooldown"
        )
    if policy.experiment_runtime not in {"host", "docker"}:
        raise ValueError("experiment_runtime must be host or docker")
    if not policy.docker_image.strip():
        raise ValueError("docker_image cannot be empty")

    strategies: list[StrategySpec] = []
    seen: set[str] = set()
    for item in payload.get("strategies") or []:
        if not isinstance(item, dict):
            raise ValueError("each strategy definition must be an object")
        strategy_id = str(item.get("id") or "").strip()
        if not strategy_id or strategy_id in seen:
            raise ValueError(f"missing or duplicate strategy id: {strategy_id}")
        seen.add(strategy_id)
        checks = tuple(
            tuple(str(part) for part in command) for command in item.get("checks") or []
        )
        if any(not command for command in checks):
            raise ValueError(f"empty check command for strategy: {strategy_id}")
        automation = tuple(
            _auto_action(row, strategy_id) for row in item.get("automation") or []
        )
        strategies.append(
            StrategySpec(
                strategy_id=strategy_id,
                name=str(item.get("name") or strategy_id),
                family=str(item.get("family") or "unknown"),
                thesis=str(item.get("thesis") or ""),
                target=str(item.get("target") or ""),
                evidence_file=_required(item, "evidence_file", strategy_id),
                walk_forward_file=_required(item, "walk_forward_file", strategy_id),
                runtime_file=_optional(item.get("runtime_file")),
                database_file=_optional(item.get("database_file")),
                minimum_paper_hours=float(item.get("minimum_paper_hours", 24)),
                minimum_paper_fills=int(item.get("minimum_paper_fills", 20)),
                maximum_paper_loss_quote=float(
                    item.get("maximum_paper_loss_quote", -25)
                ),
                maximum_evidence_age_hours=float(
                    item.get("maximum_evidence_age_hours", 168)
                ),
                maximum_runtime_age_seconds=int(
                    item.get("maximum_runtime_age_seconds", 120)
                ),
                checks=checks,
                automation=automation,
            )
        )
    if not strategies:
        raise ValueError("at least one strategy is required")
    project_root = (root or path.resolve().parents[1]).resolve()
    return EvolutionConfig(
        root=project_root, policy=policy, strategies=tuple(strategies)
    )


def _required(payload: dict[str, Any], key: str, strategy_id: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{strategy_id} is missing {key}")
    return value


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(payload: dict[str, Any], key: str, default: int) -> int:
    value = int(payload.get(key, default))
    if value < 1:
        raise ValueError(f"{key} must be positive")
    return value


def _auto_action(payload: dict[str, Any], strategy_id: str) -> AutoActionSpec:
    if not isinstance(payload, dict):
        raise ValueError(f"invalid automation entry for strategy: {strategy_id}")
    action = str(payload.get("action") or "").strip()
    command = tuple(str(part) for part in payload.get("command") or [])
    artifact_json = str(payload.get("artifact_json") or "").strip()
    if not action or not command or not artifact_json:
        raise ValueError(f"incomplete automation entry for strategy: {strategy_id}")
    if action not in {"run_cost_walk_forward", "refresh_walk_forward"}:
        raise ValueError(f"automation action is not allowlisted: {action}")
    return AutoActionSpec(
        action=action,
        command=command,
        artifact_json=artifact_json,
        timeout_seconds=max(30, int(payload.get("timeout_seconds", 1800))),
    )
