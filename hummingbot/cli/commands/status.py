"""``hbot status`` — report the bot's live state (one bot per install)."""
import os
import signal
import time
from typing import Any, Dict

from hummingbot.cli import bot
from hummingbot.cli.output import echo, render_kv

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
    if pid is None or not bot.pid_alive(pid):
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


def status() -> None:
    """Show the bot's run state, live status, and errors."""
    # Unlike stop/logs/trades/history/update (which exit NOT_FOUND when there's no bot), `status` is a
    # poll: "is anything running?" is a valid question with a valid answer, so "no bot" is success
    # (exit 0, running=false) — a harness can poll status without treating the empty state as an error.
    if not bot.exists():
        # No bot has ever been started. If a config was `import`ed (loaded but not run), surface it so
        # the user sees what `hbot start` would launch — otherwise report the plain empty state.
        loaded = bot.read_loaded()
        if loaded and loaded.get("file"):
            echo(render_kv({"running": False, "note": "imported, not started",
                            "config": loaded["file"], "type": loaded.get("type") or "-",
                            "next": "hbot start"}, title="status"))
        else:
            echo(render_kv({"running": False, "note": "no strategy config loaded",
                            "next": "hbot create <strategy>  or  hbot import <file>"}, title="status"))
        return

    _request_fresh_snapshot()
    running = bot.running()
    snapshot = bot.read_status() or {}
    meta = bot.read_meta() or {}
    engine = snapshot.get("engine") or {}
    started_at = meta.get("started_at")
    snapshot_age = (time.time() - snapshot["updated_at"]) if snapshot.get("updated_at") else None
    name = meta.get("name")
    strategy_name = engine.get("strategy_name") or meta.get("strategy_name")
    uptime = (time.time() - started_at) if (running and started_at) else None
    errors = _recent_log_errors()

    fields = {
        "name": name,
        "state": "running" if running else "stopped",
        "pid": bot.read_pid() or "-",
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

    text = snapshot.get("format_status")
    if text:
        echo("\n" + text)
