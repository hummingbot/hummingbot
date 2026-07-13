from __future__ import annotations

import json
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from hummingbot.strategy_v2.evolution.models import EvidenceSnapshot, StrategySpec
from hummingbot.strategy_v2.evolution.runtime import (
    DOCKER_WORKDIR,
    docker_source_mounts,
)


DECIMAL_SCALE = Decimal("1000000")


class EvidenceCollector:
    """Collects evidence without changing strategy code, config, or runtime."""

    def __init__(
        self,
        root: Path,
        *,
        check_timeout: int = 180,
        check_runtime: str = "host",
        docker_image: str = "hummingbot/hummingbot:latest",
    ):
        self.root = root.resolve()
        self.check_timeout = check_timeout
        self.check_runtime = check_runtime
        self.docker_image = docker_image

    def collect(
        self,
        spec: StrategySpec,
        *,
        now: datetime | None = None,
        run_checks: bool = False,
    ) -> EvidenceSnapshot:
        now = now or datetime.now(timezone.utc)
        snapshot = EvidenceSnapshot(collected_at=now.isoformat())
        snapshot.checks_executed = run_checks or not spec.checks
        self._collect_declared_evidence(spec, snapshot)
        self._collect_walk_forward(spec, snapshot, now)
        self._collect_accepted_evidence(spec, snapshot, now)
        self._collect_runtime(spec, snapshot, now)
        self._collect_database(spec, snapshot, now)
        if run_checks:
            snapshot.check_results = [
                self._run_check(command) for command in spec.checks
            ]
        snapshot.candidate_binding_valid = bool(
            snapshot.accepted_candidate_id
            and snapshot.runtime_candidate_id
            and snapshot.accepted_candidate_id == snapshot.runtime_candidate_id
        )
        return snapshot

    def _collect_accepted_evidence(
        self,
        spec: StrategySpec,
        snapshot: EvidenceSnapshot,
        now: datetime,
    ) -> None:
        path = (
            self.root
            / "data"
            / "strategy-evolution"
            / "strategies"
            / spec.strategy_id
            / "accepted-evidence.json"
        )
        if not path.exists():
            return
        payload = self._read_json(path, snapshot)
        accepted_at = _parse_time(payload.get("accepted_at"))
        if accepted_at is None:
            snapshot.source_errors.append(
                f"accepted evidence missing timestamp: {spec.strategy_id}"
            )
            return
        age_seconds = _validated_age_seconds(
            now, accepted_at, snapshot, f"accepted evidence for {spec.strategy_id}"
        )
        if age_seconds is None:
            return
        artifact_value = str(payload.get("artifact") or "")
        artifact_hash = str(payload.get("artifact_sha256") or "")
        candidate_id = str(payload.get("candidate_id") or "")
        if not artifact_value or not artifact_hash or not candidate_id:
            snapshot.source_errors.append(
                f"accepted evidence missing lineage: {spec.strategy_id}"
            )
            return
        artifact = self._path(artifact_value)
        if not artifact.is_file():
            snapshot.source_errors.append(
                f"accepted artifact missing: {artifact_value}"
            )
            return
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual_hash != artifact_hash:
            snapshot.source_errors.append(
                f"accepted artifact hash mismatch: {spec.strategy_id}"
            )
            return
        age_hours = age_seconds / 3600
        if age_hours > spec.maximum_evidence_age_hours:
            return
        snapshot.accepted_candidate_id = candidate_id
        snapshot.backtest_passed = snapshot.backtest_passed or bool(
            payload.get("backtest_passed")
        )
        snapshot.walk_forward_passed = snapshot.walk_forward_passed or bool(
            payload.get("walk_forward_passed")
        )
        snapshot.costs_included = snapshot.costs_included or bool(
            payload.get("costs_included")
        )
        snapshot.walk_forward_exists = True
        snapshot.walk_forward_age_hours = age_hours
        snapshot.refs.append(str(path.relative_to(self.root)))

    def _collect_declared_evidence(
        self, spec: StrategySpec, snapshot: EvidenceSnapshot
    ) -> None:
        path = self._path(spec.evidence_file)
        payload = self._read_json(path, snapshot)
        row = (
            (payload.get("strategies") or {}).get(spec.strategy_id, {})
            if payload
            else {}
        )
        if not isinstance(row, dict):
            row = {}
        for key in (
            "adapter_tests_passed",
            "stop_path_verified",
            "backtest_passed",
            "walk_forward_passed",
            "costs_included",
            "paper_scorecard_passed",
            "canary_approved",
            "live_release_approved",
            "recovery_verified",
        ):
            setattr(snapshot, key, bool(row.get(key, False)))
        for key in (
            "paper_scorecard_candidate_id",
            "canary_candidate_id",
            "live_release_candidate_id",
        ):
            value = str(row.get(key) or "").strip()
            setattr(snapshot, key, value or None)
        snapshot.paper_hours = max(
            snapshot.paper_hours, float(row.get("paper_hours", 0) or 0)
        )
        snapshot.refs.extend(str(item) for item in row.get("evidence_refs") or [])
        snapshot.refs.append(str(path.relative_to(self.root)))

    def _collect_walk_forward(
        self,
        spec: StrategySpec,
        snapshot: EvidenceSnapshot,
        now: datetime,
    ) -> None:
        path = self._path(spec.walk_forward_file)
        payload = self._read_json(path, snapshot)
        if not payload:
            return
        snapshot.walk_forward_exists = True
        summary = (
            payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        )
        report_passed = bool(payload.get("validation_passed") and summary.get("passed"))
        snapshot.walk_forward_passed = snapshot.walk_forward_passed and report_passed
        generated_at = _parse_time(payload.get("generated_at"))
        if generated_at:
            age_seconds = _validated_age_seconds(
                now,
                generated_at,
                snapshot,
                f"walk-forward report for {spec.strategy_id}",
            )
            if age_seconds is not None:
                snapshot.walk_forward_age_hours = age_seconds / 3600
        snapshot.refs.append(str(path.relative_to(self.root)))

    def _collect_runtime(
        self,
        spec: StrategySpec,
        snapshot: EvidenceSnapshot,
        now: datetime,
    ) -> None:
        if not spec.runtime_file:
            return
        runtime_file = spec.runtime_file
        active = self._active_paper_deployment(spec)
        if active.get("candidate_id") == snapshot.accepted_candidate_id:
            runtime_file = str(active.get("runtime_file") or runtime_file)
        path = self._path(runtime_file)
        payload = self._read_json(path, snapshot)
        if not payload:
            return
        snapshot.runtime_exists = True
        snapshot.runtime_candidate_id = (
            str(payload.get("evolution_candidate_id") or "") or None
        )
        generated_at = _parse_time(payload.get("generated_at"))
        if generated_at:
            snapshot.runtime_age_seconds = _validated_age_seconds(
                now, generated_at, snapshot, f"runtime snapshot for {spec.strategy_id}"
            )
            snapshot.runtime_fresh = snapshot.runtime_age_seconds is not None and (
                snapshot.runtime_age_seconds <= spec.maximum_runtime_age_seconds
            )
        connectors = {
            str(row.get("connector"))
            for section in ("balances", "open_orders", "positions", "market_data")
            for row in (payload.get(section) or [])
            if isinstance(row, dict) and row.get("connector")
        }
        snapshot.paper_only = bool(connectors) and all(
            name.endswith("_paper_trade") for name in connectors
        )
        positions = (
            payload.get("positions")
            if isinstance(payload.get("positions"), list)
            else []
        )
        snapshot.paper_pnl_quote = float(
            sum(
                (
                    _decimal(row.get("pnl"))
                    for row in positions
                    if isinstance(row, dict)
                ),
                Decimal("0"),
            )
        )
        snapshot.refs.append(str(path.relative_to(self.root)))

    def _collect_database(
        self,
        spec: StrategySpec,
        snapshot: EvidenceSnapshot,
        now: datetime,
    ) -> None:
        if not spec.database_file:
            return
        database_file = spec.database_file
        active = self._active_paper_deployment(spec)
        if active.get("candidate_id") == snapshot.accepted_candidate_id:
            database_file = str(active.get("database_file") or database_file)
        path = self._path(database_file)
        if not path.exists():
            snapshot.source_errors.append(
                f"missing database: {path.relative_to(self.root)}"
            )
            return
        try:
            with sqlite3.connect(
                f"file:{path}?mode=ro", uri=True, timeout=5
            ) as connection:
                order_row = connection.execute(
                    'select count(*), min(creation_timestamp) from "Order"'
                ).fetchone()
                fill_row = connection.execute(
                    "select count(*) from TradeFill"
                ).fetchone()
        except sqlite3.Error as exc:
            snapshot.source_errors.append(f"database error: {exc}")
            return
        snapshot.paper_orders = int(order_row[0] or 0)
        snapshot.paper_fills = int(fill_row[0] or 0)
        first_ms = int(order_row[1] or 0)
        if first_ms:
            started_at = datetime.fromtimestamp(first_ms / 1000, timezone.utc)
            snapshot.paper_hours = max(
                snapshot.paper_hours,
                max(0.0, (now - started_at).total_seconds() / 3600),
            )
        snapshot.refs.append(str(path.relative_to(self.root)))

    def _active_paper_deployment(self, spec: StrategySpec) -> dict[str, Any]:
        path = (
            self.root
            / "data/strategy-evolution/strategies"
            / spec.strategy_id
            / "paper/active.json"
        )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _run_check(self, command: tuple[str, ...]) -> dict[str, Any]:
        executable = Path(command[0]).name
        allowed = {"python", "python3", Path(sys.executable).name}
        if executable not in allowed:
            return {
                "command": list(command),
                "ok": False,
                "returncode": -1,
                "error": "check executable is not allowlisted",
            }
        started = time.monotonic()
        env = os.environ.copy()
        env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
        try:
            result = self._execute_check(command, env)
            output = f"{result.stdout}\n{result.stderr}"
            classification = (
                "environment_missing"
                if result.returncode != 0
                and ("ModuleNotFoundError" in output or "No module named" in output)
                else ("passed" if result.returncode == 0 else "test_failed")
            )
            return {
                "command": list(command),
                "ok": result.returncode == 0,
                "classification": classification,
                "returncode": result.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "command": list(command),
                "ok": False,
                "classification": "execution_error",
                "returncode": -1,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "error": str(exc),
            }

    def _execute_check(
        self, command: tuple[str, ...], env: dict[str, str]
    ) -> subprocess.CompletedProcess:
        if self.check_runtime != "docker":
            return subprocess.run(
                list(command),
                cwd=str(self.root),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.check_timeout,
                check=False,
            )
        docker = shutil.which("docker")
        if not docker:
            bundled = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
            docker = str(bundled) if bundled.is_file() else None
        if not docker:
            raise OSError("Docker runtime is not available for configured checks")
        python_command = ["python", *command[1:]]
        return subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--label",
                "hummingbot.strategy-evolution-check=true",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                "-e",
                "PYTHONPYCACHEPREFIX=/tmp/pycache",
                "-e",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
                "-e",
                f"PYTHONPATH={DOCKER_WORKDIR}",
                *docker_source_mounts(self.root),
                "-w",
                DOCKER_WORKDIR,
                self.docker_image,
                "conda",
                "run",
                "--no-capture-output",
                "-n",
                "hummingbot",
                *python_command,
            ],
            cwd=str(self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.check_timeout,
            check=False,
        )

    def _path(self, value: str) -> Path:
        path = (self.root / value).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError(f"evidence path escapes repository: {value}")
        return path

    @staticmethod
    def _read_json(path: Path, snapshot: EvidenceSnapshot) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            snapshot.source_errors.append(f"missing file: {path.name}")
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            snapshot.source_errors.append(f"invalid file {path.name}: {exc}")
            return {}
        return payload if isinstance(payload, dict) else {}


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validated_age_seconds(
    now: datetime,
    generated_at: datetime,
    snapshot: EvidenceSnapshot,
    label: str,
    *,
    future_tolerance_seconds: int = 300,
) -> float | None:
    age = (now - generated_at).total_seconds()
    if age < -future_tolerance_seconds:
        snapshot.source_errors.append(f"future timestamp: {label}")
        return None
    return max(0.0, age)


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
