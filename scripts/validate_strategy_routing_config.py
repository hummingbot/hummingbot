#!/usr/bin/env python3
"""Validate the paper-first multi-account routing configuration contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.strategy_routing_bootstrap import (  # noqa: E402
    bootstrap_hummingbot_namespace,
)

bootstrap_hummingbot_namespace(ROOT)

from hummingbot.strategy_v2.routing.config import load_routing_config  # noqa: E402
from hummingbot.strategy_v2.routing.paths import default_routing_config_path  # noqa: E402
from hummingbot.strategy_v2.routing.release import (  # noqa: E402
    load_evolution_release_manifests,
    validate_evolution_single_writer,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=default_routing_config_path(ROOT),
    )
    args = parser.parse_args()
    path = args.config.resolve()
    try:
        config = load_routing_config(path)
        integration = config.integration.evolution
        release_count = 0
        if integration.enabled:
            validate_evolution_single_writer(ROOT, integration.evolution_config_path)
            manifest = load_evolution_release_manifests(
                ROOT, integration.release_manifest_glob
            )
            release_count = len(manifest.releases)
    except ValueError as exc:
        print(
            json.dumps(
                {"ok": False, "config": str(path), "error": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    payload = {
        "ok": True,
        "config": str(path),
        "environment": config.environment.value,
        "accounts": len(config.accounts),
        "trading_workers": len([row for row in config.accounts if row.trading_enabled]),
        "strategy_bindings": len(config.strategy_bindings),
        "live_actions": config.release.allow_live_actions,
        "automatic_transfers": config.release.allow_automatic_transfers,
        "ai_enabled": config.ai.enabled,
        "ai_mode": config.ai.mode,
        "evolution_integration": config.integration.evolution.enabled,
        "evolution_auto_start": config.integration.evolution.allow_evolution_auto_start,
        "evolution_releases": release_count,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
