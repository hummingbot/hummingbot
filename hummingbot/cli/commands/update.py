"""``hbot update`` — live-tune a RUNNING bot's config by instance name.

  hbot update mybot                       show the bot's current config (live fields marked)
  hbot update mybot target_base_pct       read one field
  hbot update mybot target_base_pct 0.55  set it — applied live (~10s) if the field is updatable

Keyed by instance (the handle from start/status), so you never name a config file. The change is
written to the bot's resolved config file; a running controller picks updatable fields up within
~10s. Non-updatable fields (and v1/v2 scripts) are saved but need a restart to take effect.
"""
from typing import Optional

import typer

from hummingbot.cli.instances import Instance
from hummingbot.cli.output import ExitCode, fail, print_json


def update(
    instance: str = typer.Argument(..., help="Instance (bot) name."),
    key: Optional[str] = typer.Argument(None, help="Field key (dotted). Omit to show the config."),
    value: Optional[str] = typer.Argument(None, help="New value. Omit to read the field."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Read or live-update a running bot's config by instance name."""
    from hummingbot.cli.strategy_configs import config_path, edit_config, get_value, read_yaml, updatable_for
    inst = Instance(instance)
    if not inst.exists():
        fail(f"instance '{instance}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    meta = inst.read_meta() or {}
    stype, file = meta.get("type"), meta.get("file")
    if not stype or not file:
        fail(f"instance '{instance}' has no editable config on record", ExitCode.ERROR, json_output=json_output)
    path = config_path(stype, file)
    if not path.exists():
        fail(f"config file missing for '{instance}': {file}", ExitCode.ERROR, json_output=json_output)

    running = inst.is_running()
    updatable = updatable_for(stype, path)
    data = read_yaml(path)

    # SHOW
    if key is None:
        if json_output:
            print_json({"ok": True, "instance": instance, "type": stype, "file": file,
                        "running": running, "updatable_fields": sorted(updatable), "config": data})
        else:
            typer.echo(f"{instance} ({stype}: {file}, {'running' if running else 'stopped'})")
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
            print_json({"ok": True, "instance": instance, "key": key, "value": current})
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
        print_json({"ok": True, "instance": instance, "key": key, "value": new_value,
                    "running": running, "applied_live": running and is_live_field, "note": note})
    else:
        typer.echo(f"{key} = {new_value}  ({note})")
