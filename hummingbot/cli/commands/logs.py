"""``hbot logs`` — tail the bot's log (one bot per install)."""
import json
import time
from pathlib import Path
from typing import Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, fail


def _resolve_log_file(name: Optional[str], json_output: bool) -> Optional[Path]:
    if name:
        log = bot.structured_log_for(name)
        if log is None:
            fail(f"no log found for '{name}' (available: {', '.join(bot.list_bots()) or 'none'})",
                 ExitCode.NOT_FOUND, json_output=json_output)
        return log
    if not bot.exists():
        fail("no bot has been started (pass a name to view a past bot)",
             ExitCode.NOT_FOUND, json_output=json_output)
    if bot.structured_log_file().exists():
        return bot.structured_log_file()
    if bot.log_file().exists():
        return bot.log_file()
    return None


def logs(
    name: Optional[str] = typer.Argument(None, help="Bot name to view (a past/stopped bot). Omit for the current bot."),
    lines: int = typer.Option(200, "--lines", "-n", help="Number of trailing lines to show."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream new lines until interrupted (Ctrl-C)."),
    json_output: bool = typer.Option(
        False, "--json", help="JSON: a {lines:[...]} object for a snapshot, or NDJSON (one record/line) with -f."),
) -> None:
    """Show the bot's recent log output (-f to follow live).

    With no name, shows the current bot; pass a name (from `hbot start`) to view a past/stopped bot.
    Note for agents: ``-f`` runs until interrupted — bound it (e.g. a timeout) rather than awaiting forever.
    """
    log_file = _resolve_log_file(name, json_output)
    if log_file is None:
        fail("no log file yet", ExitCode.ERROR, json_output=json_output)

    tail = bot.tail_lines(log_file, lines)

    # Snapshot (no --follow): emit one JSON object (parseable in a single read), or plain text.
    if not follow:
        if json_output:
            typer.echo(json.dumps({"ok": True, "source": str(log_file), "lines": tail}, default=str))
        else:
            for line in tail:
                typer.echo(line)
        return

    # Follow: stream. JSON mode emits NDJSON (one compact record per line) so it stays parseable.
    def emit(line: str) -> None:
        line = line.rstrip("\n")
        typer.echo(json.dumps({"line": line}) if json_output else line)

    for line in tail:
        emit(line)
    with open(log_file, "r", errors="replace") as f:
        f.seek(0, 2)  # end of file
        try:
            while True:
                line = f.readline()
                if line:
                    emit(line)
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            return
