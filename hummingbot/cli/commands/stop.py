"""``hbot stop`` — gracefully stop the running bot (cancels open orders)."""
import os
import signal
import time

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, fail, print_json


def stop(
    timeout: float = typer.Option(30.0, "--timeout", help="Seconds to wait for graceful shutdown."),
    force: bool = typer.Option(False, "--force", help="SIGKILL if still alive after timeout."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Send SIGTERM so the bot winds down and cancels orders, then wait for exit."""
    if not bot.exists():
        fail("no bot has been started", ExitCode.NOT_FOUND, json_output=json_output)

    pid = bot.read_pid()
    if pid is None or not bot.pid_alive(pid):
        bot.clear_pid()
        fail("the bot is not running", ExitCode.NOT_RUNNING, json_output=json_output)

    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not bot.pid_alive(pid):
            break
        time.sleep(0.5)

    killed = False
    if bot.pid_alive(pid):
        if force:
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            killed = True
        else:
            fail(f"the bot did not stop within {timeout:g}s (use --force to SIGKILL)",
                 ExitCode.TIMEOUT, json_output=json_output)

    bot.clear_pid()
    if json_output:
        print_json({"ok": True, "stopped": True, "killed": killed})
    else:
        typer.echo("Stopped the bot." + (" (force-killed)" if killed else ""))
