from __future__ import annotations

import json
import os
import hashlib
import urllib.error
import urllib.request
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hummingbot.strategy_v2.evolution.models import (
    EvolutionPolicy,
    EvolutionStage,
    StrategyRunStatus,
    StrategyState,
)


class EvolutionStore:
    def __init__(self, root: Path, policy: EvolutionPolicy | None = None):
        self.root = root
        self.policy = policy or EvolutionPolicy()

    def strategy_dir(self, strategy_id: str) -> Path:
        return self.root / "data" / "strategy-evolution" / "strategies" / strategy_id

    def load_state(self, strategy_id: str) -> StrategyState:
        path = self.strategy_dir(strategy_id) / "state.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return StrategyState(strategy_id=strategy_id)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"corrupt evolution state for {strategy_id}: {exc}"
            ) from exc
        try:
            raw_stage = str(payload.get("stage", EvolutionStage.COLLECTED.value))
            legacy_paused = raw_stage == "paused"
            if raw_stage == "paper_enabled":
                raw_stage = EvolutionStage.PAPER_PASSED.value
            if legacy_paused:
                raw_stage = EvolutionStage.COLLECTED.value
            stage = EvolutionStage(raw_stage)
            highest = EvolutionStage(payload.get("highest_ever_stage", stage.value))
            return StrategyState(
                version=max(3, int(payload.get("version", 3))),
                strategy_id=strategy_id,
                iteration=int(payload.get("iteration", 0)),
                stage=stage,
                highest_ever_stage=highest,
                run_status=StrategyRunStatus(
                    StrategyRunStatus.PAUSED.value
                    if legacy_paused
                    else payload.get("run_status", StrategyRunStatus.IDLE.value)
                ),
                diagnostic_signature=str(
                    payload.get("diagnostic_signature", "healthy")
                ),
                consecutive_same_problem=int(
                    payload.get("consecutive_same_problem", 0)
                ),
                circuit_open=bool(payload.get("circuit_open", False)),
                recovery_healthy_cycles=int(payload.get("recovery_healthy_cycles", 0)),
                champion_candidate_id=payload.get("champion_candidate_id"),
                challenger_candidate_id=payload.get("challenger_candidate_id"),
                active_paper_candidate_id=payload.get("active_paper_candidate_id"),
                previous_good_candidate_id=payload.get("previous_good_candidate_id"),
                in_flight_experiment_id=payload.get("in_flight_experiment_id"),
                in_flight_started_at=payload.get("in_flight_started_at"),
                last_experiment_id=payload.get("last_experiment_id"),
                last_outcome_verdict=payload.get("last_outcome_verdict"),
                experiment_failure_count=int(
                    payload.get("experiment_failure_count", 0)
                ),
                next_experiment_after=payload.get("next_experiment_after"),
                updated_at=str(payload.get("updated_at", "")),
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"invalid evolution state for {strategy_id}: {exc}"
            ) from exc

    def save_cycle(self, state: StrategyState, cycle: dict[str, Any]) -> None:
        directory = self.strategy_dir(state.strategy_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._write_state(state)
        self._write_json(directory / "latest.json", cycle)
        self._append_jsonl(directory / "events.jsonl", cycle)

    def start_experiment(self, strategy_id: str, experiment_id: str) -> StrategyState:
        state = self.load_state(strategy_id)
        if state.in_flight_experiment_id is not None:
            raise RuntimeError(
                f"strategy {strategy_id} already has in-flight experiment "
                f"{state.in_flight_experiment_id}"
            )
        if state.last_experiment_id == experiment_id:
            raise RuntimeError(f"experiment {experiment_id} has already completed")
        started_at = datetime.now(timezone.utc).isoformat()
        transaction = {
            "version": 1,
            "event": "experiment_started",
            "status": "running",
            "strategy_id": strategy_id,
            "experiment_id": experiment_id,
            "started_at": started_at,
        }
        self._write_json(
            self._experiment_transaction_path(strategy_id, experiment_id), transaction
        )
        updated = replace(
            state,
            run_status=StrategyRunStatus.EXPERIMENTING,
            in_flight_experiment_id=experiment_id,
            in_flight_started_at=started_at,
        )
        self._write_state(updated)
        self._append_jsonl(
            self.strategy_dir(strategy_id) / "experiment-events.jsonl",
            {
                "event": "experiment_started",
                "strategy_id": strategy_id,
                "experiment_id": experiment_id,
                "started_at": started_at,
            },
        )
        return updated

    def finish_experiment(self, outcome: dict[str, Any]) -> StrategyState:
        strategy_id = str(outcome["strategy_id"])
        experiment_id = str(outcome["experiment_id"])
        state = self.load_state(strategy_id)
        transaction_path = self._experiment_transaction_path(strategy_id, experiment_id)
        transaction = self._read_json(transaction_path)
        if not transaction:
            raise RuntimeError(f"experiment {experiment_id} has no start transaction")
        if (
            transaction.get("strategy_id") != strategy_id
            or transaction.get("experiment_id") != experiment_id
        ):
            raise RuntimeError(
                f"experiment transaction identity mismatch: {experiment_id}"
            )
        outcome_hash = self._payload_hash(outcome)
        if transaction.get("status") == "completed":
            if transaction.get("outcome_hash") != outcome_hash:
                raise RuntimeError(
                    f"experiment {experiment_id} outcome replay mismatch"
                )
            if (
                state.last_experiment_id == experiment_id
                and state.in_flight_experiment_id is None
            ):
                return state
        if state.in_flight_experiment_id != experiment_id:
            raise RuntimeError(
                f"experiment outcome does not match in-flight state: {experiment_id}"
            )
        transaction = {
            **transaction,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "outcome_hash": outcome_hash,
            "outcome": outcome,
        }
        self._write_json(transaction_path, transaction)
        candidate_id = outcome.get("candidate_id")
        accepted = outcome.get("verdict") == "accept_candidate_evidence"
        infrastructure_failure = outcome.get("verdict") in {
            "external_rate_limited",
            "external_data_unavailable",
            "environment_missing",
            "command_failed",
            "executor_error",
            "executor_interrupted",
        }
        research_rejection = outcome.get("verdict") in {
            "reject_candidate_evidence",
            "reject_challenger",
        }
        failure_count = (
            state.experiment_failure_count + 1
            if infrastructure_failure or research_rejection
            else 0
        )
        retry_after = int(outcome.get("retry_after_seconds") or 0)
        if research_rejection and retry_after <= 0:
            retry_after = min(
                self.policy.research_rejection_cooldown_seconds
                * (2 ** min(max(failure_count - 1, 0), 8)),
                self.policy.maximum_research_rejection_cooldown_seconds,
            )
        elif infrastructure_failure and retry_after <= 0:
            retry_after = 300
        next_experiment_after = (
            (datetime.now(timezone.utc) + timedelta(seconds=retry_after)).isoformat()
            if retry_after > 0
            else None
        )
        updated = replace(
            state,
            run_status=StrategyRunStatus.IDLE,
            in_flight_experiment_id=None,
            in_flight_started_at=None,
            last_experiment_id=experiment_id,
            last_outcome_verdict=str(outcome.get("verdict") or "unknown"),
            experiment_failure_count=failure_count,
            next_experiment_after=next_experiment_after,
            previous_good_candidate_id=(
                state.champion_candidate_id
                if accepted and candidate_id
                else state.previous_good_candidate_id
            ),
            champion_candidate_id=(
                str(candidate_id)
                if accepted and candidate_id
                else state.champion_candidate_id
            ),
            challenger_candidate_id=(
                None
                if accepted
                else (
                    str(candidate_id) if candidate_id else state.challenger_candidate_id
                )
            ),
        )
        self._write_state(updated)
        self._append_jsonl(
            self.strategy_dir(strategy_id) / "experiment-events.jsonl",
            {"event": "experiment_finished", **outcome},
        )
        return updated

    def recover_in_flight(self, strategy_id: str) -> dict[str, Any] | None:
        state = self.load_state(strategy_id)
        experiment_id = state.in_flight_experiment_id
        if not experiment_id:
            return None
        transaction = self._read_json(
            self._experiment_transaction_path(strategy_id, experiment_id)
        )
        outcome = transaction.get("outcome") if transaction else None
        if not isinstance(outcome, dict):
            outcome_path = (
                self.root
                / "data"
                / "strategy-evolution"
                / "experiments"
                / experiment_id
                / "outcome.json"
            )
            outcome = self._read_json(outcome_path)
        if not outcome:
            outcome = {
                "experiment_id": experiment_id,
                "strategy_id": strategy_id,
                "action": "recovered_after_restart",
                "status": "failed",
                "verdict": "executor_interrupted",
                "artifact_json": None,
                "returncode": None,
                "elapsed_seconds": 0.0,
                "summary": {},
                "error": "supervisor restarted before the experiment produced an outcome",
                "retry_after_seconds": 60,
            }
        if (
            str(outcome.get("strategy_id")) != strategy_id
            or str(outcome.get("experiment_id")) != experiment_id
        ):
            raise RuntimeError(f"recovery outcome identity mismatch: {experiment_id}")
        self.finish_experiment(outcome)
        return {
            "strategy_id": strategy_id,
            "experiment_id": experiment_id,
            "verdict": outcome.get("verdict"),
            "recovered": True,
        }

    def save_strategy_error(self, strategy_id: str, cycle: dict[str, Any]) -> None:
        directory = self.strategy_dir(strategy_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "latest.json", cycle)
        self._append_jsonl(directory / "events.jsonl", cycle)

    def record_alert(
        self,
        *,
        severity: str,
        source: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        fingerprint = hashlib.sha256(
            f"{severity}:{source}:{message}".encode()
        ).hexdigest()[:16]
        alert = {
            "version": 1,
            "alert_id": f"alert-{fingerprint}",
            "severity": severity,
            "source": source,
            "message": message,
            "context": context or {},
            "observed_at": now,
        }
        alert["delivery"] = self._deliver_alert(alert)
        directory = self.root / "data" / "strategy-evolution" / "alerts"
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "latest.json", alert)
        self._append_jsonl(directory / "events.jsonl", alert)
        return alert

    @staticmethod
    def _deliver_alert(alert: dict[str, Any]) -> dict[str, Any]:
        url = os.environ.get("STRATEGY_EVOLUTION_ALERT_WEBHOOK_URL", "").strip()
        if not url:
            return {"status": "not_configured"}
        body = json.dumps(alert, ensure_ascii=False, default=str).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return {"status": "delivered", "http_status": response.status}
        except (OSError, urllib.error.URLError) as exc:
            return {"status": "failed", "error_type": type(exc).__name__}

    def save_supervisor_snapshot(self, payload: dict[str, Any]) -> None:
        directory = self.root / "data" / "strategy-evolution"
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "latest.json", payload)
        self._append_jsonl(directory / "supervisor-events.jsonl", payload)

    def save_heartbeat(self, payload: dict[str, Any]) -> None:
        directory = self.root / "data" / "strategy-evolution"
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "heartbeat.json", payload)

    def read_heartbeat(self) -> dict[str, Any]:
        return self._read_json(
            self.root / "data" / "strategy-evolution" / "heartbeat.json"
        )

    def _write_state(self, state: StrategyState) -> None:
        directory = self.strategy_dir(state.strategy_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(
            directory / "state.json",
            {
                "version": state.version,
                "strategy_id": state.strategy_id,
                "iteration": state.iteration,
                "stage": state.stage.value,
                "highest_ever_stage": state.highest_ever_stage.value,
                "run_status": state.run_status.value,
                "diagnostic_signature": state.diagnostic_signature,
                "consecutive_same_problem": state.consecutive_same_problem,
                "circuit_open": state.circuit_open,
                "recovery_healthy_cycles": state.recovery_healthy_cycles,
                "champion_candidate_id": state.champion_candidate_id,
                "challenger_candidate_id": state.challenger_candidate_id,
                "active_paper_candidate_id": state.active_paper_candidate_id,
                "previous_good_candidate_id": state.previous_good_candidate_id,
                "in_flight_experiment_id": state.in_flight_experiment_id,
                "in_flight_started_at": state.in_flight_started_at,
                "last_experiment_id": state.last_experiment_id,
                "last_outcome_verdict": state.last_outcome_verdict,
                "experiment_failure_count": state.experiment_failure_count,
                "next_experiment_after": state.next_experiment_after,
                "updated_at": state.updated_at,
            },
        )

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        maximum_bytes = int(
            os.environ.get("STRATEGY_EVOLUTION_JSONL_MAX_BYTES", 25 * 1024 * 1024)
        )
        if path.exists() and path.stat().st_size >= maximum_bytes:
            generations = 5
            oldest = path.with_name(f"{path.name}.{generations}")
            oldest.unlink(missing_ok=True)
            for index in range(generations - 1, 0, -1):
                source = path.with_name(f"{path.name}.{index}")
                if source.exists():
                    source.replace(path.with_name(f"{path.name}.{index + 1}"))
            path.replace(path.with_name(f"{path.name}.1"))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":"), default=str
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())

    def _experiment_transaction_path(
        self, strategy_id: str, experiment_id: str
    ) -> Path:
        return self.strategy_dir(strategy_id) / "experiments" / f"{experiment_id}.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
