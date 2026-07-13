from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hummingbot.strategy_v2.evolution.config import EvolutionConfig
from hummingbot.strategy_v2.evolution.lineage import CandidateLineageStore
from hummingbot.strategy_v2.evolution.models import (
    ExperimentOutcome,
    ExperimentPlan,
    StrategySpec,
)
from hummingbot.strategy_v2.evolution.paper import PaperCandidateStager
from hummingbot.strategy_v2.evolution.playbooks import CandidatePlaybook
from hummingbot.strategy_v2.evolution.runtime import (
    DOCKER_WORKDIR,
    docker_source_mounts,
    docker_source_paths,
)


ALLOWED_WALK_FORWARD_SCRIPTS = {
    "scripts/walk_forward_pmm_mister.py",
    "scripts/walk_forward_funding_arb.py",
    "scripts/walk_forward_supertrend.py",
}


class IntelligentStrategySelector:
    """Selects at most one evidence-producing experiment for the whole cycle."""

    def __init__(self, config: EvolutionConfig):
        self.config = config

    def select(
        self, cycles: list[dict[str, Any]]
    ) -> tuple[StrategySpec, ExperimentPlan] | None:
        rows = {row.get("strategy_id"): row for row in cycles}
        candidates = []
        for order, spec in enumerate(self.config.strategies):
            row = rows.get(spec.strategy_id) or {}
            if row.get("status") in {"circuit_open", "error", "ready_for_human_review"}:
                continue
            ready_after = (row.get("automation_control") or {}).get(
                "next_experiment_after"
            )
            if ready_after:
                try:
                    ready_at = datetime.fromisoformat(
                        str(ready_after).replace("Z", "+00:00")
                    )
                    if ready_at.tzinfo is None:
                        ready_at = ready_at.replace(tzinfo=timezone.utc)
                    if ready_at.astimezone(timezone.utc) > datetime.now(timezone.utc):
                        continue
                except ValueError:
                    continue
            gates = {gate.get("key"): gate for gate in row.get("gates") or []}
            if any(
                (gates.get(key) or {}).get("status") != "pass"
                for key in ("evidence_integrity", "configured_checks")
            ):
                continue
            payload = row.get("experiment") or {}
            if not payload.get("auto_executable"):
                continue
            plan = ExperimentPlan(
                experiment_id=str(payload["experiment_id"]),
                strategy_id=spec.strategy_id,
                hypothesis=str(payload["hypothesis"]),
                action=str(payload["action"]),
                change_budget=int(payload["change_budget"]),
                success_criteria=tuple(payload.get("success_criteria") or []),
                stop_conditions=tuple(payload.get("stop_conditions") or []),
                evidence_required=tuple(payload.get("evidence_required") or []),
                auto_executable=True,
            )
            action_score = {
                "run_cost_walk_forward": 30,
                "refresh_walk_forward": 20,
            }.get(plan.action, 0)
            status_score = 50 if row.get("status") == "blocked" else 10
            failed_gates = sum(
                gate.get("status") == "fail" for gate in row.get("gates") or []
            )
            fairness = -int(row.get("iteration") or 0)
            candidates.append(
                (
                    status_score + action_score + failed_gates * 5,
                    fairness,
                    -order,
                    spec,
                    plan,
                )
            )
        if not candidates:
            return None
        _, _, _, spec, plan = max(candidates, key=lambda item: item[:3])
        return spec, plan


class SafeExperimentExecutor:
    """Executes allowlisted backtest experiments in an isolated data directory."""

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.playbooks = CandidatePlaybook(config.root)
        self.lineage = CandidateLineageStore(config)
        self.paper_stager = PaperCandidateStager(config)

    def execute(self, spec: StrategySpec, plan: ExperimentPlan) -> ExperimentOutcome:
        action = spec.auto_action(plan.action)
        if action is None or not plan.auto_executable:
            return self._outcome(
                plan,
                "skipped",
                "not_allowlisted",
                None,
                None,
                0.0,
                {},
                "action not configured",
            )
        experiment_dir = (
            self.config.root
            / "data"
            / "strategy-evolution"
            / "experiments"
            / plan.experiment_id
        ).resolve()
        experiment_dir.mkdir(parents=True, exist_ok=True)
        for stale_name in (
            "report.json",
            "report.md",
            "outcome.json",
            "candidates.json",
        ):
            stale = experiment_dir / stale_name
            if stale.exists():
                stale.unlink()
        artifact = self._resolve_artifact(action.artifact_json, plan, experiment_dir)
        candidate_json = experiment_dir / "candidates.json"
        command = [
            self._expand(part, plan, experiment_dir, artifact, candidate_json)
            for part in action.command
        ]
        violation = self._validate_command(command, artifact, experiment_dir)
        if violation:
            return self._outcome(
                plan, "rejected", "safety_rejected", artifact, None, 0.0, {}, violation
            )
        try:
            candidate_payload = self.playbooks.generate(spec, plan, candidate_json)
        except ValueError as exc:
            return self._outcome(
                plan,
                "skipped",
                "no_parameter_playbook",
                artifact,
                None,
                0.0,
                {},
                str(exc),
            )

        before = self._git_status()
        before_digest = self._workspace_digest()
        started = time.monotonic()
        env = os.environ.copy()
        env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
        try:
            result = self._run_experiment(
                command,
                experiment_dir=experiment_dir,
                env=env,
                timeout=action.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            outcome = self._outcome(
                plan,
                "failed",
                "execution_error",
                artifact,
                -1,
                time.monotonic() - started,
                {},
                str(exc),
            )
            self._save(experiment_dir, outcome, command)
            return outcome

        elapsed = time.monotonic() - started
        after = self._git_status()
        after_digest = self._workspace_digest()
        unexpected_changes = (
            []
            if self.config.policy.experiment_runtime == "docker"
            else sorted(after - before)
        )
        if unexpected_changes or after_digest != before_digest:
            outcome = self._outcome(
                plan,
                "rejected",
                "workspace_mutation_detected",
                artifact,
                result.returncode,
                elapsed,
                {
                    "unexpected_changes": unexpected_changes,
                    "workspace_digest_changed": after_digest != before_digest,
                },
                "experiment changed files outside its isolated data artifacts",
            )
            self._save(experiment_dir, outcome, command, result)
            return outcome
        if result.returncode != 0:
            error_text = result.stderr or result.stdout
            failure_class, retry_after = self._classify_execution_failure(error_text)
            outcome = self._outcome(
                plan,
                "deferred" if retry_after else "failed",
                failure_class,
                artifact,
                result.returncode,
                elapsed,
                {},
                error_text[-1000:],
                retry_after_seconds=retry_after,
            )
            self._save(experiment_dir, outcome, command, result)
            return outcome
        report = self._read_report(artifact)
        summary = (
            report.get("summary") if isinstance(report.get("summary"), dict) else {}
        )
        report_identity_valid = report.get("strategy") == spec.strategy_id
        passed = bool(
            report_identity_valid
            and report.get("validation_passed")
            and summary.get("passed")
        )
        lineage_record = None
        lineage_error = None
        if passed:
            try:
                lineage_record = self.lineage.record_validation(
                    spec, plan, candidate_payload, artifact, report
                )
            except (OSError, ValueError) as exc:
                passed = False
                lineage_error = str(exc)
        elif report_identity_valid:
            try:
                lineage_record = self.lineage.record_failed_validation(
                    spec, plan, candidate_payload, artifact, report
                )
            except (OSError, ValueError) as exc:
                lineage_error = str(exc)
        accepted = bool(
            passed
            and lineage_record
            and lineage_record.get("decision")
            in {"bootstrap_champion", "promote_challenger", "retain_champion"}
        )
        paper_stage = None
        if accepted and lineage_record:
            try:
                paper_stage = self.paper_stager.stage(spec, lineage_record)
            except (OSError, ValueError) as exc:
                paper_stage = {"status": "staging_failed", "error": str(exc)}
        verdict = (
            "accept_candidate_evidence"
            if accepted
            else (
                "reject_challenger" if lineage_record else "reject_candidate_evidence"
            )
        )
        outcome = self._outcome(
            plan,
            "completed" if lineage_error is None else "rejected",
            verdict,
            artifact,
            result.returncode,
            elapsed,
            {
                "completed_folds": summary.get("completed_folds"),
                "profitable_fold_ratio": summary.get("profitable_fold_ratio"),
                "adjusted_net_quote": summary.get("total_adjusted_net_quote"),
                "maximum_drawdown_pct": summary.get("maximum_drawdown_pct"),
                "total_positions": summary.get("total_positions"),
                "lineage_decision": (
                    lineage_record.get("decision") if lineage_record else None
                ),
                "reason_codes": (
                    lineage_record.get("reason_codes") if lineage_record else []
                ),
                "paper_stage": paper_stage,
            },
            lineage_error,
            candidate_id=(
                str(lineage_record.get("candidate_id")) if lineage_record else None
            ),
        )
        self._save(experiment_dir, outcome, command, result)
        if accepted and lineage_record:
            self._accept_evidence(spec, plan, artifact, report, outcome, lineage_record)
        return outcome

    def _run_experiment(
        self,
        command: list[str],
        *,
        experiment_dir: Path,
        env: dict[str, str],
        timeout: int,
    ) -> subprocess.CompletedProcess:
        if self.config.policy.experiment_runtime == "docker":
            return self._run_docker_experiment(command, experiment_dir, timeout)
        return subprocess.run(
            command,
            cwd=str(self.config.root),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

    def _run_docker_experiment(
        self, command: list[str], experiment_dir: Path, timeout: int
    ) -> subprocess.CompletedProcess:
        docker = shutil.which("docker")
        if not docker:
            bundled = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
            docker = str(bundled) if bundled.is_file() else None
        if not docker:
            raise OSError("Docker runtime is not available")

        def container_argument(part: str) -> str:
            path = Path(part)
            if not path.is_absolute():
                return part
            try:
                relative = path.resolve().relative_to(experiment_dir)
            except ValueError:
                return part
            return str(Path("/output") / relative)

        python_command = ["python", command[1]] + [
            container_argument(part) for part in command[2:]
        ]
        container_name = (
            f"hb-evo-{hashlib.sha256(str(experiment_dir).encode()).hexdigest()[:12]}"
        )
        docker_command = [
            docker,
            "run",
            "--rm",
            "--name",
            container_name,
            "--label",
            "hummingbot.strategy-evolution=true",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONPYCACHEPREFIX=/tmp/pycache",
            "-e",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "-e",
            f"PYTHONPATH={DOCKER_WORKDIR}",
            *docker_source_mounts(self.config.root.resolve()),
            "-v",
            f"{experiment_dir}:/output:rw",
            "-w",
            DOCKER_WORKDIR,
            self.config.policy.docker_image,
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            "hummingbot",
            *python_command,
        ]
        try:
            return subprocess.run(
                docker_command,
                cwd=str(self.config.root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            subprocess.run(
                [docker, "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30,
            )
            raise

    def _validate_command(
        self, command: list[str], artifact: Path, experiment_dir: Path
    ) -> str | None:
        if not command:
            return "empty command"
        if Path(command[0]).name not in {
            "python",
            "python3",
            Path(sys.executable).name,
        }:
            return "only Python experiment commands are allowed"
        if len(command) < 2 or command[1] not in ALLOWED_WALK_FORWARD_SCRIPTS:
            return "command must invoke exactly one allowlisted walk-forward script"
        scripts = [part for part in command[2:] if part.startswith("scripts/")]
        if scripts:
            return "additional script arguments are not allowed"
        if artifact != experiment_dir / "report.json":
            return "artifact must be the isolated experiment report.json"
        for index, part in enumerate(command[:-1]):
            if part in {"--json-output", "--markdown-output"}:
                output = Path(command[index + 1]).resolve()
                if experiment_dir not in output.parents:
                    return "experiment outputs must stay inside the isolated data directory"
        return None

    def _resolve_artifact(
        self, template: str, plan: ExperimentPlan, directory: Path
    ) -> Path:
        rendered = template.replace("{experiment_id}", plan.experiment_id)
        path = (self.config.root / rendered).resolve()
        expected = directory / "report.json"
        if path != expected:
            return path
        return expected

    @staticmethod
    def _expand(
        part: str,
        plan: ExperimentPlan,
        directory: Path,
        artifact: Path,
        candidate_json: Path,
    ) -> str:
        return (
            part.replace("{experiment_id}", plan.experiment_id)
            .replace("{experiment_dir}", str(directory))
            .replace("{artifact_json}", str(artifact))
            .replace("{artifact_md}", str(directory / "report.md"))
            .replace("{candidate_json}", str(candidate_json))
        )

    def _git_status(self) -> set[str]:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(self.config.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
        return set(result.stdout.splitlines())

    def _workspace_digest(self) -> str:
        digest = hashlib.sha256()
        for relative, source in docker_source_paths(self.config.root.resolve()):
            files = sorted(source.rglob("*")) if source.is_dir() else [source]
            for path in files:
                if (
                    not path.is_file()
                    or "__pycache__" in path.parts
                    or path.suffix in {".pyc", ".pyo"}
                    or path.stat().st_size > 10 * 1024 * 1024
                ):
                    continue
                digest.update(relative.encode())
                digest.update(str(path.relative_to(source)).encode())
                digest.update(path.read_bytes())
        return digest.hexdigest()

    @staticmethod
    def _classify_execution_failure(output: str) -> tuple[str, int | None]:
        lowered = output.lower()
        if "http error 429" in lowered or "too many requests" in lowered:
            return "external_rate_limited", 900
        if any(
            marker in lowered
            for marker in (
                "temporary failure in name resolution",
                "connection timed out",
                "connection reset",
                "remote end closed connection",
                "urlopen error",
            )
        ):
            return "external_data_unavailable", 300
        if "modulenotfounderror" in lowered or "no module named" in lowered:
            return "environment_missing", 1800
        return "command_failed", None

    @staticmethod
    def _read_report(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _accept_evidence(
        self,
        spec: StrategySpec,
        plan: ExperimentPlan,
        artifact: Path,
        report: dict[str, Any],
        outcome: ExperimentOutcome,
        lineage_record: dict[str, Any],
    ) -> None:
        target = (
            self.config.root
            / "data"
            / "strategy-evolution"
            / "strategies"
            / spec.strategy_id
            / "accepted-evidence.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "strategy_id": spec.strategy_id,
            "experiment_id": plan.experiment_id,
            "accepted_at": report.get("generated_at"),
            "artifact": str(artifact.relative_to(self.config.root.resolve())),
            "artifact_sha256": lineage_record["artifact_sha256"],
            "candidate_id": lineage_record["candidate_id"],
            "code_hash": lineage_record["code_hash"],
            "parameter_hash": lineage_record["parameter_hash"],
            "parameters": lineage_record["parameters"],
            "dataset_fingerprint": lineage_record["dataset_fingerprint"],
            "backtest_passed": True,
            "walk_forward_passed": True,
            "costs_included": True,
            "outcome": {
                "verdict": outcome.verdict,
                "summary": outcome.summary,
            },
        }
        _atomic_json(target, payload)

    def _outcome(
        self,
        plan: ExperimentPlan,
        status: str,
        verdict: str,
        artifact: Path | None,
        returncode: int | None,
        elapsed: float,
        summary: dict[str, Any],
        error: str | None,
        candidate_id: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> ExperimentOutcome:
        return ExperimentOutcome(
            experiment_id=plan.experiment_id,
            strategy_id=plan.strategy_id,
            action=plan.action,
            status=status,
            verdict=verdict,
            artifact_json=str(artifact) if artifact else None,
            returncode=returncode,
            elapsed_seconds=round(elapsed, 3),
            summary=summary,
            error=error,
            candidate_id=candidate_id,
            execution_runtime=self.config.policy.experiment_runtime,
            retry_after_seconds=retry_after_seconds,
        )

    @staticmethod
    def _save(
        directory: Path,
        outcome: ExperimentOutcome,
        command: list[str],
        result: subprocess.CompletedProcess | None = None,
    ) -> None:
        payload = {
            **outcome.__dict__,
            "command": command,
            "stdout": result.stdout[-4000:] if result else "",
            "stderr": result.stderr[-4000:] if result else "",
        }
        _atomic_json(directory / "outcome.json", payload)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
