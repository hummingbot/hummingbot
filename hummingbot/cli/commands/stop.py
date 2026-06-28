"""``hbot stop`` — gracefully stop a running bot (cancels open orders)."""
import os
import signal
import time

import typer

from hummingbot.cli.instances import Instance, pid_alive
from hummingbot.cli.output import ExitCode, fail, print_json


def stop(
    name: str = typer.Argument(..., help="Instance id to stop."),
    timeout: float = typer.Option(30.0, "--timeout", help="Seconds to wait for graceful shutdown."),
    force: bool = typer.Option(False, "--force", help="SIGKILL if still alive after timeout."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Send SIGTERM so the bot winds down and cancels orders, then wait for exit."""
    instance = Instance(name)
    if not instance.exists():
        fail(f"instance '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    pid = instance.read_pid()
    if pid is None or not pid_alive(pid):
        instance.clear_pid()
        fail(f"instance '{name}' is not running", ExitCode.NOT_RUNNING, json_output=json_output)

    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pid):
            break
        time.sleep(0.5)

    killed = False
    if pid_alive(pid):
        if force:
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            killed = True
        else:
            fail(f"'{name}' did not stop within {timeout:g}s (use --force to SIGKILL)",
                 ExitCode.TIMEOUT, json_output=json_output)

    instance.clear_pid()
    result = {"ok": True, "name": name, "stopped": True, "killed": killed}
    if json_output:
        print_json(result)
    else:
        typer.echo(f"Stopped '{name}'." + (" (force-killed)" if killed else ""))
