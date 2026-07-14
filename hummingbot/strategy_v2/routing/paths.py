from __future__ import annotations

from pathlib import Path


def default_routing_config_path(root: Path) -> Path:
    """Prefer the ignored operational config, falling back to the reviewed template."""
    operational = root / "conf/runtime/strategy_router_accounts.yml"
    if operational.is_file():
        return operational
    legacy = root / "conf/strategy_router_accounts.yml"
    if legacy.is_file():
        return legacy
    return root / "reports/examples/strategy_router_accounts.example.yml"
