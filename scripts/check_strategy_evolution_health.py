#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check strategy evolution heartbeat freshness."
    )
    parser.add_argument(
        "--heartbeat",
        type=Path,
        default=ROOT / "data/strategy-evolution/heartbeat.json",
    )
    parser.add_argument("--maximum-age", type=int, default=900)
    parser.add_argument("--maximum-running-age", type=int, default=2400)
    parser.add_argument("--require-live-process", action="store_true")
    parser.add_argument(
        "--mode", choices=("liveness", "readiness", "safety"), default="liveness"
    )
    parser.add_argument(
        "--expected-source-sha256",
        default=os.environ.get("STRATEGY_EVOLUTION_SOURCE_SHA256", ""),
    )
    args = parser.parse_args()
    try:
        payload = json.loads(args.heartbeat.read_text(encoding="utf-8"))
        status = str(payload.get("status") or "unknown")
        timestamp = (
            payload.get("cycle_started_at")
            if status == "running"
            else payload.get("last_activity") or payload.get("last_success")
        )
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = (
            datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
        ).total_seconds()
        pid = int(payload.get("pid"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"unhealthy: invalid heartbeat: {exc}")
        return 2
    if age < -300:
        print(f"unhealthy: heartbeat timestamp is in the future by {-age:.1f}s")
        return 2
    process_alive = _pid_alive(pid)
    actual_source = str(
        (payload.get("runtime_identity") or {}).get("source_sha256") or ""
    )
    if args.expected_source_sha256 and actual_source != args.expected_source_sha256:
        print("unhealthy: runtime source fingerprint mismatch")
        return 1
    if status == "running":
        if not process_alive or age > args.maximum_running_age:
            print(
                f"unhealthy: status=running pid_alive={process_alive} "
                f"age_seconds={age:.1f}"
            )
            return 1
        if args.mode != "liveness":
            print(f"unhealthy: status=running mode={args.mode}")
            return 1
        print(f"healthy: status=running pid={pid} age_seconds={age:.1f}")
        return 0
    if status not in {"healthy", "degraded"} or age > args.maximum_age:
        print(f"unhealthy: status={status} age_seconds={age:.1f}")
        return 1
    if args.require_live_process and not process_alive:
        print(f"unhealthy: status=healthy pid={pid} is not running")
        return 1
    if args.mode == "readiness" and payload.get("readiness_status") != "ready":
        print(
            f"unhealthy: readiness={payload.get('readiness_status')} "
            f"issues={payload.get('safety_issues') or []}"
        )
        return 1
    if args.mode == "safety" and payload.get("safety_status") != "safe":
        print(
            f"unhealthy: safety={payload.get('safety_status')} "
            f"issues={payload.get('safety_issues') or []}"
        )
        return 1
    print(f"healthy: mode={args.mode} status={status} pid={pid} age_seconds={age:.1f}")
    return 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
