from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
from pydantic import Field

from hummingbot.strategy_v2.routing.config import RoutingConfig
from hummingbot.strategy_v2.routing.data_types import (
    Environment,
    RoutePlan,
    StrictModel,
)
from hummingbot.strategy_v2.routing.release import ReleaseManifest, StrategyRelease


class WorkerAction(StrictModel):
    account_id: str
    worker_id: str
    action: Literal["continue", "start", "drain", "stop", "blocked"]
    strategy_id: str | None = None
    candidate_id: str | None = None
    config_hash: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class PaperWorkerManager:
    """Paper-only worker lifecycle adapter. No shell commands and no live connectors."""

    def __init__(
        self,
        root: Path,
        config: RoutingConfig,
        state_path: Path,
        *,
        container_probe: Callable[[str], bool] | None = None,
    ):
        self.root = root.resolve()
        self.config = config
        self.state_path = state_path
        self.container_probe = container_probe or self._container_running

    def plan_actions(
        self,
        plan: RoutePlan,
        manifest: ReleaseManifest,
    ) -> list[WorkerAction]:
        state = self._state().get("workers", {})
        releases = {row.strategy_id: row for row in manifest.releases}
        desired = {row.account_id: row for row in plan.allocations}
        actions = []
        for account in self.config.accounts:
            if not account.trading_enabled or not account.worker_id:
                continue
            current = state.get(account.id) or {}
            target = desired.get(account.id)
            if target is None:
                if current.get("status") in {"running", "starting", "draining"}:
                    actions.append(
                        WorkerAction(
                            account_id=account.id,
                            worker_id=account.worker_id,
                            action="stop",
                            strategy_id=current.get("strategy_id"),
                            candidate_id=current.get("candidate_id"),
                        )
                    )
                continue
            release = releases.get(target.strategy_id)
            blockers = self._release_blockers(target, release)
            if blockers:
                actions.append(
                    WorkerAction(
                        account_id=account.id,
                        worker_id=account.worker_id,
                        action="blocked",
                        strategy_id=target.strategy_id,
                        candidate_id=target.candidate_id,
                        config_hash=target.config_hash,
                        reason_codes=blockers,
                    )
                )
                continue
            if not current and self.container_probe(account.worker_id):
                actions.append(
                    WorkerAction(
                        account_id=account.id,
                        worker_id=account.worker_id,
                        action="blocked",
                        strategy_id=target.strategy_id,
                        candidate_id=target.candidate_id,
                        config_hash=target.config_hash,
                        reason_codes=["unmanaged_running_worker"],
                    )
                )
                continue
            if current.get("candidate_id") == target.candidate_id:
                if current.get("status") == "running":
                    action = "continue"
                elif current.get("status") == "stopped":
                    action = "start"
                else:
                    actions.append(
                        WorkerAction(
                            account_id=account.id,
                            worker_id=account.worker_id,
                            action="blocked",
                            strategy_id=target.strategy_id,
                            candidate_id=target.candidate_id,
                            config_hash=target.config_hash,
                            reason_codes=["worker_runtime_verification_pending"],
                        )
                    )
                    continue
            elif current.get("status") in {"running", "starting"}:
                action = "drain"
            else:
                action = "start"
            actions.append(
                WorkerAction(
                    account_id=account.id,
                    worker_id=account.worker_id,
                    action=action,
                    strategy_id=target.strategy_id,
                    candidate_id=target.candidate_id,
                    config_hash=target.config_hash,
                )
            )
        return actions

    def apply(
        self,
        actions: list[WorkerAction],
        manifest: ReleaseManifest,
    ) -> list[dict[str, Any]]:
        if self.config.environment != Environment.PAPER:
            raise ValueError("worker manager only applies paper routes")
        if any(row.action == "drain" for row in actions) and not os.environ.get(
            "CONFIG_PASSWORD"
        ):
            raise ValueError(
                "CONFIG_PASSWORD is required before draining a worker for replacement"
            )
        releases = {row.strategy_id: row for row in manifest.releases}
        for action in actions:
            if action.action != "drain":
                continue
            release = releases.get(action.strategy_id or "")
            if release is None:
                raise ValueError(
                    f"missing replacement release before drain: {action.strategy_id}"
                )
            self._validate_start(release)
        state = self._state()
        workers = state.setdefault("workers", {})
        results = []
        for action in actions:
            if action.action in {"continue", "blocked"}:
                results.append(action.model_dump(mode="json"))
                continue
            if action.action in {"stop", "drain"}:
                result = self._stop(action)
                workers[action.account_id] = {
                    **action.model_dump(mode="json"),
                    "status": "stopped" if result.returncode == 0 else "stop_failed",
                    "returncode": result.returncode,
                }
                results.append(workers[action.account_id])
                continue
            release = releases.get(action.strategy_id or "")
            if release is None:
                raise ValueError(
                    f"missing release for worker start: {action.strategy_id}"
                )
            result = self._start(action, release)
            workers[action.account_id] = {
                **action.model_dump(mode="json"),
                "status": "starting" if result.returncode == 0 else "start_failed",
                "returncode": result.returncode,
                "output": (result.stderr or result.stdout)[-1000:],
            }
            results.append(workers[action.account_id])
        self._save_state(state)
        return results

    def adopt_legacy_paper_worker(
        self,
        account_id: str,
        runtime_path: Path,
        *,
        approved_by: str,
    ) -> dict[str, Any]:
        if self.config.environment != Environment.PAPER:
            raise ValueError("only paper workers can be adopted")
        account = self.config.accounts_by_id.get(account_id)
        if account is None or not account.trading_enabled or not account.worker_id:
            raise ValueError("legacy adoption requires a configured trading account")
        if not approved_by.strip():
            raise ValueError("legacy adoption requires an operator identity")
        if not self.container_probe(account.worker_id):
            raise ValueError("legacy paper worker container is not running")
        payload = _read_json(runtime_path)
        paper_flags = [
            row.get("paper")
            for key in ("balances", "open_orders", "positions")
            for row in payload.get(key, [])
            if isinstance(row, dict)
        ]
        if not paper_flags or not all(flag is True for flag in paper_flags):
            raise ValueError("legacy runtime is not verifiably paper-only")
        state = self._state()
        worker = {
            "account_id": account.id,
            "worker_id": account.worker_id,
            "status": "running",
            "strategy_id": "legacy_paper_runtime",
            "candidate_id": f"legacy:{account.worker_id}",
            "config_hash": "legacy-unverified",
            "legacy": True,
            "runtime_path": str(runtime_path.resolve()),
            "adopted_by": approved_by,
        }
        state.setdefault("workers", {})[account.id] = worker
        self._save_state(state)
        return worker

    def reconcile_runtime(
        self,
        account_id: str,
        runtime_path: Path,
    ) -> dict[str, Any]:
        payload = _read_json(runtime_path)
        state = self._state()
        worker = state.setdefault("workers", {}).get(account_id)
        if not worker:
            return {"account_id": account_id, "status": "unmanaged_runtime"}
        if worker.get("status") == "stopped":
            return {
                "account_id": account_id,
                **worker,
                "old_runtime_ignored": True,
            }
        reasons = []
        if not worker.get("legacy"):
            if payload.get("evolution_candidate_id") != worker.get("candidate_id"):
                reasons.append("runtime_candidate_mismatch")
            if payload.get("evolution_config_hash") != worker.get("config_hash"):
                reasons.append("runtime_config_hash_mismatch")
        paper_flags = [
            row.get("paper")
            for key in ("balances", "open_orders", "positions")
            for row in payload.get(key, [])
            if isinstance(row, dict)
        ]
        if paper_flags and not all(flag is True for flag in paper_flags):
            reasons.append("non_paper_runtime_detected")
        worker["status"] = "protect" if reasons else "running"
        worker["runtime_path"] = str(runtime_path)
        worker["reconcile_blockers"] = reasons
        self._save_state(state)
        return {"account_id": account_id, **worker}

    def _release_blockers(self, target, release: StrategyRelease | None) -> list[str]:
        if release is None:
            return ["worker_release_missing"]
        blockers = []
        if release.candidate_id != target.candidate_id:
            blockers.append("worker_candidate_mismatch")
        if release.config_hash != target.config_hash:
            blockers.append("worker_config_hash_mismatch")
        if Environment.PAPER not in release.allowed_environments:
            blockers.append("worker_release_not_paper")
        return blockers

    def _start(self, action: WorkerAction, release: StrategyRelease):
        runner, env = self._validate_start(release)
        env["HUMMINGBOT_CONTAINER_NAME"] = action.worker_id
        return subprocess.run(
            [str(runner)],
            cwd=self.root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )

    def _validate_start(self, release: StrategyRelease) -> tuple[Path, dict[str, str]]:
        if not os.environ.get("CONFIG_PASSWORD"):
            raise ValueError("CONFIG_PASSWORD is required to start a paper worker")
        script_config = self._safe_path(release.artifact_ref, "conf/scripts")
        payload = yaml.safe_load(script_config.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("worker script config must be a YAML object")
        controller_names = payload.get("controllers_config") or []
        if not controller_names:
            raise ValueError("worker script config has no controllers")
        for name in controller_names:
            controller = self._safe_path(
                f"conf/controllers/{Path(name).name}", "conf/controllers"
            )
            controller_payload = yaml.safe_load(controller.read_text(encoding="utf-8"))
            connector = str((controller_payload or {}).get("connector_name", ""))
            if not connector.endswith("_paper_trade"):
                raise ValueError("worker start rejected a non-paper connector")
        runner, command_env = self._validated_start_command(release)
        env = os.environ.copy()
        env.update(command_env)
        env["SCRIPT_CONFIG"] = script_config.name
        return runner, env

    def _validated_start_command(
        self, release: StrategyRelease
    ) -> tuple[Path, dict[str, str]]:
        command = list(release.start_command)
        if not command:
            raise ValueError("release has no paper worker start command")
        command_env = {}
        if command[0] == "env":
            command.pop(0)
            while command and "=" in command[0]:
                key, value = command.pop(0).split("=", 1)
                if key != "SCRIPT_CONFIG" or Path(value).name != value:
                    raise ValueError("release start environment is not allowlisted")
                command_env[key] = value
        if len(command) != 1:
            raise ValueError("release start command must contain one paper runner")
        runner_name = Path(command[0]).name
        if not runner_name.startswith("run_") or not runner_name.endswith("_paper.sh"):
            raise ValueError("release start command is not a paper runner")
        return self._safe_path(f"scripts/{runner_name}", "scripts"), command_env

    def _stop(self, action: WorkerAction):
        docker = os.environ.get("DOCKER_BIN") or shutil.which("docker")
        if not docker:
            candidate = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
            docker = str(candidate) if candidate.exists() else None
        if not docker:
            raise ValueError("Docker CLI is required to stop a paper worker")
        return subprocess.run(
            [docker, "stop", "--time", "30", action.worker_id],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )

    @staticmethod
    def _container_running(worker_id: str) -> bool:
        docker = os.environ.get("DOCKER_BIN") or shutil.which("docker")
        if not docker:
            return False
        result = subprocess.run(
            [docker, "inspect", "--format", "{{.State.Running}}", worker_id],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def _safe_path(self, relative: str, prefix: str) -> Path:
        path = (self.root / relative).resolve()
        allowed = (self.root / prefix).resolve()
        if path != allowed and allowed not in path.parents:
            raise ValueError(f"worker artifact escapes allowlisted path: {relative}")
        if not path.is_file():
            raise ValueError(f"worker artifact does not exist: {relative}")
        return path

    def _state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "workers": {}}
        return payload if isinstance(payload, dict) else {"version": 1, "workers": {}}

    def _save_state(self, payload: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read runtime snapshot: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid runtime snapshot: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("runtime snapshot must contain an object")
    return payload
