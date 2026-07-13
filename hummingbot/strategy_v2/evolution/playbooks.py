from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hummingbot.strategy_v2.evolution.models import ExperimentPlan, StrategySpec


@dataclass(frozen=True)
class ParameterAxis:
    name: str
    minimum: float
    maximum: float
    relative_step: float
    integer: bool = False


@dataclass(frozen=True)
class StrategyPlaybook:
    defaults: dict[str, Any]
    axes: tuple[ParameterAxis, ...]


PLAYBOOKS = {
    "pmm_mister": StrategyPlaybook(
        defaults={"spread": 0.002, "take_profit": 0.003, "refresh_seconds": 120},
        axes=(
            ParameterAxis("spread", 0.00025, 0.004, 0.25),
            ParameterAxis("take_profit", 0.0005, 0.008, 0.25),
            ParameterAxis("refresh_seconds", 15, 300, 0.5, True),
        ),
    ),
    "funding_rate_arb": StrategyPlaybook(
        defaults={
            "minimum_daily_rate_difference": 0.002,
            "take_profit_pct": 0.005,
            "maximum_hold_hours": 48,
            "reversal_stop_pct": -0.001,
            "maximum_entry_basis_pct": 0.02,
        },
        axes=(
            ParameterAxis("minimum_daily_rate_difference", 0.0005, 0.01, 0.25),
            ParameterAxis("take_profit_pct", 0.001, 0.02, 0.25),
            ParameterAxis("maximum_hold_hours", 8, 168, 0.5, True),
        ),
    ),
    "supertrend_v1": StrategyPlaybook(
        defaults={"length": 20, "multiplier": 4.0, "percentage_threshold": 0.01},
        axes=(
            ParameterAxis("length", 5, 100, 0.5, True),
            ParameterAxis("multiplier", 1.5, 8.0, 0.25),
            ParameterAxis("percentage_threshold", 0.002, 0.05, 0.25),
        ),
    ),
}


class CandidatePlaybook:
    """Produces a one-axis candidate matrix from the latest accepted evidence."""

    def __init__(self, root: Path):
        self.root = root

    def generate(
        self,
        spec: StrategySpec,
        plan: ExperimentPlan,
        output: Path,
    ) -> dict[str, Any]:
        playbook = PLAYBOOKS.get(spec.strategy_id)
        if playbook is None:
            raise ValueError(f"no parameter playbook for {spec.strategy_id}")
        baseline, source = self._baseline(spec, playbook)
        feedback = self._axis_feedback(spec, playbook)
        cycle_index = _cycle_index(plan.experiment_id)
        preferred_axis = (cycle_index - 1) % len(playbook.axes)
        axis = min(
            playbook.axes,
            key=lambda item: (
                feedback[item.name]["trials"],
                (playbook.axes.index(item) - preferred_axis) % len(playbook.axes),
            ),
        )
        current = float(baseline[axis.name])
        step = axis.relative_step / (
            2 ** min(feedback[axis.name]["consecutive_losses"], 4)
        )
        evaluated = self._evaluated_parameters(spec)
        candidates = []
        for _ in range(6):
            low = _bounded(current * (1 - step), axis)
            high = _bounded(current * (1 + step), axis)
            candidates = [dict(baseline)]
            for value in (low, high):
                candidate = dict(baseline)
                candidate[axis.name] = (
                    int(round(value)) if axis.integer else _clean_float(value)
                )
                if (
                    candidate not in candidates
                    and _canonical(candidate) not in evaluated
                ):
                    candidates.append(candidate)
            if len(candidates) > 1:
                break
            step /= 2
        if len(candidates) <= 1:
            raise ValueError(
                f"candidate space exhausted for {spec.strategy_id}:{axis.name}"
            )
        payload = {
            "version": 1,
            "strategy_id": spec.strategy_id,
            "experiment_id": plan.experiment_id,
            "hypothesis": plan.hypothesis,
            "source": source,
            "single_axis": axis.name,
            "change_budget": plan.change_budget,
            "bounds": {"minimum": axis.minimum, "maximum": axis.maximum},
            "feedback": feedback[axis.name],
            "effective_relative_step": step,
            "candidates": candidates,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(f"{output.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(output)
        return payload

    def _baseline(
        self,
        spec: StrategySpec,
        playbook: StrategyPlaybook,
    ) -> tuple[dict[str, Any], str]:
        accepted = (
            self.root
            / "data"
            / "strategy-evolution"
            / "strategies"
            / spec.strategy_id
            / "accepted-evidence.json"
        )
        report_paths = []
        champion = (
            self.root
            / "data"
            / "strategy-evolution"
            / "strategies"
            / spec.strategy_id
            / "research-champion.json"
        )
        if champion.exists():
            try:
                payload = json.loads(champion.read_text(encoding="utf-8"))
                parameters = payload.get("parameters")
                if isinstance(parameters, dict) and all(
                    key in parameters for key in playbook.defaults
                ):
                    return (
                        {key: parameters[key] for key in playbook.defaults},
                        str(champion.relative_to(self.root)),
                    )
            except (OSError, json.JSONDecodeError):
                pass
        if accepted.exists():
            try:
                pointer = json.loads(accepted.read_text(encoding="utf-8"))
                artifact = pointer.get("artifact")
                if artifact:
                    report_paths.append(self.root / str(artifact))
            except (OSError, json.JSONDecodeError):
                pass
        report_paths.append(self.root / spec.walk_forward_file)
        for path in report_paths:
            parameters = _most_common_selected_parameters(path)
            if parameters and all(key in parameters for key in playbook.defaults):
                return {key: parameters[key] for key in playbook.defaults}, str(
                    path.relative_to(self.root)
                )
        return dict(playbook.defaults), "playbook_default"

    def _axis_feedback(
        self, spec: StrategySpec, playbook: StrategyPlaybook
    ) -> dict[str, dict[str, Any]]:
        feedback = {
            axis.name: {"trials": 0, "wins": 0, "losses": 0, "consecutive_losses": 0}
            for axis in playbook.axes
        }
        directory = (
            self.root
            / "data"
            / "strategy-evolution"
            / "strategies"
            / spec.strategy_id
            / "evaluations"
        )
        for path in sorted(directory.glob("*.json")):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            axis = feedback.get(str(row.get("changed_axis")))
            if axis is None:
                continue
            axis["trials"] += 1
            if row.get("decision") in {"bootstrap_champion", "promote_challenger"}:
                axis["wins"] += 1
                axis["consecutive_losses"] = 0
            elif row.get("decision") == "reject_challenger":
                axis["losses"] += 1
                axis["consecutive_losses"] += 1
        return feedback

    def _evaluated_parameters(self, spec: StrategySpec) -> set[str]:
        directory = (
            self.root
            / "data"
            / "strategy-evolution"
            / "strategies"
            / spec.strategy_id
            / "evaluations"
        )
        seen = set()
        for path in directory.glob("*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(row.get("parameters"), dict):
                seen.add(_canonical(row["parameters"]))
            for parameters in row.get("proposed_parameters") or []:
                if isinstance(parameters, dict):
                    seen.add(_canonical(parameters))
        return seen


def _most_common_selected_parameters(path: Path) -> dict[str, Any] | None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rows = [
        fold.get("selected_parameters")
        for fold in report.get("folds") or []
        if isinstance(fold, dict) and isinstance(fold.get("selected_parameters"), dict)
    ]
    if not rows:
        return None
    encoded = Counter(json.dumps(row, sort_keys=True) for row in rows)
    return json.loads(encoded.most_common(1)[0][0])


def _cycle_index(experiment_id: str) -> int:
    match = re.search(r"-i(\d+)-", experiment_id)
    return max(1, int(match.group(1))) if match else 1


def _bounded(value: float, axis: ParameterAxis) -> float:
    return min(axis.maximum, max(axis.minimum, value))


def _clean_float(value: float) -> float:
    return float(f"{value:.10g}")


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
