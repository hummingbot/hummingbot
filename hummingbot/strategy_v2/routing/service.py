from __future__ import annotations

import fcntl
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from hummingbot.strategy_v2.routing.adapters import (
    EvolutionCandidateAdapter,
    load_account_snapshots,
    load_market_state,
    load_runtime_mapping,
    market_state_from_runtime,
    merge_runtime_account_snapshots,
)
from hummingbot.strategy_v2.routing.ai_provider import DeepSeekRoutingClient
from hummingbot.strategy_v2.routing.config import RoutingConfig, load_routing_config
from hummingbot.strategy_v2.routing.ledger import DecisionLedger
from hummingbot.strategy_v2.routing.lifecycle import PersistentLifecycleGate
from hummingbot.strategy_v2.routing.release import (
    load_evolution_release_manifests,
    validate_evolution_single_writer,
)
from hummingbot.strategy_v2.routing.supervisor import StrategyRoutingSupervisor
from hummingbot.strategy_v2.routing.worker import PaperWorkerManager


class StrategyRouterService:
    def __init__(
        self,
        root: Path,
        config_path: Path,
        *,
        state_dir: Path | None = None,
        container_probe: Callable[[str], bool] | None = None,
    ):
        self.root = root.resolve()
        self.config_path = config_path.resolve()
        self.config: RoutingConfig = load_routing_config(self.config_path)
        self.state_dir = state_dir or self.root / "data/strategy-routing"
        self.ledger = DecisionLedger(self.state_dir / "decisions.jsonl")
        self.workers = PaperWorkerManager(
            self.root,
            self.config,
            self.state_dir / "workers.json",
            container_probe=container_probe,
        )
        self.ai = DeepSeekRoutingClient(
            self.config.ai,
            self.state_dir / "ai-circuit.json",
        )
        self.lifecycle = PersistentLifecycleGate(
            self.config.router.switch_policy,
            self.state_dir / "lifecycle.json",
        )

    def run_once(
        self,
        market_path: Path | None,
        account_snapshots_path: Path,
        *,
        now: float | None = None,
        apply_paper_workers: bool = False,
        runtime_mapping_path: Path | None = None,
        market_runtime_path: Path | None = None,
        market_symbol: str | None = None,
    ) -> dict[str, Any]:
        with self._lock():
            return self._run_once_locked(
                market_path,
                account_snapshots_path,
                now=now,
                apply_paper_workers=apply_paper_workers,
                runtime_mapping_path=runtime_mapping_path,
                market_runtime_path=market_runtime_path,
                market_symbol=market_symbol,
            )

    def _run_once_locked(
        self,
        market_path: Path | None,
        account_snapshots_path: Path,
        *,
        now: float | None,
        apply_paper_workers: bool,
        runtime_mapping_path: Path | None,
        market_runtime_path: Path | None,
        market_symbol: str | None,
    ) -> dict[str, Any]:
        now = time.time() if now is None else now
        integration = self.config.integration.evolution
        if not integration.enabled:
            raise ValueError("Evolution integration must be enabled for router service")
        validate_evolution_single_writer(self.root, integration.evolution_config_path)
        manifest = load_evolution_release_manifests(
            self.root,
            integration.release_manifest_glob,
        )
        if (market_path is None) == (market_runtime_path is None):
            raise ValueError(
                "provide exactly one market file or market runtime snapshot"
            )
        market = (
            load_market_state(market_path)
            if market_path is not None
            else market_state_from_runtime(
                market_runtime_path,
                symbol=market_symbol,
            )
        )
        snapshots = load_account_snapshots(account_snapshots_path)
        if runtime_mapping_path is not None:
            snapshots = merge_runtime_account_snapshots(
                self.root,
                runtime_mapping_path,
                snapshots,
            )
            for account_id, (runtime_path, _) in load_runtime_mapping(
                self.root,
                runtime_mapping_path,
            ).items():
                runtime_status = self.workers.reconcile_runtime(
                    account_id, runtime_path
                )
                if runtime_status.get("status") in {"running", "stopped"}:
                    snapshots[account_id] = snapshots[account_id].model_copy(
                        update={"runtime_managed": True}
                    )
        candidates = EvolutionCandidateAdapter(self.root, self.config).build(
            manifest,
            market,
        )
        ai_signal = self.ai.evaluate(market, candidates)
        plan = StrategyRoutingSupervisor(self.config).plan(
            market,
            snapshots,
            candidates,
            now=now,
            ai_signal=ai_signal,
            release_manifest=manifest,
        )
        appended = self.ledger.append(plan)
        actions = self.workers.plan_actions(plan, manifest)
        actions = self.lifecycle.gate(actions, plan, now=now)
        worker_results = []
        if apply_paper_workers:
            worker_results = self.workers.apply(actions, manifest)
            if any(
                row.get("action") == "drain" and row.get("status") == "stopped"
                for row in worker_results
            ):
                follow_up = self.workers.plan_actions(plan, manifest)
                follow_up = self.lifecycle.gate(follow_up, plan, now=now)
                worker_results.extend(self.workers.apply(follow_up, manifest))
                actions.extend(follow_up)
        payload = {
            "version": 1,
            "mode": "paper_apply" if apply_paper_workers else "paper_plan",
            "decision_appended": appended,
            "release_count": len(manifest.releases),
            "candidate_count": len(candidates),
            "plan": plan.model_dump(mode="json"),
            "worker_actions": [row.model_dump(mode="json") for row in actions],
            "worker_results": worker_results,
            "runtime_mapping_applied": runtime_mapping_path is not None,
            "ai_signal": ai_signal.model_dump(mode="json") if ai_signal else None,
        }
        self._save_latest(payload)
        return payload

    @contextmanager
    def _lock(self):
        path = self.state_dir / "router.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError(
                    "another StrategyRouterService instance is active"
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _save_latest(self, payload: dict[str, Any]) -> None:
        path = self.state_dir / "latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
