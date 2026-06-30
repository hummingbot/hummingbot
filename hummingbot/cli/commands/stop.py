"""``hbot stop`` — gracefully stop the running bot (cancels open orders)."""
import os
import signal
import time

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, echo, fail, render_kv


def stop(
    timeout: float = typer.Option(30.0, "--timeout", help="Seconds to wait for graceful shutdown."),
    force: bool = typer.Option(False, "--force", help="SIGKILL if still alive after timeout."),
) -> None:
    """Stop the bot gracefully, cancelling its open orders."""
    if not bot.exists():
        fail("no bot has been started", ExitCode.NOT_FOUND)

    pid = bot.read_pid()
    if pid is None or not bot.pid_alive(pid):
        bot.clear_pid()
        fail("the bot is not running", ExitCode.NOT_RUNNING)

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
                 ExitCode.TIMEOUT)

    bot.clear_pid()
    echo(render_kv({"stopped": True, "killed": killed}, title="stop"))
