"""``hbot import`` — load an existing config file as the bot's current strategy.

Mirrors the interactive client's ``import``: it starts nothing. It makes ``<file>`` the config that
``hbot start`` runs when given no argument, and that ``hbot config`` shows/edits. The file's type
(``v1-strategy`` / ``v2-script`` / ``controller``) is auto-detected from the conf folder holding it;
a ``--v1-strategy`` / ``--v2-script`` / ``--controller`` flag is only needed for a legacy name that
exists under more than one folder. The file is validated (it must parse; a controller must build) so
a broken config fails here, not later at ``start``.
"""
import typer

from hummingbot.cli import bot
from hummingbot.cli.commands._common import one_type
from hummingbot.cli.output import ExitCode, echo, fail, render_kv


def import_config(
    file: str = typer.Argument(..., help="Config file name in conf/strategies|scripts|controllers."),
    v1: bool = typer.Option(False, "--v1-strategy", help="Force V1 strategy type (only if the name collides across types)."),
    v2: bool = typer.Option(False, "--v2-script", help="Force V2 script type (only if the name collides across types)."),
    controller: bool = typer.Option(
        False, "--controller", help="Force controller type (only if the name collides across types)."),
) -> None:
    """Load an existing config file as the current strategy (for `start` / `config`)."""
    from hummingbot.cli.strategy_configs import config_path, read_yaml, resolve_config_type, validate_controller
    try:
        stype = resolve_config_type(file, one_type(v1, v2, controller, required=False))
    except FileNotFoundError as e:
        fail(str(e), ExitCode.NOT_FOUND)
    except ValueError as e:
        fail(str(e), ExitCode.CONFIG_ERROR)

    path = config_path(stype, file)
    try:
        data = read_yaml(path)
        if stype == "controller":
            validate_controller(path)  # instantiate the pydantic config so a broken controller fails now
    except Exception as e:
        fail(f"invalid config {file}: {e}", ExitCode.CONFIG_ERROR)

    bot.write_loaded(file, stype)
    strategy = data.get("strategy") or data.get("controller_name") or data.get("script_file_name") or ""
    echo(render_kv({"file": file, "type": stype, "strategy": strategy, "next": "hbot start"},
                   title=f"imported {file}"))
