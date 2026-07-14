#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.strategy_routing_bootstrap import (  # noqa: E402
    bootstrap_hummingbot_namespace,
)

bootstrap_hummingbot_namespace(ROOT)

from hummingbot.strategy_v2.routing.config import RoutingConfig  # noqa: E402
from hummingbot.strategy_v2.routing.paths import (  # noqa: E402
    default_routing_config_path,
)


FIELDS = {
    "minimum_reserve_quote": ("allocation", "minimum_reserve_quote", float),
    "maximum_capital_quote": ("allocation", "maximum_capital_quote", float),
    "maximum_drawdown_quote": ("risk", "maximum_drawdown_quote", float),
    "maximum_gross_exposure_quote": (
        "risk",
        "maximum_gross_exposure_quote",
        float,
    ),
    "maximum_open_orders": ("risk", "maximum_open_orders", int),
    "market_data_stale_after_seconds": (
        "risk",
        "market_data_stale_after_seconds",
        int,
    ),
}


def update_account(
    source: Path,
    destination: Path,
    account_id: str,
    values: dict[str, float | int],
) -> dict:
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("cannot read current routing configuration") from exc
    if not isinstance(payload, dict) or payload.get("environment") != "paper":
        raise ValueError("admin account updates require a paper routing configuration")
    accounts = payload.get("accounts")
    if not isinstance(accounts, list):
        raise ValueError("routing configuration has no accounts")
    account = next(
        (
            row
            for row in accounts
            if isinstance(row, dict) and row.get("id") == account_id
        ),
        None,
    )
    if account is None:
        raise ValueError("unknown routing account")
    for name, value in values.items():
        section, key, cast = FIELDS[name]
        account.setdefault(section, {})[key] = cast(value)
    validated = RoutingConfig.model_validate(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_text(
        yaml.safe_dump(
            validated.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    temporary.replace(destination)
    updated = validated.accounts_by_id[account_id]
    try:
        config_path = str(destination.relative_to(ROOT))
    except ValueError:
        config_path = str(destination)
    return {
        "account_id": account_id,
        "config_path": config_path,
        "allocation": updated.allocation.model_dump(mode="json"),
        "risk": updated.risk.model_dump(mode="json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update allowlisted paper account limits with full config validation."
    )
    parser.add_argument("--account", required=True)
    for field, (_, _, cast) in FIELDS.items():
        parser.add_argument(f"--{field.replace('_', '-')}", type=cast)
    args = parser.parse_args()
    values = {
        field: getattr(args, field)
        for field in FIELDS
        if getattr(args, field) is not None
    }
    if not values:
        print(json.dumps({"ok": False, "error": "no account limits supplied"}))
        return 2
    source = default_routing_config_path(ROOT)
    destination = ROOT / "conf/runtime/strategy_router_accounts.yml"
    lock_path = ROOT / "data/strategy-routing/account-config.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            result = update_account(source, destination, args.account, values)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, "account": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
