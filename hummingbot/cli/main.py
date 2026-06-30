"""``hbot`` CLI entrypoint — run, control, and monitor Hummingbot bots.

Designed to be driven non-interactively by agentic harnesses: every command supports ``--json``
and returns a stable exit code (see ``hummingbot.cli.output.ExitCode``). One bot per install
(like Hummingbot itself); for multiple bots, use multiple installs/containers.
"""
from pathlib import Path
from typing import Optional

import typer

from hummingbot.cli.commands import (
    balance as balance_cmd,
    connect as connect_cmd,
    connectors as connectors_cmd,
    history as history_cmd,
    logs as logs_cmd,
    order_book as order_book_cmd,
    positions as positions_cmd,
    rules as rules_cmd,
    settings as settings_cmd,
    start as start_cmd,
    status as status_cmd,
    stop as stop_cmd,
    strategy as strategy_cmd,
    ticker as ticker_cmd,
    trades as trades_cmd,
    update as update_cmd,
)
from hummingbot.cli.output import SortedCommandsGroup

app = typer.Typer(
    name="hbot",
    cls=SortedCommandsGroup,
    no_args_is_help=True,
    add_completion=False,
    help="Run, control, and monitor a Hummingbot bot (one bot per install).",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version() -> str:
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return version_file.read_text().strip()
    except OSError:
        return "unknown"


@app.callback(invoke_without_command=True)
def _root(
    version: Optional[bool] = typer.Option(
        None, "--version", help="Show the hbot/Hummingbot version and exit.", is_eager=True),
) -> None:
    if version:
        typer.echo(f"hbot {_version()}")
        raise typer.Exit()


app.command("connect")(connect_cmd.connect)
app.command("connectors")(connectors_cmd.connectors)
app.command("balance")(balance_cmd.balance)
app.command("rules")(rules_cmd.rules)
app.command("ticker")(ticker_cmd.ticker)
app.command("book")(order_book_cmd.order_book)
app.command("positions")(positions_cmd.positions)
app.command("settings")(settings_cmd.settings)
app.add_typer(strategy_cmd.strategy_app, name="strategy")
app.command("update")(update_cmd.update)
app.command("start")(start_cmd.start)
app.command("stop")(stop_cmd.stop)
app.command("status")(status_cmd.status)
app.command("logs")(logs_cmd.logs)
app.command("history")(history_cmd.history)
app.command("trades")(trades_cmd.trades)


def main() -> None:
    """Console-script entrypoint (``hbot``)."""
    app()


if __name__ == "__main__":
    main()
