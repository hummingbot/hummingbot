from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from hummingbot.strategy_v2.evolution.config import EvolutionConfig
from hummingbot.strategy_v2.evolution.models import EvidenceSnapshot, StrategySpec


class PaperCandidateStager:
    """Renders an immutable paper-only PMM config bundle without starting it."""

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.root = config.root.resolve()

    def stage(self, spec: StrategySpec, candidate: dict[str, Any]) -> dict[str, Any]:
        if spec.strategy_id != "pmm_mister":
            return {
                "status": "paper_adapter_missing",
                "strategy_id": spec.strategy_id,
                "candidate_id": candidate["candidate_id"],
            }
        parameters = candidate.get("parameters") or {}
        required = {"spread", "take_profit", "refresh_seconds"}
        if set(parameters) != required:
            raise ValueError("PMM paper candidate parameter set is not allowlisted")
        controller_base = self.root / "conf/controllers/conf_pmm_mister_paper.yml"
        script_base = self.root / "conf/scripts/conf_pmm_mister_paper.yml"
        controller = _read_yaml(controller_base)
        script = _read_yaml(script_base)
        if not str(controller.get("connector_name", "")).endswith("_paper_trade"):
            raise ValueError("PMM paper base config is not paper-only")
        if int(controller.get("leverage", 1)) != 1:
            raise ValueError("automatic paper staging requires leverage=1")

        spread = float(parameters["spread"])
        take_profit = float(parameters["take_profit"])
        refresh = int(parameters["refresh_seconds"])
        controller.update(
            {
                "id": f"evo_{candidate['candidate_id']}",
                "buy_spreads": spread,
                "sell_spreads": spread,
                "price_distance_tolerance": spread,
                "refresh_tolerance": spread,
                "take_profit": take_profit,
                "executor_refresh_time": refresh,
                "buy_cooldown_time": refresh,
                "sell_cooldown_time": refresh,
                "buy_position_effectivization_time": refresh * 2,
                "sell_position_effectivization_time": refresh * 2,
            }
        )
        controller_text = yaml.safe_dump(
            controller, sort_keys=False, allow_unicode=True
        )
        script.update({"evolution_candidate_id": candidate["candidate_id"]})
        bundle_seed = hashlib.sha256(
            (
                controller_text
                + "\n"
                + yaml.safe_dump(script, sort_keys=False, allow_unicode=True)
            ).encode()
        ).hexdigest()
        deployment_id = f"paper-{candidate['candidate_id']}-{bundle_seed[:8]}"
        runtime_name = f"{deployment_id}_runtime.json"
        controller_name = f"conf_evo_{deployment_id}.yml"
        script_name = f"conf_evo_{deployment_id}.yml"
        controller_path = self.root / "conf/controllers" / controller_name
        script_path = self.root / "conf/scripts" / script_name
        script.update(
            {
                "controllers_config": [controller_name],
                "evolution_deployment_id": deployment_id,
                "runtime_snapshot_file": runtime_name,
            }
        )
        preliminary_script = yaml.safe_dump(script, sort_keys=False, allow_unicode=True)
        config_hash = hashlib.sha256(
            (controller_text + "\n" + preliminary_script).encode()
        ).hexdigest()
        script["evolution_config_hash"] = config_hash
        script_text = yaml.safe_dump(script, sort_keys=False, allow_unicode=True)
        strategy_dir = (
            self.root / "data/strategy-evolution/strategies" / spec.strategy_id
        )
        active = _read_json(strategy_dir / "paper/active.json")
        deployment_path = strategy_dir / "paper/deployments" / f"{deployment_id}.json"
        existing = _read_json(deployment_path)
        if (
            active.get("candidate_id") == candidate["candidate_id"]
            and active.get("config_hash") == config_hash
        ):
            return active
        if existing:
            if existing.get("config_hash") != config_hash:
                raise ValueError("paper deployment id collided with a different config")
            staged = _read_json(strategy_dir / "paper/staged.json")
            return staged if staged.get("deployment_id") == deployment_id else existing

        _atomic_text(controller_path, controller_text)
        _atomic_text(script_path, script_text)
        runtime = _read_json(self.root / str(spec.runtime_file or ""))
        flat = _runtime_is_explicitly_flat(runtime)
        status = "ready_to_start" if flat else "waiting_for_valid_flat_runtime"
        deployment = {
            "version": 1,
            "deployment_id": deployment_id,
            "strategy_id": spec.strategy_id,
            "candidate_id": candidate["candidate_id"],
            "previous_deployment_id": active.get("deployment_id"),
            "controller_config": str(controller_path.relative_to(self.root)),
            "script_config": str(script_path.relative_to(self.root)),
            "runtime_file": f"data/{runtime_name}",
            "database_file": f"data/{Path(script_name).stem}.sqlite",
            "config_hash": config_hash,
            "status": status,
            "paper_only": True,
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "start_command": [
                "env",
                f"SCRIPT_CONFIG={script_name}",
                "scripts/run_pmm_mister_paper.sh",
            ],
        }
        _atomic_json(deployment_path, deployment)
        _atomic_json(strategy_dir / "paper/staged.json", deployment)
        _atomic_json(strategy_dir / "paper/release-manifest.json", deployment)
        if active:
            _atomic_json(strategy_dir / "paper/rollback-target.json", active)
        return deployment

    def reconcile_and_maybe_activate(
        self, spec: StrategySpec, evidence: EvidenceSnapshot | None = None
    ) -> dict[str, Any] | None:
        if spec.strategy_id != "pmm_mister":
            return None
        strategy_dir = (
            self.root / "data/strategy-evolution/strategies" / spec.strategy_id
        )
        active = _read_json(strategy_dir / "paper/active.json")
        if active.get("status") in {"rolled_back", "rollback_blocked"}:
            return active
        if active and str(active.get("status") or "").startswith("rollback"):
            recovered = self._recover_observation_rollback(
                spec, strategy_dir, active, evidence
            )
            if recovered is not None:
                return recovered
            return self._rollback_active(
                spec,
                strategy_dir,
                active,
                list(active.get("rollback_reasons") or ["rollback_requested"]),
            )
        if active and evidence:
            rollback_reasons = []
            if evidence.runtime_exists and not evidence.paper_only:
                rollback_reasons.append("non_paper_connector_detected")
            if evidence.runtime_exists and not evidence.runtime_fresh:
                rollback_reasons.append("runtime_stale")
            if (
                evidence.runtime_exists
                and evidence.paper_pnl_quote <= spec.maximum_paper_loss_quote
            ):
                rollback_reasons.append("paper_loss_limit_crossed")
            if (
                evidence.runtime_candidate_id
                and evidence.runtime_candidate_id != active.get("candidate_id")
            ):
                rollback_reasons.append("runtime_candidate_mismatch")
            if rollback_reasons:
                return self._rollback_active(
                    spec, strategy_dir, active, rollback_reasons
                )
        staged_path = strategy_dir / "paper/staged.json"
        deployment = _read_json(staged_path)
        if not deployment:
            return active or None
        if deployment.get("status") in {
            "rolled_back",
            "rollback_blocked",
            "startup_failed",
        }:
            return deployment
        release_manifest = strategy_dir / "paper/release-manifest.json"
        if not release_manifest.exists():
            _atomic_json(release_manifest, deployment)
        candidate_runtime = _read_json(
            self.root / str(deployment.get("runtime_file") or "")
        )
        runtime_candidate = candidate_runtime.get("evolution_candidate_id")
        runtime_hash = candidate_runtime.get("evolution_config_hash")
        if runtime_candidate == deployment["candidate_id"]:
            if runtime_hash != deployment["config_hash"]:
                return self._rollback_active(
                    spec,
                    strategy_dir,
                    deployment,
                    ["runtime_config_hash_mismatch"],
                )
            deployment["status"] = "active_verified"
            deployment["verified_at"] = datetime.now(timezone.utc).isoformat()
            _atomic_json(strategy_dir / "paper/active.json", deployment)
            _persist_staged(staged_path, release_manifest, deployment)
            return deployment
        if deployment.get("status") in {
            "starting",
            "startup_pending_runtime_verification",
        }:
            started_at = deployment.get("start_attempted_at")
            try:
                started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - started).total_seconds()
            except (TypeError, ValueError):
                age = self.config.policy.paper_startup_timeout_seconds + 1
            if age <= self.config.policy.paper_startup_timeout_seconds:
                deployment["status"] = "startup_pending_runtime_verification"
                _persist_staged(staged_path, release_manifest, deployment)
                return deployment
            return self._rollback_active(
                spec,
                strategy_dir,
                deployment,
                ["paper_startup_verification_timeout"],
            )
        # Before the candidate starts, its dedicated runtime snapshot does not
        # exist yet. The launch gate must therefore use the currently running
        # strategy snapshot. Once launched, verification above only trusts the
        # candidate-specific runtime file declared in the release manifest.
        preflight_runtime = _read_json(self.root / str(spec.runtime_file or ""))
        if not _runtime_is_explicitly_flat(preflight_runtime):
            deployment["status"] = "waiting_for_valid_flat_runtime"
            _persist_staged(staged_path, release_manifest, deployment)
            return deployment
        if not self.config.policy.auto_start_paper_candidates:
            deployment["status"] = "ready_for_manual_start"
            _persist_staged(staged_path, release_manifest, deployment)
            return deployment
        if (
            evidence is None
            or evidence.source_errors
            or not evidence.runtime_exists
            or not evidence.runtime_fresh
            or not evidence.paper_only
        ):
            deployment["status"] = "waiting_for_safe_fresh_runtime"
            deployment["runtime_errors"] = (
                list(evidence.source_errors)
                if evidence is not None
                else ["evidence_missing"]
            )
            _persist_staged(staged_path, release_manifest, deployment)
            return deployment
        if not os.environ.get("CONFIG_PASSWORD"):
            deployment["status"] = "waiting_for_credentials"
            _persist_staged(staged_path, release_manifest, deployment)
            return deployment
        deployment["status"] = "starting"
        deployment["start_attempted_at"] = datetime.now(timezone.utc).isoformat()
        _persist_staged(staged_path, release_manifest, deployment)
        env = os.environ.copy()
        env["SCRIPT_CONFIG"] = Path(deployment["script_config"]).name
        result = subprocess.run(
            [str(self.root / "scripts/run_pmm_mister_paper.sh")],
            cwd=str(self.root),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
        if result.returncode == 0:
            deployment["status"] = "startup_pending_runtime_verification"
            deployment["start_returncode"] = 0
            deployment["startup_deadline_at"] = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp()
                + self.config.policy.paper_startup_timeout_seconds,
                tz=timezone.utc,
            ).isoformat()
            _persist_staged(staged_path, release_manifest, deployment)
            return deployment
        deployment["status"] = "startup_failed"
        deployment["start_returncode"] = result.returncode
        deployment["error"] = (result.stderr or result.stdout)[-1000:]
        rollback = _read_json(strategy_dir / "paper/rollback-target.json")
        rollback_script = Path(
            rollback.get("script_config", "conf/scripts/conf_pmm_mister_paper.yml")
        ).name
        env["SCRIPT_CONFIG"] = rollback_script
        rollback_result = subprocess.run(
            [str(self.root / "scripts/run_pmm_mister_paper.sh")],
            cwd=str(self.root),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
        deployment["rollback_status"] = (
            "rolled_back" if rollback_result.returncode == 0 else "rollback_blocked"
        )
        deployment["rollback_returncode"] = rollback_result.returncode
        _persist_staged(staged_path, release_manifest, deployment)
        _atomic_json(
            strategy_dir
            / "paper/rollback-events"
            / f"{deployment['deployment_id']}.json",
            deployment,
        )
        return deployment

    def _recover_observation_rollback(
        self,
        spec: StrategySpec,
        strategy_dir: Path,
        deployment: dict[str, Any],
        evidence: EvidenceSnapshot | None,
    ) -> dict[str, Any] | None:
        """Cancel only a transient stale-snapshot rollback after full recovery proof."""
        reasons = set(deployment.get("rollback_reasons") or [])
        if not reasons or not reasons.issubset({"runtime_stale"}):
            return None
        if (
            evidence is None
            or evidence.source_errors
            or not evidence.runtime_exists
            or not evidence.runtime_fresh
            or not evidence.paper_only
            or not evidence.candidate_binding_valid
            or evidence.accepted_candidate_id != deployment.get("candidate_id")
            or evidence.runtime_candidate_id != deployment.get("candidate_id")
            or evidence.paper_pnl_quote <= spec.maximum_paper_loss_quote
        ):
            return None
        runtime = _read_json(
            self.root / str(deployment.get("runtime_file") or spec.runtime_file or "")
        )
        if runtime.get("evolution_config_hash") != deployment.get("config_hash"):
            return None
        recovered = dict(deployment)
        recovered["status"] = "active_verified"
        recovered["rollback_recovered_at"] = datetime.now(timezone.utc).isoformat()
        recovered["rollback_recovery"] = {
            "reasons": sorted(reasons),
            "evidence_collected_at": evidence.collected_at,
            "runtime_candidate_id": evidence.runtime_candidate_id,
        }
        recovered.pop("rollback_reasons", None)
        recovered.pop("rollback_requested_at", None)
        _atomic_json(strategy_dir / "paper/active.json", recovered)
        _persist_staged(
            strategy_dir / "paper/staged.json",
            strategy_dir / "paper/release-manifest.json",
            recovered,
        )
        _atomic_json(
            strategy_dir
            / "paper/rollback-events"
            / f"{deployment['deployment_id']}-recovered.json",
            recovered,
        )
        return recovered

    def _rollback_active(
        self,
        spec: StrategySpec,
        strategy_dir: Path,
        deployment: dict[str, Any],
        reasons: list[str],
    ) -> dict[str, Any]:
        deployment = dict(deployment)
        deployment["status"] = "rollback_pending"
        deployment["rollback_reasons"] = reasons
        deployment["rollback_requested_at"] = datetime.now(timezone.utc).isoformat()
        runtime_path = self.root / str(
            deployment.get("runtime_file") or spec.runtime_file or ""
        )
        runtime = _read_json(runtime_path)
        if not _runtime_has_explicit_exposure_state(runtime):
            deployment["status"] = "rollback_blocked_runtime_unavailable"
            _persist_rollback_state(strategy_dir, deployment)
            return deployment
        if runtime.get("positions") or runtime.get("open_orders"):
            deployment["status"] = "rollback_blocked_open_exposure"
            _persist_rollback_state(strategy_dir, deployment)
            return deployment
        if not os.environ.get("CONFIG_PASSWORD"):
            deployment["status"] = "rollback_waiting_for_credentials"
            _persist_rollback_state(strategy_dir, deployment)
            return deployment
        rollback = _read_json(strategy_dir / "paper/rollback-target.json")
        script_config = Path(
            rollback.get("script_config", "conf/scripts/conf_pmm_mister_paper.yml")
        ).name
        env = os.environ.copy()
        env["SCRIPT_CONFIG"] = script_config
        result = subprocess.run(
            [str(self.root / "scripts/run_pmm_mister_paper.sh")],
            cwd=str(self.root),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
        deployment["status"] = (
            "rolled_back" if result.returncode == 0 else "rollback_blocked"
        )
        deployment["rollback_returncode"] = result.returncode
        deployment["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        _persist_rollback_state(strategy_dir, deployment)
        _atomic_json(
            strategy_dir
            / "paper/rollback-events"
            / f"{deployment['deployment_id']}.json",
            deployment,
        )
        return deployment

    def promote_paper_candidate(
        self, spec: StrategySpec, candidate_id: str
    ) -> dict[str, Any]:
        strategy_dir = (
            self.root / "data/strategy-evolution/strategies" / spec.strategy_id
        )
        active = _read_json(strategy_dir / "paper/active.json")
        if active.get("candidate_id") != candidate_id:
            raise ValueError(
                "paper promotion candidate does not match active deployment"
            )
        previous = _read_json(strategy_dir / "paper/champion.json")
        if previous.get("candidate_id") == candidate_id:
            return previous
        if previous:
            _atomic_json(strategy_dir / "paper/previous-champion.json", previous)
        champion = dict(active)
        champion["status"] = "paper_champion"
        champion["promoted_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(strategy_dir / "paper/champion.json", champion)
        _atomic_json(strategy_dir / "paper/release-manifest.json", champion)
        return champion


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid YAML object: {path}")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_is_explicitly_flat(payload: dict[str, Any]) -> bool:
    positions = payload.get("positions")
    open_orders = payload.get("open_orders")
    return (
        isinstance(positions, list)
        and isinstance(open_orders, list)
        and not positions
        and not open_orders
    )


def _runtime_has_explicit_exposure_state(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("positions"), list) and isinstance(
        payload.get("open_orders"), list
    )


def _hash_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
    )


def _persist_staged(
    staged_path: Path, release_manifest: Path, deployment: dict[str, Any]
) -> None:
    _atomic_json(staged_path, deployment)
    _atomic_json(release_manifest, deployment)


def _persist_rollback_state(strategy_dir: Path, deployment: dict[str, Any]) -> None:
    _atomic_json(strategy_dir / "paper/active.json", deployment)
    _atomic_json(strategy_dir / "paper/release-manifest.json", deployment)
    staged_path = strategy_dir / "paper/staged.json"
    staged = _read_json(staged_path)
    if staged.get("deployment_id") == deployment.get("deployment_id"):
        _atomic_json(staged_path, deployment)
