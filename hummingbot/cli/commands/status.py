"""``hbot status`` — report the bot's live state (one bot per install)."""
import os
import signal
import time
from typing import Any, Dict

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import print_json

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


def status(
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show the bot's status: liveness, the strategy's format_status, and any recent errors."""
    if not bot.exists():
        if json_output:
            print_json({"ok": True, "running": False, "note": "no bot started"})
        else:
            typer.echo("No bot started. Run `hbot start <config> --v1|--v2|--controller`.")
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

    if json_output:
        print_json({"ok": True, "name": name, "running": running, "pid": bot.read_pid(),
                    "strategy_name": strategy_name, "uptime_seconds": uptime,
                    "snapshot_age_seconds": snapshot_age, "engine": snapshot.get("engine"),
                    "recent_errors": errors, "balances": snapshot.get("balances"),
                    "format_status": snapshot.get("format_status")})
        return

    typer.echo(f"Bot:       {name}")
    typer.echo(f"State:     {'running' if running else 'stopped'} (pid {bot.read_pid() or '-'})")
    typer.echo(f"Strategy:  {strategy_name or '-'}")
    if uptime:
        typer.echo(f"Uptime:    {uptime:.0f}s")
    if snapshot_age is not None:
        typer.echo(f"Snapshot:  {snapshot_age:.0f}s ago")
    # Surface a running-but-broken bot: process is alive but the strategy is logging errors.
    if errors["count"]:
        last = errors["messages"][-1] if errors["messages"] else ""
        typer.echo(f"Errors:    {errors['count']} in last {errors['window']} log lines — last: {last[:120]}"
                   f"\n           (run `hbot logs` for detail)")
    text = snapshot.get("format_status")
    if text:
        typer.echo("\n" + text)
