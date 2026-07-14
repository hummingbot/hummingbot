#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.strategy_routing_bootstrap import (  # noqa: E402
    bootstrap_hummingbot_namespace,
)

bootstrap_hummingbot_namespace(ROOT)

from hummingbot.strategy_v2.routing.service import StrategyRouterService  # noqa: E402
from hummingbot.strategy_v2.routing.paths import default_routing_config_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed Evolution-to-paper-worker strategy router."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_routing_config_path(ROOT),
    )
    market_group = parser.add_mutually_exclusive_group(required=True)
    market_group.add_argument("--market", type=Path)
    market_group.add_argument(
        "--market-runtime",
        type=Path,
        help="Build a conservative market state from a Hummingbot runtime snapshot.",
    )
    parser.add_argument("--market-symbol", default=None)
    parser.add_argument("--accounts", type=Path, required=True)
    parser.add_argument(
        "--runtime-map",
        type=Path,
        default=None,
        help="Optional account-to-Hummingbot runtime snapshot mapping.",
    )
    parser.add_argument("--now", type=float, default=None)
    parser.add_argument(
        "--apply-paper-workers",
        action="store_true",
        help="Actually start/stop paper-only workers; requires CONFIG_PASSWORD.",
    )
    parser.add_argument("--watch", type=int, default=0)
    parser.add_argument("--max-iterations", type=int, default=1)
    args = parser.parse_args()
    service = StrategyRouterService(ROOT, args.config)
    iteration = 0
    try:
        while True:
            iteration += 1
            payload = service.run_once(
                args.market,
                args.accounts,
                now=args.now,
                apply_paper_workers=args.apply_paper_workers,
                runtime_mapping_path=args.runtime_map,
                market_runtime_path=args.market_runtime,
                market_symbol=args.market_symbol,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
            if args.watch <= 0 or (
                args.max_iterations > 0 and iteration >= args.max_iterations
            ):
                return 0
            time.sleep(max(5, args.watch))
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
