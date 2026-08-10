"""``hbot status`` — report the bot's live state (one bot per install)."""
import os
import signal
import time
from typing import Any, Dict

from kairos.cli import bot
from kairos.cli.output import echo, emit, json_option, render_kv

# How long `hbot status` waits for the engine to write a fresh snapshot after SIGUSR1.
REFRESH_TIMEOUT = 5.0
# How many recent log lines to scan for errors (a running-but-broken bot logs but stays alive).
ERROR_SCAN_LINES = 600


def _recent_log_errors() -> Dict[str, Any]:
    """Scan the tail of the bot's structured log for ERROR/CRITICAL events.

    A bot can be process-alive + strategy_running while erroring every tick, so the snapshot alone
    can look healthy. This gives an agent a signal to investigate. Returns count + last few messages.
    """
    lines = bot.tail_lines(bot.structured_log_file(), ERROR_SCAN_LINES)
    errs = [ln for ln in lines if " - ERROR - " in ln or " - CRITICAL - " in ln]
    # line format: "<ts> - <pid> - <logger> - <LEVEL> - <message>"; keep just the message.
    messages = [ln.split(" - ", 4)[-1][:200] for ln in errs[-3:]]
    return {"count": len(errs), "messages": messages, "window": ERROR_SCAN_LINES}


def _request_fresh_snapshot(timeout: float = REFRESH_TIMEOUT) -> None:
    """Ask the running engine (via SIGUSR1) to write a current snapshot, and wait for it."""
    pid = bot.read_pid()
    if pid is None or not bot.is_engine_pid(pid):
        return
    prev = (bot.read_status() or {}).get("updated_at", 0)
    try:
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (bot.read_status() or {}).get("updated_at", 0) > prev:
            return
        time.sleep(0.1)


def status(as_json: bool = json_option()) -> None:
    """Show the bot's run state, live status, and errors."""
    # Unlike stop/logs/trades/history/update (which exit NOT_FOUND when there's no bot), `status` is a
    # poll: "is anything running?" is a valid question with a valid answer, so "no bot" is success
    # (exit 0, running=false) — a harness can poll status without treating the empty state as an error.
    if not bot.exists():
        # No bot has ever been started. If a config was `import`ed (loaded but not run), surface it so
        # the user sees what `hbot start` would launch — otherwise report the plain empty state.
        loaded = bot.read_loaded()
        if loaded and loaded.get("file"):
            record = {"running": False, "note": "imported, not started",
                      "config": loaded["file"], "type": loaded.get("type") or "-",
                      "next": "hbot start"}
        else:
            record = {"running": False, "note": "no strategy config loaded",
                      "next": "hbot create <strategy>  or  hbot import <file>"}
        emit(record, render_kv(record, title="status"), as_json)
        return

    running = bot.running()
    meta = bot.read_meta() or {}

    # A config imported after the last run supersedes the stopped bot's record: `hbot start` would
    # run the imported file, so that's what status must surface (matching what `hbot config` shows);
    # the previous run stays visible as last_run.
    if not running:
        loaded = bot.read_loaded()
        if loaded and loaded.get("file") and loaded["file"] != meta.get("file"):
            record = {"running": False, "note": "imported, not started",
                      "config": loaded["file"], "type": loaded.get("type") or "-",
                      "last_run": meta.get("name") or meta.get("file") or "-",
                      "next": "hbot start"}
            emit(record, render_kv(record, title="status"), as_json)
            return

    if running:
        _request_fresh_snapshot()
    # The snapshot describes the run that wrote it. Once the bot is stopped it's history, not status —
    # rendering its markets/orders/balances (or the stale pid) would present a dead run as live.
    snapshot = (bot.read_status() or {}) if running else {}
    engine = snapshot.get("engine") or {}
    started_at = meta.get("started_at")
    snapshot_age = (time.time() - snapshot["updated_at"]) if snapshot.get("updated_at") else None
    name = meta.get("name")
    strategy_name = engine.get("strategy_name") or meta.get("strategy_name")
    uptime = (time.time() - started_at) if (running and started_at) else None
    errors = _recent_log_errors()

    text = snapshot.get("format_status")

    if as_json:
        emit({
            "running": running,
            "name": name,
            "pid": bot.read_pid() if running else None,
            "config": meta.get("file"),
            "type": meta.get("type"),
            "strategy": strategy_name,
            "uptime_s": round(uptime, 1) if uptime else None,
            "snapshot_age_s": round(snapshot_age, 1) if snapshot_age is not None else None,
            "errors": errors,
            "format_status": text,
            "balances": snapshot.get("balances"),
        }, "", True)
        return

    fields = {
        "name": name,
        "state": "running" if running else "stopped",
        "pid": (bot.read_pid() if running else None) or "-",
        "config": meta.get("file") or "-",       # the strategy config file this bot runs
        "type": meta.get("type") or "-",          # v1-strategy / v2-script / controller
        "strategy": strategy_name or "-",
    }
    if uptime:
        fields["uptime"] = f"{uptime:.0f}s"
    if snapshot_age is not None:
        fields["snapshot"] = f"{snapshot_age:.0f}s ago"
    # Surface a running-but-broken bot: process is alive but the strategy is logging errors.
    if errors["count"]:
        last = errors["messages"][-1] if errors["messages"] else ""
        fields["errors"] = (f"{errors['count']} in last {errors['window']} log lines — last: "
                            f"{last[:120]} (run `hbot logs` for detail)")
    echo(render_kv(fields, title="status"))

    if text:
        echo("\n" + text)
