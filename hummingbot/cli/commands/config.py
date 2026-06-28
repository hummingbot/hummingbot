"""``hbot config`` — view and set global client configs in conf/conf_client.yml.

  hbot config                          list all global config key=value pairs
  hbot config <key>                    read one key (dotted, e.g. mqtt_bridge.mqtt_host)
  hbot config <key> <value>            set a key (validated) and save

Values are validated by the same pydantic models the interactive client uses; secret fields are
masked on read. No keystore password is needed — conf_client.yml is not encrypted. A running bot
loaded its config at start, so changes take effect on its next start.
"""
from typing import Optional

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.client.config.config_helpers import ClientConfigAdapter, load_client_config_map_from_file, save_to_yml
from hummingbot.client.settings import CLIENT_CONFIG_PATH


def _leaf_items(cm: ClientConfigAdapter):
    """Traversal items that hold a value (skip section/parent nodes)."""
    return [item for item in cm.traverse() if not isinstance(item.value, ClientConfigAdapter)]


def _item_for(cm: ClientConfigAdapter, key: str):
    return next((item for item in cm.traverse() if item.config_path == key), None)


def _navigate(cm: ClientConfigAdapter, key: str):
    """Return (parent_model, leaf_attr) for a dotted key."""
    parts = key.split(".")
    model = cm
    for part in parts[:-1]:
        model = getattr(model, part)
    return model, parts[-1]


def config(
    key: Optional[str] = typer.Argument(
        None, help="Config key (dotted, e.g. mqtt_bridge.mqtt_host). Omit to list all."),
    value: Optional[str] = typer.Argument(
        None, help="New value to set. Omit to read the key."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """View or set global client configs (conf/conf_client.yml)."""
    cm = load_client_config_map_from_file()

    if key is None:
        data = {item.config_path: item.printable_value for item in _leaf_items(cm)}
        if json_output:
            print_json({"ok": True, "config": data})
        else:
            for k, v in data.items():
                typer.echo(f"{k} = {v}")
        return

    if key not in set(cm.config_paths()):
        fail(f"unknown config key '{key}' (run `hbot config` to list)",
             ExitCode.CONFIG_ERROR, json_output=json_output)

    model, leaf = _navigate(cm, key)
    if isinstance(getattr(model, leaf), ClientConfigAdapter):
        fail(f"'{key}' is a section, not a value; specify a sub-key",
             ExitCode.CONFIG_ERROR, json_output=json_output)

    if value is None:
        item = _item_for(cm, key)
        if json_output:
            print_json({"ok": True, "key": key, "value": item.printable_value})
        else:
            typer.echo(f"{key} = {item.printable_value}")
        return

    try:
        setattr(model, leaf, value)
    except Exception as e:
        fail(f"invalid value for {key}: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
    save_to_yml(CLIENT_CONFIG_PATH, cm)

    item = _item_for(cm, key)
    if json_output:
        print_json({"ok": True, "key": key, "value": item.printable_value})
    else:
        typer.echo(f"{key} = {item.printable_value}")
