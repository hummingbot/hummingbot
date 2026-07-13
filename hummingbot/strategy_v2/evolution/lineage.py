from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hummingbot.strategy_v2.evolution.config import EvolutionConfig
from hummingbot.strategy_v2.evolution.models import ExperimentPlan, StrategySpec


class CandidateLineageStore:
    """Keeps immutable candidate records and atomic champion pointers."""

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.root = config.root.resolve()

    def record_validation(
        self,
        spec: StrategySpec,
        plan: ExperimentPlan,
        candidate_payload: dict[str, Any],
        artifact: Path,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        parameters, stable, selected_folds, candidate_summary = _candidate_evaluation(
            report
        )
        candidates = candidate_payload.get("candidates") or []
        if not parameters or parameters not in candidates:
            raise ValueError(
                "report selected parameters are not an exact proposed candidate"
            )
        completed_folds = int((report.get("summary") or {}).get("completed_folds") or 0)
        if completed_folds < 3 or selected_folds != completed_folds:
            raise ValueError("report fold lineage is incomplete")
        code_hash = self._code_hash(spec, plan)
        parameter_hash = _hash_json(parameters)
        dataset_hash = _hash_json(
            {
                "configuration": report.get("configuration") or {},
                "cost_model": report.get("cost_model") or {},
                "data_sources": report.get("data_sources") or {},
            }
        )
        candidate_id = f"{spec.strategy_id}-{_hash_json({'code': code_hash, 'parameters': parameters})[:12]}"
        strategy_dir = (
            self.root / "data" / "strategy-evolution" / "strategies" / spec.strategy_id
        )
        champion = _read_json(strategy_dir / "research-champion.json")
        same_as_champion = champion.get("candidate_id") == candidate_id
        summary = candidate_summary or report.get("summary") or {}
        record = {
            "version": 1,
            "candidate_id": candidate_id,
            "strategy_id": spec.strategy_id,
            "parent_id": (
                champion.get("parent_id")
                if same_as_champion
                else champion.get("candidate_id")
            ),
            "generation": (
                int(champion.get("generation", 0))
                if same_as_champion
                else int(champion.get("generation", -1)) + 1
            ),
            "code_hash": code_hash,
            "parameter_hash": parameter_hash,
            "parameters": parameters,
            "changed_axis": candidate_payload.get("single_axis"),
            "hypothesis": plan.hypothesis,
            "source_experiment_id": plan.experiment_id,
            "dataset_fingerprint": dataset_hash,
            "artifact": str(artifact.resolve().relative_to(self.root)),
            "artifact_sha256": _sha256_file(artifact),
            "metrics": {
                "adjusted_net_quote": summary.get("total_adjusted_net_quote"),
                "maximum_drawdown_pct": summary.get("maximum_drawdown_pct"),
                "profitable_fold_ratio": summary.get("profitable_fold_ratio"),
                "total_positions": summary.get("total_positions"),
                "completed_folds": summary.get("completed_folds"),
            },
            "stable_across_folds": stable,
            "status": "validated_challenger",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        decision, reasons = self._compare(champion, record)
        record["decision"] = decision
        record["reason_codes"] = reasons
        if decision in {"bootstrap_champion", "promote_challenger", "retain_champion"}:
            record["status"] = "research_champion"
        self._write_candidate(strategy_dir, record)
        self._write_evaluation(strategy_dir, record)
        self._append_event(strategy_dir, "evaluation_completed", record)
        if decision in {"bootstrap_champion", "promote_challenger"}:
            if champion:
                _atomic_json(strategy_dir / "previous-research-champion.json", champion)
            _atomic_json(strategy_dir / "research-champion.json", record)
            self._append_event(strategy_dir, "research_champion_promoted", record)
        elif decision == "retain_champion":
            self._append_event(strategy_dir, "research_champion_retained", record)
        else:
            _atomic_json(strategy_dir / "challenger.json", record)
            self._append_event(strategy_dir, "challenger_rejected", record)
        return record

    def record_failed_validation(
        self,
        spec: StrategySpec,
        plan: ExperimentPlan,
        candidate_payload: dict[str, Any],
        artifact: Path,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        proposed = [
            dict(parameters)
            for parameters in candidate_payload.get("candidates") or []
            if isinstance(parameters, dict)
        ]
        if not proposed:
            raise ValueError("failed validation has no proposed candidates")
        selected, stable, _, selected_summary = _candidate_evaluation(report)
        if selected not in proposed:
            selected = proposed[0]
            stable = False
        summary = selected_summary or report.get("summary") or {}
        code_hash = self._code_hash(spec, plan)
        parameter_hash = _hash_json(selected)
        dataset_hash = _hash_json(
            {
                "configuration": report.get("configuration") or {},
                "cost_model": report.get("cost_model") or {},
                "data_sources": report.get("data_sources") or {},
            }
        )
        candidate_id = (
            f"{spec.strategy_id}-"
            f"{_hash_json({'code': code_hash, 'parameters': selected})[:12]}"
        )
        strategy_dir = (
            self.root / "data" / "strategy-evolution" / "strategies" / spec.strategy_id
        )
        champion = _read_json(strategy_dir / "research-champion.json")
        reasons = ["absolute_validation_failed"]
        if int(summary.get("completed_folds") or 0) < 3:
            reasons.append("insufficient_completed_folds")
        if _number(summary.get("total_positions")) <= 0:
            reasons.append("no_oos_positions")
        if _number(summary.get("total_adjusted_net_quote")) <= 0:
            reasons.append("non_positive_adjusted_net_quote")
        if _number(summary.get("profitable_fold_ratio")) <= 0:
            reasons.append("no_profitable_oos_folds")
        record = {
            "version": 1,
            "candidate_id": candidate_id,
            "strategy_id": spec.strategy_id,
            "parent_id": champion.get("candidate_id"),
            "generation": int(champion.get("generation", -1)) + 1,
            "code_hash": code_hash,
            "parameter_hash": parameter_hash,
            "parameters": selected,
            "proposed_parameters": proposed,
            "changed_axis": candidate_payload.get("single_axis"),
            "hypothesis": plan.hypothesis,
            "source_experiment_id": plan.experiment_id,
            "dataset_fingerprint": dataset_hash,
            "artifact": str(artifact.resolve().relative_to(self.root)),
            "artifact_sha256": _sha256_file(artifact),
            "metrics": {
                "adjusted_net_quote": summary.get("total_adjusted_net_quote"),
                "maximum_drawdown_pct": summary.get("maximum_drawdown_pct"),
                "profitable_fold_ratio": summary.get("profitable_fold_ratio"),
                "total_positions": summary.get("total_positions"),
                "completed_folds": summary.get("completed_folds"),
            },
            "stable_across_folds": stable,
            "status": "rejected_research_candidate",
            "decision": "reject_challenger",
            "reason_codes": reasons,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_candidate(strategy_dir, record)
        self._write_evaluation(strategy_dir, record)
        _atomic_json(strategy_dir / "last-rejected-challenger.json", record)
        self._append_event(strategy_dir, "challenger_rejected", record)
        return record

    def _compare(
        self, champion: dict[str, Any], challenger: dict[str, Any]
    ) -> tuple[str, list[str]]:
        if not challenger["stable_across_folds"]:
            return "reject_challenger", ["unstable_parameter_selection"]
        if not champion:
            return "bootstrap_champion", ["first_validated_candidate"]
        if champion.get("candidate_id") == challenger["candidate_id"]:
            return "retain_champion", ["same_candidate_revalidated"]
        if champion.get("dataset_fingerprint") != challenger["dataset_fingerprint"]:
            return "reject_challenger", ["unpaired_dataset_window"]
        champion_metrics = champion.get("metrics") or {}
        challenger_metrics = challenger["metrics"]
        old_net = _number(champion_metrics.get("adjusted_net_quote"))
        new_net = _number(challenger_metrics.get("adjusted_net_quote"))
        improvement = (new_net - old_net) / max(abs(old_net), 1.0)
        old_drawdown = _number(champion_metrics.get("maximum_drawdown_pct"))
        new_drawdown = _number(challenger_metrics.get("maximum_drawdown_pct"))
        reasons = []
        if improvement < self.config.policy.minimum_challenger_improvement:
            reasons.append("insufficient_objective_improvement")
        if (
            new_drawdown
            > old_drawdown + self.config.policy.maximum_drawdown_degradation
        ):
            reasons.append("drawdown_degraded")
        if _number(challenger_metrics.get("profitable_fold_ratio")) < _number(
            champion_metrics.get("profitable_fold_ratio")
        ):
            reasons.append("profitable_fold_ratio_degraded")
        return (
            ("reject_challenger", reasons)
            if reasons
            else ("promote_challenger", ["paired_improvement_passed"])
        )

    def _code_hash(self, spec: StrategySpec, plan: ExperimentPlan) -> str:
        digest = hashlib.sha256()
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
        digest.update(result.stdout.strip().encode())
        paths = [self.root / "hummingbot/strategy_v2/evolution"]
        target = self.root / f"{spec.target.replace('.', '/')}.py"
        if target.exists():
            paths.append(target)
        action = spec.auto_action(plan.action)
        if action:
            paths.extend(
                self.root / part
                for part in action.command
                if part.startswith("scripts/")
            )
        for path in paths:
            files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
            for file_path in files:
                if file_path.is_file():
                    digest.update(str(file_path.relative_to(self.root)).encode())
                    digest.update(file_path.read_bytes())
        return digest.hexdigest()

    @staticmethod
    def _write_candidate(strategy_dir: Path, record: dict[str, Any]) -> None:
        path = strategy_dir / "candidates" / record["candidate_id"] / "manifest.json"
        manifest = {
            key: record[key]
            for key in (
                "version",
                "candidate_id",
                "strategy_id",
                "parent_id",
                "generation",
                "code_hash",
                "parameter_hash",
                "parameters",
                "changed_axis",
                "created_at",
            )
        }
        if path.exists():
            existing = _read_json(path)
            comparable = {
                key: value for key, value in manifest.items() if key != "created_at"
            }
            old = {key: value for key, value in existing.items() if key != "created_at"}
            if old != comparable:
                raise ValueError(f"candidate id collision: {record['candidate_id']}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(path, manifest)

    @staticmethod
    def _write_evaluation(strategy_dir: Path, record: dict[str, Any]) -> None:
        evaluation_id = str(record["source_experiment_id"])
        path = strategy_dir / "evaluations" / f"{evaluation_id}.json"
        if path.exists():
            existing = _read_json(path)
            if existing != record:
                raise ValueError(f"evaluation id collision: {evaluation_id}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(path, record)

    @staticmethod
    def _append_event(
        strategy_dir: Path, event_type: str, record: dict[str, Any]
    ) -> None:
        strategy_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "event": event_type,
            "candidate_id": record["candidate_id"],
            "strategy_id": record["strategy_id"],
            "decision": record.get("decision"),
            "reason_codes": record.get("reason_codes") or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with (strategy_dir / "lineage.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())


def _candidate_evaluation(
    report: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool, int, dict[str, Any]]:
    fixed = [
        row
        for row in report.get("candidate_summaries") or []
        if isinstance(row, dict)
        and isinstance(row.get("parameters"), dict)
        and isinstance(row.get("summary"), dict)
        and row["summary"].get("passed")
    ]
    if fixed:
        winner = max(
            fixed,
            key=lambda row: (
                _number(row["summary"].get("total_adjusted_net_quote")),
                _number(row["summary"].get("profitable_fold_ratio")),
                -_number(row["summary"].get("maximum_drawdown_pct")),
                _number(row["summary"].get("total_positions")),
            ),
        )
        completed = int(winner["summary"].get("completed_folds") or 0)
        return winner["parameters"], True, completed, winner["summary"]
    rows = [
        fold.get("selected_parameters")
        for fold in report.get("folds") or []
        if isinstance(fold, dict)
        and fold.get("status") == "completed"
        and isinstance(fold.get("selected_parameters"), dict)
    ]
    if not rows:
        return None, False, 0, {}
    encoded = Counter(json.dumps(row, sort_keys=True) for row in rows)
    selected, count = encoded.most_common(1)[0]
    return json.loads(selected), count == len(rows), len(rows), {}


def _hash_json(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
