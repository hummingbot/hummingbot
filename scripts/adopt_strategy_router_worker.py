#!/usr/bin/env python3
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
from hummingbot.strategy_v2.routing.worker import PaperWorkerManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adopt a verified legacy paper container into Routing state."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_routing_config_path(ROOT),
    )
    parser.add_argument("--account", required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    try:
        config = load_routing_config(args.config)
        manager = PaperWorkerManager(
            ROOT,
            config,
            ROOT / "data/strategy-routing/workers.json",
        )
        worker = manager.adopt_legacy_paper_worker(
            args.account,
            args.runtime,
            approved_by=args.approved_by,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, "worker": worker}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
