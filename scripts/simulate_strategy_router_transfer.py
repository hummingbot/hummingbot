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

from hummingbot.strategy_v2.routing.config import load_routing_config  # noqa: E402
from hummingbot.strategy_v2.routing.paths import default_routing_config_path  # noqa: E402
from hummingbot.strategy_v2.routing.transfer import (  # noqa: E402
    PaperTransferRequest,
    PaperTransferSimulator,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute an idempotent paper-only account transfer simulation."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_routing_config_path(ROOT),
    )
    parser.add_argument("--transfer-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--amount", required=True, type=float)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument(
        "--seed-balances",
        type=Path,
        help="Optional one-time JSON object mapping account_id to paper balance.",
    )
    args = parser.parse_args()
    config = load_routing_config(args.config)
    simulator = PaperTransferSimulator(
        config,
        ROOT / "data/strategy-routing/paper-balances.json",
        ROOT / "data/strategy-routing/transfers.jsonl",
    )
    try:
        if args.seed_balances:
            balances = json.loads(args.seed_balances.read_text(encoding="utf-8"))
            if not isinstance(balances, dict):
                raise ValueError("seed balances must be a JSON object")
            simulator.seed({key: float(value) for key, value in balances.items()})
        result = simulator.execute(
            PaperTransferRequest(
                transfer_id=args.transfer_id,
                source_account_id=args.source,
                target_account_id=args.target,
                amount_quote=args.amount,
                approved_by=args.approved_by,
                requested_at=time.time(),
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, "transfer": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
