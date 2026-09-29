"""``hbot logs`` — tail the bot's log (one bot per install)."""
import time
from pathlib import Path
from typing import Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, echo, emit, fail, json_option


def _resolve_log_file(name: Optional[str]) -> Optional[Path]:
    if name:
        log = bot.structured_log_for(name)
        if log is None:
            fail(f"no log found for '{name}' (available: {', '.join(bot.list_bots()) or 'none'})",
                 ExitCode.NOT_FOUND)
        return log
    if not bot.exists():
        fail("no bot has been started (pass a name to view a past bot)",
             ExitCode.NOT_FOUND)
    if bot.structured_log_file().exists():
        return bot.structured_log_file()
    if bot.log_file().exists():
        return bot.log_file()
    return None


def logs(
    name: Optional[str] = typer.Argument(None, help="Bot name to view (a past/stopped bot). Omit for the current bot."),
    lines: int = typer.Option(200, "--lines", "-n", help="Number of trailing lines to show."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream new lines until interrupted (Ctrl-C)."),
    as_json: bool = json_option(),
) -> None:
    """Show the bot's recent log output (-f to follow live).

    With no name, shows the current bot; pass a name (from `hbot start`) to view a past/stopped bot.
    Note for agents: ``-f`` runs until interrupted — bound it (e.g. a timeout) rather than awaiting forever.
    """
    if as_json and follow:
        fail("--json is a snapshot format; it cannot be combined with --follow", ExitCode.CONFIG_ERROR)

    log_file = _resolve_log_file(name)
    if log_file is None:
        fail("no log file yet", ExitCode.ERROR)

    tail = bot.tail_lines(log_file, lines)

    # Snapshot (no --follow): print the trailing lines as-is.
    if not follow:
        if as_json:
            emit({"file": str(log_file), "lines": tail}, "", True)
        else:
            for line in tail:
                echo(line)
        return

    # Follow: stream new lines as they're written, as-is, until interrupted.
    def emit_line(line: str) -> None:
        echo(line.rstrip("\n"))

    for line in tail:
        emit_line(line)
    with open(log_file, "r", errors="replace") as f:
        f.seek(0, 2)  # end of file
        try:
            while True:
                line = f.readline()
                if line:
                    emit_line(line)
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            return
