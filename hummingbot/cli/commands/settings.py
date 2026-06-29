"""``hbot settings`` — view and set global client settings in conf/conf_client.yml.

  hbot settings                        list all global setting key=value pairs
  hbot settings <key>                  read one key (dotted, e.g. mqtt_bridge.mqtt_host)
  hbot settings <key> <value>          set a key (validated) and save

These are the client's global settings (rate source, log level, command timeouts, ...), distinct from
a strategy's config file (which `hbot strategy` manages). Values are validated by the same pydantic
models the interactive client uses; secret fields are masked on read. No keystore password is needed
— conf_client.yml is not encrypted. A running bot loaded its settings at start, so changes take
effect on its next start.
"""
from typing import TYPE_CHECKING, Optional

import typer

from hummingbot.cli.output import ExitCode, fail, print_json

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


def _leaf_items(cm: "ClientConfigAdapter"):
    """Traversal items that hold a value (skip section/parent nodes)."""
    from hummingbot.client.config.config_helpers import ClientConfigAdapter
    return [item for item in cm.traverse() if not isinstance(item.value, ClientConfigAdapter)]


def _item_for(cm: "ClientConfigAdapter", key: str):
    return next((item for item in cm.traverse() if item.config_path == key), None)


def _navigate(cm: "ClientConfigAdapter", key: str):
    """Return (parent_model, leaf_attr) for a dotted key."""
    parts = key.split(".")
    model = cm
    for part in parts[:-1]:
        model = getattr(model, part)
    return model, parts[-1]


def settings(
    key: Optional[str] = typer.Argument(
        None, help="Setting key (dotted, e.g. mqtt_bridge.mqtt_host). Omit to list all."),
    value: Optional[str] = typer.Argument(
        None, help="New value to set. Omit to read the key."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """View or set global client settings (conf/conf_client.yml)."""
    from hummingbot.client.config.config_helpers import (
        ClientConfigAdapter,
        load_client_config_map_from_file,
        save_to_yml,
    )
    from hummingbot.client.settings import CLIENT_CONFIG_PATH
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
        fail(f"unknown setting key '{key}' (run `hbot settings` to list)",
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
