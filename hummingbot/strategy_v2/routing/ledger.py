from __future__ import annotations

import json
import os
from pathlib import Path

import fcntl

from hummingbot.strategy_v2.routing.data_types import RoutePlan


class DecisionLedger:
    """Append-only, idempotent JSONL store for route plans."""

    def __init__(self, path: Path):
        self.path = path

    def append(self, plan: RoutePlan) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.seek(0)
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("decision_id") == plan.decision_id:
                        return False
                handle.seek(0, os.SEEK_END)
                handle.write(
                    json.dumps(
                        plan.model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
                return True
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
