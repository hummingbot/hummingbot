"""``hbot config`` — view and edit configuration.

  hbot config                     list global client settings (+ the loaded strategy's config)
  hbot config <key>               read one key (a global setting, or a loaded-strategy field)
  hbot config <key> <value>       set a key (global -> conf/conf_client.yml; strategy -> its config file)

Two scopes, one command — matching the interactive client's ``config``:

* **Global** client settings (rate source, log level, command timeouts, …) live in
  ``conf/conf_client.yml``. They are not encrypted, so no keystore password is needed. Global keys are
  dotted, e.g. ``mqtt_bridge.mqtt_host``.
* **Strategy** config — shown/edited only when a strategy is *loaded*: the config a running bot is
  using, or (when nothing is running) the one selected by ``hbot import`` / the last ``hbot start``.
  A running controller applies live-updatable fields within ~10s; other fields (and v1/v2 scripts)
  take effect on the next start.

A bare ``hbot config`` shows global only when nothing is loaded, and global + strategy when one is.
Global keys take precedence: a key that names a global setting is always read/written globally.
"""
from typing import TYPE_CHECKING, Optional, Tuple

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, cell, emit, fail, json_option, render_kv, render_table

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


def _active_strategy() -> Optional[Tuple[str, str, bool]]:
    """The strategy config ``config`` should show/edit — ``(file, type, running)`` — or None.

    A running bot's own config wins (so ``config`` reflects the live bot); otherwise the config
    ``hbot import`` / the last ``hbot start`` loaded. When neither exists, only global settings show.
    """
    if bot.running():
        meta = bot.read_meta() or {}
        if meta.get("file") and meta.get("type"):
            return meta["file"], meta["type"], True
    loaded = bot.read_loaded()
    if loaded and loaded.get("file") and loaded.get("type"):
        return loaded["file"], loaded["type"], False
    return None


def _list(cm: "ClientConfigAdapter", active: Optional[Tuple[str, str, bool]], as_json: bool) -> None:
    rows = [{"key": item.config_path, "value": item.printable_value} for item in _leaf_items(cm)]
    out = render_table(rows, columns=["key", "value"], title="global settings")
    payload: dict = {"global": {r["key"]: r["value"] for r in rows}, "strategy": None}
    if active is not None:
        file, stype, running = active
        from hummingbot.cli.strategy_configs import config_path, read_yaml, updatable_for
        path = config_path(stype, file)
        data = read_yaml(path)
        updatable = updatable_for(stype, path)
        srows = [{"field": k, "value": cell(val), "live": k in updatable} for k, val in data.items()]
        state = "running" if running else "loaded"
        out += "\n\n" + render_table(
            srows, columns=["field", "value", "live"],
            title=f"strategy config — {file} ({stype}, {state})")
        payload["strategy"] = {"file": file, "type": stype, "state": state,
                               "fields": data, "live_fields": sorted(updatable)}
    emit(payload, out, as_json)


def _read_or_set_global(cm: "ClientConfigAdapter", key: str, value: Optional[str], as_json: bool) -> None:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter, save_to_yml
    from hummingbot.client.settings import CLIENT_CONFIG_PATH
    model, leaf = _navigate(cm, key)
    if isinstance(getattr(model, leaf), ClientConfigAdapter):
        fail(f"'{key}' is a section, not a value; specify a sub-key", ExitCode.CONFIG_ERROR)
    if value is not None:
        try:
            setattr(model, leaf, value)
        except Exception as e:
            fail(f"invalid value for {key}: {e}", ExitCode.CONFIG_ERROR)
        save_to_yml(CLIENT_CONFIG_PATH, cm)
    item = _item_for(cm, key)
    record = {"key": key, "value": item.printable_value, "scope": "global"}
    emit(record, render_kv(record, title="config"), as_json)


def _read_or_set_strategy(active: Tuple[str, str, bool], key: str, value: Optional[str], as_json: bool) -> None:
    from hummingbot.cli.strategy_configs import config_path, edit_config, get_value, read_yaml
    file, stype, running = active
    path = config_path(stype, file)
    data = read_yaml(path)
    try:
        current = get_value(data, key)
    except KeyError:
        fail(f"unknown config key '{key}' — not a global setting nor a field of {file} "
             f"(run `hbot config` to list)", ExitCode.CONFIG_ERROR)

    if value is None:
        record = {"key": key, "value": current if as_json else cell(current), "scope": f"{stype}:{file}"}
        emit(record, render_kv(record, title="config"), as_json)
        return

    try:
        new_value, updatable = edit_config(path, stype, key, value)
    except KeyError:
        fail(f"key '{key}' not found in {file}", ExitCode.CONFIG_ERROR)
    except Exception as e:
        fail(f"value rejected: {e}", ExitCode.CONFIG_ERROR)

    record = {"key": key, "value": new_value, "scope": f"{stype}:{file}"}
    if running:
        live = stype == "controller" and key in updatable
        record["applies"] = "live (~10s)" if live else "on next start"
    emit(record, render_kv(record, title=f"set {file}"), as_json)


def config(
    key: Optional[str] = typer.Argument(
        None, help="Config key: a global setting (dotted, e.g. mqtt_bridge.mqtt_host) or a loaded-strategy field. Omit to list."),
    value: Optional[str] = typer.Argument(
        None, help="New value to set. Omit to read the key."),
    as_json: bool = json_option(),
) -> None:
    """View or set configuration — global client settings, plus the loaded strategy's config."""
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    cm = load_client_config_map_from_file()
    active = _active_strategy()

    if key is None:
        _list(cm, active, as_json)
        return

    # Global keys are the priority namespace: a key that names a global setting is always global.
    if key in set(cm.config_paths()):
        _read_or_set_global(cm, key, value, as_json)
        return

    if active is None:
        fail(f"unknown config key '{key}' — not a global setting, and no strategy is loaded "
             f"(run `hbot import <file>` to load one, or `hbot config` to list settings)",
             ExitCode.CONFIG_ERROR)
    _read_or_set_strategy(active, key, value, as_json)
