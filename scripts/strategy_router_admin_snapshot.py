#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.strategy_routing_bootstrap import (  # noqa: E402
    bootstrap_hummingbot_namespace,
)

bootstrap_hummingbot_namespace(ROOT)

from hummingbot.strategy_v2.routing.adapters import (  # noqa: E402
    load_account_snapshots,
    load_runtime_mapping,
    merge_runtime_account_snapshots,
)
from hummingbot.strategy_v2.routing.config import load_routing_config  # noqa: E402
from hummingbot.strategy_v2.routing.paths import default_routing_config_path  # noqa: E402


def _json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return list(reversed(rows))


def _container_state(worker_id: str | None) -> str:
    if not worker_id or not shutil.which("docker"):
        return "unavailable"
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", worker_id],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() if result.returncode == 0 else "missing"


def _iso_age_seconds(value: Any, now: float) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
    return max(0.0, now - timestamp)


def _account_runtime(root: Path, mapping_path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    try:
        mapping = load_runtime_mapping(root, mapping_path)
    except ValueError:
        return result
    for account_id, (path, settlement_asset) in mapping.items():
        payload = _json(path, {})
        if not isinstance(payload, dict):
            continue
        balances = payload.get("balances") or []
        quote_rows = [
            row
            for row in balances
            if isinstance(row, dict) and row.get("asset") == settlement_asset
        ]
        paper_flags = [
            row.get("paper")
            for key in ("balances", "positions", "open_orders")
            for row in payload.get(key, [])
            if isinstance(row, dict)
        ]
        result[account_id] = {
            "path": str(path.relative_to(root)),
            "generatedAt": payload.get("generated_at"),
            "settlementAsset": settlement_asset,
            "totalQuote": sum(float(row.get("total", 0)) for row in quote_rows),
            "availableQuote": sum(float(row.get("available", 0)) for row in quote_rows),
            "openOrders": len(payload.get("open_orders") or []),
            "positions": len(payload.get("positions") or []),
            "candidateId": payload.get("evolution_candidate_id"),
            "configHash": payload.get("evolution_config_hash"),
            "paperOnly": bool(paper_flags)
            and all(flag is True for flag in paper_flags),
        }
    return result


def _release_manifests(glob_pattern: str) -> list[dict[str, Any]]:
    releases = []
    for path in ROOT.glob(glob_pattern):
        row = _json(path, {})
        if isinstance(row, dict):
            releases.append({**row, "manifest_path": str(path.relative_to(ROOT))})
    return releases


def build_snapshot(
    config_path: Path,
    accounts_path: Path,
    runtime_map_path: Path,
) -> dict[str, Any]:
    now = time.time()
    config = load_routing_config(config_path)
    route_state = _json(ROOT / "data/strategy-routing/latest.json", {})
    worker_state = _json(ROOT / "data/strategy-routing/workers.json", {})
    lifecycle_state = _json(ROOT / "data/strategy-routing/lifecycle.json", {})
    transfer_state = _json(ROOT / "data/strategy-routing/paper-balances.json", {})
    evolution = _json(ROOT / "data/strategy-evolution/latest.json", {})
    heartbeat = _json(ROOT / "data/strategy-evolution/heartbeat.json", {})
    router_heartbeat = _json(ROOT / "data/strategy-routing/heartbeat.json", {})
    runtime_rows = _account_runtime(ROOT, runtime_map_path)

    snapshots = {}
    try:
        snapshots = load_account_snapshots(accounts_path)
        snapshots = merge_runtime_account_snapshots(ROOT, runtime_map_path, snapshots)
    except ValueError:
        snapshots = {}

    workers_by_account = worker_state.get("workers", {})
    balances = transfer_state.get("balances", {})
    accounts = []
    for account in config.accounts:
        snapshot = snapshots.get(account.id)
        worker = workers_by_account.get(account.id, {})
        runtime = runtime_rows.get(account.id)
        runtime_age = (
            _iso_age_seconds(runtime.get("generatedAt"), now) if runtime else None
        )
        accounts.append(
            {
                "id": account.id,
                "kind": account.kind.value,
                "parentId": account.parent_id,
                "exchange": account.exchange,
                "connector": account.connector,
                "workerId": account.worker_id,
                "tradingEnabled": account.trading_enabled,
                "settlementAsset": account.settlement_asset,
                "allowedSleeves": [row.value for row in account.allowed_sleeves],
                "allowedPairs": account.allowed_pairs,
                "positionMode": account.position_mode,
                "marginMode": account.margin_mode,
                "allocation": {
                    "minimumReserveQuote": account.allocation.minimum_reserve_quote,
                    "maximumCapitalQuote": account.allocation.maximum_capital_quote,
                },
                "risk": {
                    "maximumDrawdownQuote": account.risk.maximum_drawdown_quote,
                    "maximumGrossExposureQuote": account.risk.maximum_gross_exposure_quote,
                    "maximumOpenOrders": account.risk.maximum_open_orders,
                    "maximumLeverage": account.risk.maximum_leverage,
                    "marketDataStaleAfterSeconds": account.risk.market_data_stale_after_seconds,
                },
                "permissions": {
                    "trade": account.permissions.trade,
                    "internalTransfer": account.permissions.internal_transfer,
                    "withdraw": account.permissions.withdraw,
                },
                "transferPolicy": {
                    "enabled": account.transfer_policy.enabled,
                    "requireManualApproval": account.transfer_policy.require_manual_approval,
                    "allowedCounterparties": account.transfer_policy.allowed_counterparties,
                    "minimumTransferQuote": account.transfer_policy.minimum_transfer_quote,
                    "maximumTransferQuote": account.transfer_policy.maximum_transfer_quote,
                    "maximumDailyTransferQuote": account.transfer_policy.maximum_daily_transfer_quote,
                    "cooldownSeconds": account.transfer_policy.cooldown_seconds,
                },
                "snapshot": snapshot.model_dump(mode="json") if snapshot else None,
                "paperBalance": balances.get(account.id),
                "workerStatus": worker.get("status"),
                "containerState": _container_state(account.worker_id),
                "runtime": runtime,
                "runtimeAgeSeconds": runtime_age,
                "runtimeFresh": runtime_age is not None
                and runtime_age <= account.risk.market_data_stale_after_seconds,
            }
        )

    strategies_by_id = {
        row.get("strategy_id"): row
        for row in evolution.get("strategies", [])
        if isinstance(row, dict) and row.get("strategy_id")
    }
    strategies = []
    for binding in config.strategy_bindings:
        evo = strategies_by_id.get(binding.strategy_id, {})
        strategies.append(
            {
                "strategyId": binding.strategy_id,
                "sleeve": binding.sleeve.value,
                "accountIds": binding.account_selector.account_ids,
                "allowedPairs": binding.allowed_pairs,
                "compatibilityGroup": binding.compatibility_group,
                "maximumInstancesPerAccount": binding.maximum_instances_per_account,
                "evolutionStatus": evo.get("status"),
                "evolutionStage": evo.get("stage_after"),
                "evolutionRunStatus": evo.get("run_status_after"),
                "nextStep": evo.get("next_step"),
            }
        )

    plan = route_state.get("plan", {}) if isinstance(route_state, dict) else {}
    route_expires_at = plan.get("expires_at")
    route_fresh = isinstance(route_expires_at, (int, float)) and route_expires_at >= now
    releases = _release_manifests(config.integration.evolution.release_manifest_glob)
    evolution_issues = heartbeat.get("safety_issues", [])
    routed_strategies = {
        row.get("strategy_id")
        for row in plan.get("allocations", [])
        if isinstance(row, dict) and row.get("strategy_id")
    }
    routed_evolution_issues = [
        str(item)
        for item in evolution_issues
        if str(item).split(":", 1)[0] in routed_strategies
    ]
    conflicts = []
    if routed_evolution_issues:
        conflicts.append("evolution_readiness_degraded")
        conflicts.extend(routed_evolution_issues)
    if not route_fresh:
        conflicts.append("route_expired")
    if any(
        row["workerStatus"] == "running" and row["containerState"] != "running"
        for row in accounts
    ):
        conflicts.append("worker_state_container_mismatch")
    if any(
        release.get("status") not in {"active_verified", "paper_champion"}
        for release in releases
    ):
        conflicts.append("release_not_active_verified")

    return {
        "version": 1,
        "ok": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "configPath": str(config_path.relative_to(ROOT)),
        "configValidated": True,
        "environment": config.environment.value,
        "safety": {
            "paperOnly": config.environment.value == "paper",
            "liveActions": config.release.allow_live_actions,
            "automaticTransfers": config.release.allow_automatic_transfers,
            "manualTransferApproval": config.release.require_manual_transfer_approval,
            "evolutionAutoStart": config.integration.evolution.allow_evolution_auto_start,
            "aiEnabled": config.ai.enabled,
            "aiMode": config.ai.mode,
            "aiProvider": config.ai.provider,
            "aiPrimaryModel": config.ai.primary_model,
        },
        "router": {
            "routeIntervalSeconds": config.router.route_interval_seconds,
            "requireClosedCandle": config.router.require_closed_candle,
            "reserveQuotePct": config.router.reserve_quote_pct,
            "minimumCandidateScore": config.router.minimum_candidate_score,
            "switchPolicy": config.router.switch_policy.model_dump(mode="json"),
        },
        "routerHeartbeat": router_heartbeat,
        "globalRisk": config.global_risk.model_dump(mode="json"),
        "accounts": accounts,
        "strategies": strategies,
        "compatibility": [
            row.model_dump(mode="json") for row in config.compatibility.rules
        ],
        "route": {
            "mode": route_state.get("mode"),
            "decisionAppended": route_state.get("decision_appended"),
            "releaseCount": route_state.get("release_count", 0),
            "candidateCount": route_state.get("candidate_count", 0),
            "plan": plan,
            "workerActions": route_state.get("worker_actions", []),
            "runtimeMappingApplied": route_state.get("runtime_mapping_applied", False),
            "fresh": route_fresh,
        },
        "workers": list(workers_by_account.values()),
        "lifecycle": list(lifecycle_state.get("entries", {}).values()),
        "evolution": {
            "generatedAt": evolution.get("generated_at"),
            "summary": evolution.get("summary", {}),
            "strategies": evolution.get("strategies", []),
            "heartbeat": heartbeat,
            "runtimeIdentity": evolution.get("runtime_identity"),
        },
        "releases": releases,
        "decisions": _jsonl(ROOT / "data/strategy-routing/decisions.jsonl", 12),
        "transfers": {
            "balances": balances,
            "lastTransfer": transfer_state.get("last_transfer", {}),
            "events": _jsonl(ROOT / "data/strategy-routing/transfers.jsonl", 12),
        },
        "conflicts": list(dict.fromkeys(conflicts)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit the sanitized Strategy Routing admin snapshot."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_routing_config_path(ROOT),
    )
    parser.add_argument(
        "--accounts",
        type=Path,
        default=ROOT / "reports/examples/strategy_router_accounts.smoke.json",
    )
    parser.add_argument(
        "--runtime-map",
        type=Path,
        default=ROOT / "reports/examples/strategy_router_runtime_map.example.json",
    )
    args = parser.parse_args()
    try:
        payload = build_snapshot(args.config, args.accounts, args.runtime_map)
    except (OSError, ValueError) as exc:
        payload = {
            "version": 1,
            "ok": False,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
