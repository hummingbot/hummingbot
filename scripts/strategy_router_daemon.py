#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
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

from hummingbot.strategy_v2.routing.paths import (  # noqa: E402
    default_routing_config_path,
)
from hummingbot.strategy_v2.routing.service import StrategyRouterService  # noqa: E402


STOP = False


def _stop(_signum, _frame) -> None:
    global STOP
    STOP = True


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def resolve_runtime_inputs(
    root: Path, service: StrategyRouterService
) -> tuple[Path, str, Path]:
    integration = service.config.integration.evolution
    mappings: dict[str, dict[str, str]] = {}
    market_candidates: list[tuple[float, Path, str]] = []
    for manifest_path in sorted(root.glob(integration.release_manifest_glob)):
        release = _json(manifest_path)
        if release.get("status") not in {"active_verified", "paper_champion"}:
            continue
        strategy_id = str(release.get("strategy_id") or "")
        binding = service.config.bindings_by_id.get(strategy_id)
        runtime_value = release.get("runtime_file")
        if binding is None or not isinstance(runtime_value, str):
            continue
        runtime_path = (root / runtime_value).resolve()
        if root.resolve() not in runtime_path.parents or not runtime_path.is_file():
            continue
        runtime = _json(runtime_path)
        mark_prices = [
            row for row in runtime.get("mark_prices", []) if isinstance(row, dict)
        ]
        symbol = next(
            (
                str(row.get("symbol"))
                for row in mark_prices
                if row.get("symbol") in binding.allowed_pairs
            ),
            "",
        )
        if not symbol:
            continue
        account_id = binding.account_selector.account_ids[0]
        account = service.config.accounts_by_id[account_id]
        mappings[account_id] = {
            "path": str(runtime_path.relative_to(root)),
            "settlement_asset": account.settlement_asset,
        }
        market_candidates.append((runtime_path.stat().st_mtime, runtime_path, symbol))
    if not market_candidates:
        raise ValueError("no routable Evolution runtime snapshot is available")
    mapping_path = root / "data/strategy-routing/runtime-map.json"
    _atomic_json(mapping_path, {"runtime_snapshots": mappings})
    _, market_runtime, market_symbol = max(market_candidates, key=lambda row: row[0])
    return market_runtime, market_symbol, mapping_path


def heartbeat(status: str, **values: Any) -> None:
    _atomic_json(
        ROOT / "data/strategy-routing/heartbeat.json",
        {
            "version": 1,
            "status": status,
            "pid": os.getpid(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "paper_only": True,
            "apply_workers": os.environ.get("STRATEGY_ROUTER_APPLY_WORKERS") == "1",
            **values,
        },
    )


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    config_path = default_routing_config_path(ROOT)
    accounts_path = ROOT / "reports/examples/strategy_router_accounts.smoke.json"
    apply_workers = os.environ.get("STRATEGY_ROUTER_APPLY_WORKERS") == "1"
    iteration = 0
    while not STOP:
        iteration += 1
        try:
            # Reload the operational config every cycle so limits saved from the UI
            # take effect without restarting this daemon.
            service = StrategyRouterService(ROOT, config_path)
            interval = max(30, service.config.router.route_interval_seconds // 2)
            runtime_path, symbol, mapping_path = resolve_runtime_inputs(ROOT, service)
            result = service.run_once(
                None,
                accounts_path,
                apply_paper_workers=apply_workers,
                runtime_mapping_path=mapping_path,
                market_runtime_path=runtime_path,
                market_symbol=symbol,
            )
            heartbeat(
                "healthy",
                iteration=iteration,
                decision_id=result.get("plan", {}).get("decision_id"),
                decision_expires_at=result.get("plan", {}).get("expires_at"),
                worker_actions=result.get("worker_actions", []),
                market_symbol=symbol,
                runtime_file=str(runtime_path.relative_to(ROOT)),
                config_path=str(config_path.relative_to(ROOT)),
                last_error=None,
            )
            sleep_for = interval
        except Exception as exc:  # noqa: BLE001
            heartbeat("degraded", iteration=iteration, last_error=str(exc)[:500])
            sleep_for = 30
        deadline = time.monotonic() + sleep_for
        while not STOP and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    heartbeat("stopped", iteration=iteration, last_error=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
