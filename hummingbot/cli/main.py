"""``hbot`` CLI entrypoint — run, control, and monitor Hummingbot bots.

Designed to be driven non-interactively by agentic harnesses: every command emits compact Markdown
and returns a stable exit code (see ``hummingbot.cli.output.ExitCode``); the run/observe commands
(deploy/start/stop/status/logs/config/balance) also take ``--json`` for machine-readable output.
One bot per install (like Hummingbot itself); for multiple bots, use multiple installs/containers.
"""
import os  # noqa: E402 — HBOT_PREFIX must apply before settings imports
from pathlib import Path
from typing import Optional

import typer

# HBOT_PREFIX (4a): a second instance is a second prefix — instance state
# (conf/, data/, logs/, data/bot/) resolves under it; code stays with the
# install. Applied here, before anything can snapshot a settings path.
_env_prefix = os.environ.get("HBOT_PREFIX")
if _env_prefix:
    import hummingbot

    hummingbot.set_prefix_path(os.path.realpath(_env_prefix))

from hummingbot.cli.commands import (  # noqa: E402
    backtest as backtest_cmd,
    balance as balance_cmd,
    config as config_cmd,
    connect as connect_cmd,
    create as create_cmd,
    deploy as deploy_cmd,
    doctor as doctor_cmd,
    history as history_cmd,
    import_cmd,
    logs as logs_cmd,
    start as start_cmd,
    status as status_cmd,
    stop as stop_cmd,
    trades as trades_cmd,
    update as update_cmd,
)
from hummingbot.cli.output import SortedCommandsGroup  # noqa: E402

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


def _apply_prefix(prefix: str) -> None:
    """Point this process (and every child it spawns) at an instance prefix,
    scaffolding the per-instance conf layout on first use."""
    import hummingbot

    real = os.path.realpath(prefix)
    os.environ["HBOT_PREFIX"] = real  # the detached engine inherits it
    hummingbot.set_prefix_path(real)
    if real != str(hummingbot.root_path()):
        for sub in ("conf/strategies", "conf/scripts", "conf/controllers",
                    "conf/connectors", "logs", "data"):
            Path(real, sub).mkdir(parents=True, exist_ok=True)


@app.callback(invoke_without_command=True)
def _root(
    version: Optional[bool] = typer.Option(
        None, "--version", help="Show the hbot/Hummingbot version and exit.", is_eager=True),
    prefix: Optional[str] = typer.Option(
        None, "--prefix",
        help="Instance directory for conf/, data/ and logs/ (default: the install root; "
             "equivalent to HBOT_PREFIX). Lets a paper-smoke instance run beside the live bot.",
        envvar="HBOT_PREFIX", show_envvar=True),
) -> None:
    if prefix:
        _apply_prefix(prefix)
    if version:
        typer.echo(f"hbot {_version()}")
        raise typer.Exit()


# v1 surface — a faithful subset of the interactive client's commands (minus gateway), plus one
# composite: `deploy` (= create/import + start in one call, the primitive agents reach for). Order
# here is irrelevant; --help lists them alphabetically (SortedCommandsGroup).
app.command("connect")(connect_cmd.connect)
app.command("balance")(balance_cmd.balance)
app.command("create")(create_cmd.create)
app.command("import")(import_cmd.import_config)
# ignore_unknown_options: config values can legitimately start with '-' (negative spreads/pcts);
# without it `hbot config <key> -1` dies at the parser with "No such option: -1". Known options
# (--json, -h) still parse; anything else option-shaped falls through to the VALUE argument.
app.command("config", context_settings={"ignore_unknown_options": True})(config_cmd.config)
app.command("deploy")(deploy_cmd.deploy)
app.command("start")(start_cmd.start)
app.command("stop")(stop_cmd.stop)
app.command("status")(status_cmd.status)
app.command("logs")(logs_cmd.logs)
app.command("history")(history_cmd.history)
app.command("trades")(trades_cmd.trades)
app.command("backtest")(backtest_cmd.backtest)
app.command("update")(update_cmd.update)
app.command("doctor")(doctor_cmd.doctor)


def main() -> None:
    """Console-script entrypoint (``hbot``)."""
    app()


if __name__ == "__main__":
    main()
