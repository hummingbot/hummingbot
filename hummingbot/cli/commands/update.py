"""``hbot update`` — live-tune the running bot's config.

  hbot update                       show the bot's current config (live fields marked)
  hbot update target_base_pct       read one field
  hbot update target_base_pct 0.55  set it — applied live (~10s) if the field is updatable

The change is written to the bot's resolved config file; a running controller picks updatable fields
up within ~10s. Non-updatable fields (and v1/v2 scripts) are saved but need a restart to take effect.
"""
from typing import Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, fail, print_json


def update(
    key: Optional[str] = typer.Argument(None, help="Field key (dotted). Omit to show the config."),
    value: Optional[str] = typer.Argument(None, help="New value. Omit to read the field."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """View or change the running bot's config, live."""
    from hummingbot.cli.strategy_configs import config_path, edit_config, get_value, read_yaml, updatable_for
    if not bot.exists():
        fail("no bot has been started", ExitCode.NOT_FOUND, json_output=json_output)

    meta = bot.read_meta() or {}
    stype, file = meta.get("type"), meta.get("file")
    if not stype or not file:
        fail("the bot has no editable config on record", ExitCode.ERROR, json_output=json_output)
    path = config_path(stype, file)
    if not path.exists():
        fail(f"config file missing: {file}", ExitCode.ERROR, json_output=json_output)

    running = bot.running()
    updatable = updatable_for(stype, path)
    data = read_yaml(path)

    # SHOW
    if key is None:
        if json_output:
            print_json({"ok": True, "type": stype, "file": file,
                        "running": running, "updatable_fields": sorted(updatable), "config": data})
        else:
            typer.echo(f"{file} ({stype}, {'running' if running else 'stopped'})")
            for k, val in data.items():
                typer.echo(f"  {k} = {val}{'  (live)' if k in updatable else ''}")
        return

    # GET
    if value is None:
        try:
            current = get_value(data, key)
        except KeyError:
            fail(f"key '{key}' not found in {file}", ExitCode.CONFIG_ERROR, json_output=json_output)
        if json_output:
            print_json({"ok": True, "key": key, "value": current})
        else:
            typer.echo(f"{key} = {current}")
        return

    # SET
    try:
        new_value, updatable = edit_config(path, stype, key, value)
    except KeyError:
        fail(f"key '{key}' not found in {file}", ExitCode.CONFIG_ERROR, json_output=json_output)
    except Exception as e:
        fail(f"value rejected: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)

    is_live_field = key.split(".")[0] in updatable
    if running and is_live_field:
        note = "applied live (~10s)"
    elif running and not is_live_field:
        note = "saved; bot is running but this field is not live — restart to apply"
    else:
        note = "saved; applies on next start"

    if json_output:
        print_json({"ok": True, "key": key, "value": new_value,
                    "running": running, "applied_live": running and is_live_field, "note": note})
    else:
        typer.echo(f"{key} = {new_value}  ({note})")
