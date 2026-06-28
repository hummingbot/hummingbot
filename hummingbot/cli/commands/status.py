"""``hbot status`` — report one bot's live state, or list all instances."""
import os
import signal
import time
from typing import Any, Dict, List, Optional

import typer

from hummingbot.cli.instances import Instance, list_instances, pid_alive
from hummingbot.cli.output import ExitCode, fail, print_json

# How long `hbot status` waits for the engine to write a fresh snapshot after SIGUSR1.
REFRESH_TIMEOUT = 5.0


def _request_fresh_snapshot(instance: Instance, timeout: float = REFRESH_TIMEOUT) -> None:
    """Ask the running engine (via SIGUSR1) to write a current snapshot, and wait for it."""
    pid = instance.read_pid()
    if pid is None or not pid_alive(pid):
        return
    prev = (instance.read_status() or {}).get("updated_at", 0)
    try:
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (instance.read_status() or {}).get("updated_at", 0) > prev:
            return
        time.sleep(0.1)


def _instance_summary(instance: Instance) -> Dict[str, Any]:
    running = instance.is_running()
    status = instance.read_status() or {}
    engine = status.get("engine") or {}
    meta = instance.read_meta() or {}
    started_at = meta.get("started_at")
    snapshot_age = (time.time() - status["updated_at"]) if status.get("updated_at") else None
    return {
        "name": instance.name,
        "running": running,
        "pid": instance.read_pid(),
        "strategy_name": engine.get("strategy_name") or meta.get("strategy_name"),
        "uptime_seconds": (time.time() - started_at) if (running and started_at) else None,
        "snapshot_age_seconds": snapshot_age,
    }


def status(
    name: Optional[str] = typer.Argument(None, help="Instance id. Omit to list all instances."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show a bot's status snapshot, or list every instance when no name is given."""
    if name is None:
        instances: List[Instance] = list_instances()
        summaries = [_instance_summary(i) for i in instances]
        if json_output:
            print_json({"ok": True, "instances": summaries})
            return
        if not summaries:
            typer.echo("No instances found.")
            return
        header = f"{'NAME':<24} {'STATE':<9} {'PID':<8} {'STRATEGY':<24} UPTIME"
        typer.echo(header)
        for s in summaries:
            up = f"{s['uptime_seconds']:.0f}s" if s["uptime_seconds"] else "-"
            state = "running" if s["running"] else "stopped"
            typer.echo(f"{s['name']:<24} {state:<9} {str(s['pid'] or '-'):<8} "
                       f"{str(s['strategy_name'] or '-'):<24} {up}")
        return

    instance = Instance(name)
    if not instance.exists():
        fail(f"instance '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    # Trigger a fresh, on-demand snapshot from the running engine before reading it.
    _request_fresh_snapshot(instance)
    summary = _instance_summary(instance)
    snapshot = instance.read_status() or {}
    if json_output:
        print_json({"ok": True, **summary,
                    "engine": snapshot.get("engine"),
                    "balances": snapshot.get("balances"),
                    "format_status": snapshot.get("format_status")})
        return

    state = "running" if summary["running"] else "stopped"
    typer.echo(f"Instance:  {summary['name']}")
    typer.echo(f"State:     {state} (pid {summary['pid'] or '-'})")
    typer.echo(f"Strategy:  {summary['strategy_name'] or '-'}")
    if summary["uptime_seconds"]:
        typer.echo(f"Uptime:    {summary['uptime_seconds']:.0f}s")
    if summary["snapshot_age_seconds"] is not None:
        typer.echo(f"Snapshot:  {summary['snapshot_age_seconds']:.0f}s ago")
    text = snapshot.get("format_status")
    if text:
        typer.echo("\n" + text)
