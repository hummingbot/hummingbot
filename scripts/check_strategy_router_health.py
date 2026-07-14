#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "data/strategy-routing/heartbeat.json"
    try:
        heartbeat = json.loads(path.read_text(encoding="utf-8"))
        latest = json.loads(
            (ROOT / "data/strategy-routing/latest.json").read_text(encoding="utf-8")
        )
        updated = datetime.fromisoformat(
            str(heartbeat["updated_at"]).replace("Z", "+00:00")
        ).timestamp()
        expires = float(latest["plan"]["expires_at"])
        pid = int(heartbeat["pid"])
        os.kill(pid, 0)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"unhealthy: invalid router state: {exc}", file=sys.stderr)
        return 1
    age = time.time() - updated
    if heartbeat.get("status") != "healthy" or age > 240 or expires <= time.time():
        print(
            f"unhealthy: status={heartbeat.get('status')} age={age:.1f} expires={expires}",
            file=sys.stderr,
        )
        return 1
    print(f"healthy: route={heartbeat.get('decision_id')} age={age:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
