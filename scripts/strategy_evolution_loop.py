#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hummingbot.strategy_v2.evolution import EvolutionSupervisor, load_evolution_config  # noqa: E402
from hummingbot.strategy_v2.evolution.supervisor import render_supervisor_markdown  # noqa: E402


LOGGER = logging.getLogger("strategy-evolution")


def _configure_file_logging() -> None:
    log_file = os.environ.get("STRATEGY_EVOLUTION_LOG_FILE")
    if not log_file:
        return
    path = Path(log_file).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(handler)


def _emit(message: str, *, error: bool = False) -> None:
    print(message, file=sys.stderr if error else sys.stdout, flush=True)
    if LOGGER.handlers:
        LOGGER.error(message.replace("\n", " ")) if error else LOGGER.info(
            message.replace("\n", " ")
        )


def _backoff_seconds(
    consecutive_errors: int,
    *,
    initial: int,
    maximum: int,
    jitter_ratio: float = 0.0,
) -> float:
    base = min(maximum, initial * (2 ** min(max(consecutive_errors - 1, 0), 8)))
    if jitter_ratio <= 0:
        return float(base)
    return max(1.0, base * random.uniform(1 - jitter_ratio, 1 + jitter_ratio))


def _stop_on_signal(_signum, _frame) -> None:
    raise KeyboardInterrupt


def main() -> int:
    root = ROOT
    parser = argparse.ArgumentParser(
        description="多策略、证据驱动、禁止自动实盘的进化 Loop。"
    )
    parser.add_argument(
        "--config", type=Path, default=root / "conf" / "strategy_evolution.json"
    )
    parser.add_argument(
        "--strategy", action="append", default=[], help="只推进指定策略，可重复传入。"
    )
    parser.add_argument(
        "--run-checks", action="store_true", help="运行配置里的无 shell 确定性检查。"
    )
    parser.add_argument(
        "--auto-experiment",
        action="store_true",
        help="每轮智能选择并执行至多一个隔离的回测实验；不修改策略配置，不触发实盘。",
    )
    parser.add_argument("--watch", type=int, default=0, help="大于 0 时按秒持续运行。")
    parser.add_argument(
        "--max-iterations", type=int, default=1, help="0 表示持续运行。"
    )
    parser.add_argument(
        "--max-backoff", type=int, default=300, help="持续模式异常退避上限秒数。"
    )
    parser.add_argument(
        "--initial-backoff", type=int, default=5, help="持续模式首次异常退避秒数。"
    )
    parser.add_argument(
        "--json", action="store_true", help="输出 JSON 而不是中文战报。"
    )
    args = parser.parse_args()
    if args.initial_backoff < 1 or args.max_backoff < args.initial_backoff:
        parser.error("backoff values must satisfy 1 <= initial <= maximum")

    _configure_file_logging()
    signal.signal(signal.SIGTERM, _stop_on_signal)
    signal.signal(signal.SIGINT, _stop_on_signal)

    config = load_evolution_config(args.config.expanduser().resolve(), root=root)
    supervisor = EvolutionSupervisor(config)
    iteration = 0
    consecutive_errors = 0
    try:
        with supervisor.lock():
            recovered = supervisor.recover_in_flight_experiments()
            if recovered:
                _emit(
                    json.dumps({"recovered_experiments": recovered}, ensure_ascii=False)
                )
            while True:
                iteration += 1
                try:
                    payload = supervisor.run_once(
                        strategy_ids=args.strategy,
                        run_checks=args.run_checks,
                        auto_experiment=args.auto_experiment,
                    )
                    consecutive_errors = 0
                except Exception as exc:  # noqa: BLE001
                    if args.watch <= 0:
                        raise
                    consecutive_errors += 1
                    backoff = _backoff_seconds(
                        consecutive_errors,
                        initial=args.initial_backoff,
                        maximum=args.max_backoff,
                        jitter_ratio=0.2,
                    )
                    previous_heartbeat = supervisor.store.read_heartbeat()
                    observed_at = datetime.now(timezone.utc).isoformat()
                    error_payload = {
                        "version": 3,
                        "status": "degraded",
                        "phase": "backoff",
                        "pid": os.getpid(),
                        "last_activity": observed_at,
                        "last_success": previous_heartbeat.get("last_success"),
                        "last_error": str(exc)[:500],
                        "iteration": iteration,
                        "consecutive_errors": consecutive_errors,
                        "retry_in_seconds": round(backoff, 3),
                        "liveness_status": "healthy",
                        "readiness_status": "degraded",
                        "safety_status": "unknown",
                        "runtime_identity": previous_heartbeat.get("runtime_identity"),
                    }
                    supervisor.store.save_heartbeat(error_payload)
                    supervisor.store.record_alert(
                        severity="error",
                        source="supervisor",
                        message=str(exc)[:500],
                        context={"iteration": iteration},
                    )
                    _emit(json.dumps(error_payload, ensure_ascii=False), error=True)
                    time.sleep(backoff)
                    continue
                _emit(
                    json.dumps(payload, ensure_ascii=False, indent=2)
                    if args.json
                    else render_supervisor_markdown(payload)
                )
                if args.watch <= 0 or (
                    args.max_iterations > 0 and iteration >= args.max_iterations
                ):
                    return 0
                time.sleep(max(5, args.watch))
    except KeyboardInterrupt:
        previous_heartbeat = supervisor.store.read_heartbeat()
        supervisor.store.save_heartbeat(
            {
                **previous_heartbeat,
                "version": 3,
                "status": "stopped",
                "phase": "stopped",
                "pid": os.getpid(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        _emit(str(exc), error=True)
        return 2
    except Exception as exc:  # noqa: BLE001
        _emit(f"strategy evolution loop failed safely: {exc}", error=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
