from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from hummingbot.strategy_v2.evolution.config import EvolutionConfig
from hummingbot.strategy_v2.evolution.automation import (
    IntelligentStrategySelector,
    SafeExperimentExecutor,
)
from hummingbot.strategy_v2.evolution.engine import StrategyEvolutionEngine
from hummingbot.strategy_v2.evolution.evidence import EvidenceCollector
from hummingbot.strategy_v2.evolution.models import CycleStatus, EvolutionStage
from hummingbot.strategy_v2.evolution.operations import runtime_identity
from hummingbot.strategy_v2.evolution.paper import PaperCandidateStager
from hummingbot.strategy_v2.evolution.store import EvolutionStore


class EvolutionSupervisor:
    """Runs one isolated evidence cycle per strategy and never places orders."""

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.collector = EvidenceCollector(
            config.root,
            check_runtime=config.policy.experiment_runtime,
            docker_image=config.policy.docker_image,
        )
        self.engine = StrategyEvolutionEngine(config.policy)
        self.store = EvolutionStore(config.root, config.policy)
        self.selector = IntelligentStrategySelector(config)
        self.executor = SafeExperimentExecutor(config)
        self.paper_deployments = PaperCandidateStager(config)

    def run_once(
        self,
        *,
        strategy_ids: list[str] | None = None,
        run_checks: bool = False,
        auto_experiment: bool = False,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.now(timezone.utc)
        previous_heartbeat = self.store.read_heartbeat()
        identity = runtime_identity(self.config.root)
        self.store.save_heartbeat(
            {
                "version": 3,
                "status": "running",
                "phase": "collecting_evidence",
                "liveness_status": "running",
                "readiness_status": "starting",
                "safety_status": "unknown",
                "pid": os.getpid(),
                "cycle_started_at": now.isoformat(),
                "last_activity": now.isoformat(),
                "last_success": previous_heartbeat.get("last_success"),
                "last_error": None,
                "runtime_identity": identity,
            }
        )
        run_checks = run_checks or auto_experiment
        selected = set(strategy_ids or [])
        unknown = selected - {spec.strategy_id for spec in self.config.strategies}
        if unknown:
            raise ValueError(f"unknown strategies: {', '.join(sorted(unknown))}")
        rows = []
        for spec in self.config.strategies:
            if selected and spec.strategy_id not in selected:
                continue
            try:
                evidence = self.collector.collect(spec, now=now, run_checks=run_checks)
                paper_deployment = self.paper_deployments.reconcile_and_maybe_activate(
                    spec, evidence
                )
                previous = self.store.load_state(spec.strategy_id)
                state, result = self.engine.advance(spec, evidence, previous, now=now)
                if (
                    paper_deployment
                    and paper_deployment.get("status") == "active_verified"
                ):
                    state.active_paper_candidate_id = str(
                        paper_deployment.get("candidate_id")
                    )
                elif paper_deployment and str(
                    paper_deployment.get("status", "")
                ).startswith("rollback"):
                    state.active_paper_candidate_id = None
                if (
                    result.stage_after == EvolutionStage.PAPER_PASSED
                    and evidence.accepted_candidate_id
                ):
                    self.paper_deployments.promote_paper_candidate(
                        spec, evidence.accepted_candidate_id
                    )
                row = result.to_dict()
                row["paper_deployment"] = paper_deployment
                row["automation_control"] = {
                    "experiment_failure_count": state.experiment_failure_count,
                    "next_experiment_after": state.next_experiment_after,
                }
                self.store.save_cycle(state, row)
            except Exception as exc:  # noqa: BLE001
                row = {
                    "strategy_id": spec.strategy_id,
                    "strategy_name": spec.name,
                    "status": CycleStatus.ERROR.value,
                    "generated_at": now.isoformat(),
                    "error": str(exc)[:500],
                    "next_step": "该策略本轮失败，其他策略继续；修复后从原状态重试。",
                }
                self.store.save_strategy_error(spec.strategy_id, row)
                self.store.record_alert(
                    severity="error",
                    source=f"strategy:{spec.strategy_id}",
                    message=str(exc)[:500],
                    context={"generated_at": now.isoformat()},
                )
            rows.append(row)
        execution = None
        if auto_experiment:
            selection = self.selector.select(rows)
            if selection:
                spec, experiment = selection
                try:
                    self.store.start_experiment(
                        spec.strategy_id, experiment.experiment_id
                    )
                    execution = self.executor.execute(spec, experiment).__dict__
                except Exception as exc:  # noqa: BLE001
                    execution = {
                        "experiment_id": experiment.experiment_id,
                        "strategy_id": spec.strategy_id,
                        "action": experiment.action,
                        "status": "failed",
                        "verdict": "executor_error",
                        "error": str(exc)[:500],
                    }
                try:
                    self.store.finish_experiment(execution)
                except Exception as exc:  # noqa: BLE001
                    execution["state_feedback_error"] = str(exc)[:500]
            else:
                execution = {
                    "status": "idle",
                    "verdict": "no_safe_actionable_experiment",
                }
        payload = {
            "version": 3,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": (
                "safe_automatic_experiment"
                if auto_experiment
                else (
                    "read_only_evidence_and_checks"
                    if run_checks
                    else "read_only_evidence"
                )
            ),
            "policy": {
                "allow_live_actions": self.config.policy.allow_live_actions,
                "max_parameter_changes_per_cycle": self.config.policy.max_parameter_changes_per_cycle,
                "same_problem_limit": self.config.policy.same_problem_limit,
                "auto_start_paper_candidates": self.config.policy.auto_start_paper_candidates,
            },
            "summary": _summary(rows),
            "experiment_execution": execution,
            "strategies": rows,
            "runtime_identity": identity,
        }
        self.store.save_supervisor_snapshot(payload)
        completed_at = datetime.now(timezone.utc).isoformat()
        error_rows = [
            row for row in rows if row.get("status") == CycleStatus.ERROR.value
        ]
        safety_issues = _safety_issues(rows)
        heartbeat_status = "degraded" if error_rows or safety_issues else "healthy"
        last_error = (
            error_rows[0].get("error")
            if error_rows
            else (safety_issues[0] if safety_issues else None)
        )
        previous_issues = previous_heartbeat.get("safety_issues") or []
        if safety_issues and safety_issues != previous_issues:
            self.store.record_alert(
                severity="critical",
                source="strategy-safety",
                message=safety_issues[0],
                context={"issues": safety_issues},
            )
        self.store.save_heartbeat(
            {
                "version": 3,
                "status": heartbeat_status,
                "phase": "sleeping" if heartbeat_status == "healthy" else "degraded",
                "liveness_status": "healthy",
                "readiness_status": "ready"
                if not safety_issues and not error_rows
                else "degraded",
                "safety_status": "safe" if not safety_issues else "unsafe",
                "safety_issues": safety_issues,
                "pid": os.getpid(),
                "cycle_started_at": now.isoformat(),
                "last_activity": completed_at,
                "last_cycle_completed": completed_at,
                "last_success": (
                    completed_at
                    if heartbeat_status == "healthy"
                    else previous_heartbeat.get("last_success")
                ),
                "last_error": last_error,
                "mode": payload["mode"],
                "summary": payload["summary"],
                "runtime_identity": identity,
            }
        )
        _atomic_write_text(
            self.config.root / "data" / "strategy-evolution" / "latest.md",
            render_supervisor_markdown(payload),
        )
        return payload

    def recover_in_flight_experiments(self) -> list[dict]:
        recovered = []
        for spec in self.config.strategies:
            try:
                result = self.store.recover_in_flight(spec.strategy_id)
            except Exception as exc:  # noqa: BLE001
                self.store.record_alert(
                    severity="critical",
                    source=f"experiment-recovery:{spec.strategy_id}",
                    message=str(exc)[:500],
                )
                recovered.append(
                    {
                        "strategy_id": spec.strategy_id,
                        "recovered": False,
                        "error": str(exc)[:500],
                    }
                )
                continue
            if result:
                recovered.append(result)
                self.store.record_alert(
                    severity="warning",
                    source=f"experiment-recovery:{spec.strategy_id}",
                    message=f"reconciled interrupted experiment {result['experiment_id']}",
                    context=result,
                )
        return recovered

    @contextmanager
    def lock(self) -> Iterator[None]:
        path = self.config.root / "data" / "strategy-evolution" / "supervisor.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("另一个策略进化监督器正在运行") from exc
            handle.seek(0)
            handle.truncate()
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def render_supervisor_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# 多策略进化 Loop 战报",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- 模式：{payload['mode']}",
        f"- 策略数：{summary['total']}",
        f"- 状态：{summary['by_status']}",
        f"- 自动实盘动作：{payload['policy']['allow_live_actions']}",
        "",
    ]
    if payload.get("experiment_execution"):
        execution = payload["experiment_execution"]
        lines.extend(
            [
                "## 本轮自动实验",
                "",
                f"- 状态：{execution.get('status')}",
                f"- 策略：{execution.get('strategy_id', '无')}",
                f"- 动作：{execution.get('action', '无')}",
                f"- 判决：{execution.get('verdict')}",
                "",
            ]
        )
    for row in payload["strategies"]:
        lines.extend(
            [
                f"## {row['strategy_name']} (`{row['strategy_id']}`)",
                "",
                f"- 状态：{row['status']}",
                f"- 阶段：{row.get('stage_before', '?')} → {row.get('stage_after', '?')}",
                f"- 运行状态：{row.get('run_status_before', '?')} → {row.get('run_status_after', '?')}",
                f"- 诊断：{row.get('diagnostic_signature', row.get('error', 'healthy'))}",
                f"- 下一步：{row['next_step']}",
            ]
        )
        experiment = row.get("experiment") or {}
        if experiment:
            lines.append(
                f"- 实验：{experiment.get('hypothesis')}；动作={experiment.get('action')}；"
                f"变更预算={experiment.get('change_budget')}；自动执行={experiment.get('auto_executable')}"
            )
        deployment = row.get("paper_deployment") or {}
        if deployment:
            lines.append(
                f"- 纸盘候选：{deployment.get('candidate_id')}；"
                f"状态={deployment.get('status')}"
            )
        blockers = [
            gate
            for gate in row.get("gates", [])
            if gate.get("status") not in {"pass", "manual"}
        ]
        for gate in blockers:
            lines.append(f"- [{gate['status']}] {gate['label']}：{gate['actual']}")
        lines.append("")
    return "\n".join(lines)


def _summary(rows: list[dict]) -> dict:
    by_status: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status", "unknown"))
        by_status[status] = by_status.get(status, 0) + 1
    return {"total": len(rows), "by_status": dict(sorted(by_status.items()))}


def _safety_issues(rows: list[dict]) -> list[str]:
    issues = []
    for row in rows:
        strategy_id = str(row.get("strategy_id") or "unknown")
        status = str(row.get("status") or "")
        if status == CycleStatus.CIRCUIT_OPEN.value:
            issues.append(f"{strategy_id}:circuit_open")
        deployment_status = str((row.get("paper_deployment") or {}).get("status") or "")
        if deployment_status.startswith("rollback") or deployment_status in {
            "startup_failed",
            "staging_failed",
        }:
            issues.append(f"{strategy_id}:paper_{deployment_status}")
    return sorted(set(issues))


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)
