"""Shared helpers for the three trading-config kinds the CLI speaks.

    v1-strategy  conf/strategies/*.yml    full V1 strategy configs
    v2-script    conf/scripts/*.yml       V2 script configs (may reference controllers)
    controller   conf/controllers/*.yml   V2 controller configs (live-updatable while running)

Used by both `hbot start` (to run) and `hbot strategy` (to inspect/edit). Editing preserves
comments/formatting via ruamel round-trip. Only controllers can be validated against a real
pydantic config class and expose `is_updatable` fields (the only kind applied live by a running
bot, via the 10s controller-config poll in StrategyV2Base).
"""
import importlib
import inspect
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml
from ruamel.yaml import YAML

from hummingbot import prefix_path
from hummingbot.client.settings import (
    CONTROLLERS_CONF_DIR_PATH,
    CONTROLLERS_MODULE,
    SCRIPT_STRATEGY_CONF_DIR_PATH,
    STRATEGIES_CONF_DIR_PATH,
)

# Type ids match the folder vocabulary: v1-strategy (hummingbot/strategy + conf/strategies),
# v2-script (scripts + conf/scripts), controller (controllers + conf/controllers).
STRATEGY_TYPES = ("v1-strategy", "v2-script", "controller")

TYPE_DIRS = {
    "v1-strategy": STRATEGIES_CONF_DIR_PATH,
    "v2-script": SCRIPT_STRATEGY_CONF_DIR_PATH,
    "controller": CONTROLLERS_CONF_DIR_PATH,
}

V2_CONTROLLER_RUNNER = "v2_with_controllers.py"


def list_configs(stype: str) -> List[str]:
    directory = TYPE_DIRS[stype]
    if not directory.exists():
        return []
    return sorted(f.name for f in directory.iterdir() if f.suffix == ".yml")


def config_path(stype: str, filename: str) -> Path:
    return TYPE_DIRS[stype] / filename


def matching_config_types(filename: str) -> List[str]:
    """Types whose CONFIG dir (conf/strategies | conf/scripts | conf/controllers) holds ``filename``."""
    return [t for t in STRATEGY_TYPES if config_path(t, filename).exists()]


def matching_strategy_types(name: str) -> List[str]:
    """Types whose SOURCE catalog contains ``name`` — v1 strategy folder, scripts/<name>.py, or
    controllers/<type>/<name>.py. (v2 scripts carry a .py suffix, so match it with or without.)"""
    out = []
    for t in STRATEGY_TYPES:
        sources = available_sources(t)
        if name in sources or (t == "v2-script" and f"{name}.py" in sources):
            out.append(t)
    return out


def resolve_config_type(filename: str, explicit: Optional[str] = None) -> str:
    """Resolve which type a config FILE is — the single lookup shared by every filename-taking command
    (start/set/show-config/clone/update).

    With ``explicit`` (a type id from a flag), verify the file exists in that type's dir. Otherwise
    detect it from the conf dirs: config names are unique across types, so a bare filename is enough.
    Raises FileNotFoundError if the file is absent, or ValueError if it exists under multiple types
    (a legacy collision) and an explicit type is needed.
    """
    if explicit is not None:
        if not config_path(explicit, filename).exists():
            raise FileNotFoundError(f"{explicit} config not found: {filename}")
        return explicit
    matches = matching_config_types(filename)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"config not found: {filename}")
    raise ValueError(f"'{filename}' exists as {' and '.join(matches)} — pass "
                     f"{' / '.join('--' + m for m in matches)} to disambiguate")


def available_controllers() -> List[str]:
    """Controller module names that can be scaffolded (controllers/<type>/<name>.py)."""
    base = Path(prefix_path()) / CONTROLLERS_MODULE
    if not base.exists():
        return []
    return sorted({f.stem for type_dir in base.iterdir() if type_dir.is_dir() and not type_dir.name.startswith("__")
                   for f in type_dir.glob("*.py") if not f.name.startswith("__")})


def available_scripts() -> List[str]:
    """V2 script files (scripts/*.py)."""
    base = Path(prefix_path()) / "scripts"
    if not base.exists():
        return []
    return sorted(f.name for f in base.glob("*.py") if not f.name.startswith("__"))


def available_v1_strategies() -> List[str]:
    """List v1 strategies (the strategy folders). Fast — a directory scan, no config-map imports."""
    from hummingbot import get_strategy_list
    return sorted(get_strategy_list())


def available_sources(stype: str) -> List[str]:
    return {"v1-strategy": available_v1_strategies,
            "v2-script": available_scripts,
            "controller": available_controllers}[stype]()


def describe_strategy(stype: str, source: str, scaffold_id: bool = True) -> Tuple[dict, List[str], Set[str]]:
    """Return (template fields, required field names, live-updatable field names) for a creatable
    strategy/controller/script — used by both `strategy show` (preview) and `strategy create`.

    `scaffold_id` controls the controller `id` field: when creating a file we mint a real id, but
    when previewing with `show` we leave a placeholder so we don't display a meaningless throwaway.
    """
    from hummingbot.client.config.config_helpers import get_strategy_config_map, get_strategy_pydantic_config_cls

    if stype == "controller":
        from hummingbot.strategy_v2.utils.common import generate_unique_id
        config_class, ctype = resolve_controller_class_by_name(source)
        data, required = template_config_data(config_class, {"controller_name": source, "controller_type": ctype})
        # A controller needs a STABLE, persisted id. If left blank, StrategyV2Base generates a fresh
        # ephemeral id every start AND the ~10s live-reload (update_controllers_configs) fails to match
        # the running controller by id, so it spawns a duplicate controller each cycle. `create` mints
        # one now; `show` only previews, so it shows a placeholder instead of a meaningless value.
        data["id"] = generate_unique_id() if scaffold_id else "<auto-generated on create>"
        required = [r for r in required if r != "id"]
        return data, required, controller_updatable_fields(config_class)
    if stype == "v2-script":
        script_file = source if source.endswith(".py") else f"{source}.py"
        config_class = resolve_script_config_class(script_file)
        data, required = template_config_data(config_class, {"script_file_name": script_file})
        return data, required, set()
    # v1
    config_class = get_strategy_pydantic_config_cls(source)
    if config_class is not None:
        data, required = template_config_data(config_class, {})
    else:
        config_map = get_strategy_config_map(source)
        if not config_map:
            raise ValueError(f"unknown v1 strategy '{source}'")
        data, required = template_legacy_data(config_map)
    return data, required, set()


def controller_config_class(config_data: dict):
    """Resolve the pydantic config class for a controller yaml (mirrors load_controller_configs)."""
    from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase
    from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
        DirectionalTradingControllerConfigBase,
    )
    from hummingbot.strategy_v2.controllers.market_making_controller_base import MarketMakingControllerConfigBase

    ctype = config_data.get("controller_type")
    cname = config_data.get("controller_name")
    if not ctype or not cname:
        raise ValueError("controller config is missing controller_type or controller_name")
    module = importlib.import_module(f"{CONTROLLERS_MODULE}.{ctype}.{cname}")
    bases = (ControllerConfigBase, MarketMakingControllerConfigBase, DirectionalTradingControllerConfigBase)
    cls = next((m for _, m in inspect.getmembers(module)
                if inspect.isclass(m) and m not in bases and issubclass(m, ControllerConfigBase)), None)
    if cls is None:
        raise ValueError(f"no controller config class found in module for '{cname}'")
    return cls


def controller_updatable_fields(config_class) -> Set[str]:
    return {name for name, field in config_class.model_fields.items()
            if (field.json_schema_extra or {}).get("is_updatable", False)}


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _coerce(existing: Any, value: str) -> Any:
    """Coerce a string value to match an existing value's type (Decimals stay strings in yaml)."""
    if isinstance(existing, bool):
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        raise ValueError(f"expected a boolean, got '{value}'")
    if isinstance(existing, int) and not isinstance(existing, bool):
        return int(value)
    if isinstance(existing, float):
        return float(value)
    return value


def get_value(data: dict, key: str) -> Any:
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(key)
        node = node[part]
    return node


def set_value_preserving_comments(path: Path, key: str, value: str) -> Any:
    """Round-trip edit ``path`` setting ``key`` (dotted) to a coerced ``value``; returns the new value."""
    ruamel = YAML()
    ruamel.preserve_quotes = True
    with open(path) as f:
        data = ruamel.load(f)
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        node = node[part]
    leaf = parts[-1]
    if leaf not in node:
        raise KeyError(key)
    new_value = _coerce(node[leaf], value)
    node[leaf] = new_value
    with open(path, "w") as f:
        ruamel.dump(data, f)
    return new_value


def validate_controller(path: Path) -> Tuple[object, Set[str]]:
    """Instantiate the controller config class to validate the file; return (config, updatable fields)."""
    data = read_yaml(path)
    config_class = controller_config_class(data)
    config = config_class(**data)
    return config, controller_updatable_fields(config_class)


def updatable_for(stype: str, path: Path) -> Set[str]:
    """Fields that a running bot applies live. Only controllers have any."""
    if stype != "controller":
        return set()
    try:
        _, updatable = validate_controller(path)
        return updatable
    except Exception:
        return set()


def edit_config(path: Path, stype: str, key: str, value: str) -> Tuple[Any, Set[str]]:
    """Set ``key=value`` in ``path`` (comment-preserving), validating controllers and rolling back
    on failure. Returns (new_value, updatable_fields). Raises KeyError for a missing key, or another
    exception (with the file restored) if the value is rejected.
    """
    original = path.read_text()
    try:
        new_value = set_value_preserving_comments(path, key, value)
    except KeyError:
        raise
    except Exception:
        path.write_text(original)
        raise
    updatable: Set[str] = set()
    if stype == "controller":
        try:
            _, updatable = validate_controller(path)
        except Exception:
            path.write_text(original)
            raise
    return new_value, updatable


def resolve_controller_class_by_name(controller_name: str):
    """Find a controller's config class + its type by module name (e.g. 'lp_jit')."""
    import controllers

    base = Path(controllers.__file__).parent
    for type_dir in sorted(base.iterdir()):
        if type_dir.is_dir() and (type_dir / f"{controller_name}.py").exists():
            ctype = type_dir.name
            cls = controller_config_class({"controller_type": ctype, "controller_name": controller_name})
            return cls, ctype
    raise ValueError(f"controller '{controller_name}' not found under {CONTROLLERS_MODULE}/")


def resolve_script_config_class(script_filename: str):
    """Find the config class defined inside a V2 script (e.g. simple_pmm.py -> SimplePMMConfig)."""
    from hummingbot.client.config.config_data_types import BaseClientModel

    mod_name = script_filename[:-3] if script_filename.endswith(".py") else script_filename
    module = importlib.import_module(f"scripts.{mod_name}")
    candidates = [m for _, m in inspect.getmembers(module)
                  if inspect.isclass(m) and issubclass(m, BaseClientModel)
                  and m is not BaseClientModel and m.__module__ == module.__name__]
    if not candidates:
        raise ValueError(f"no config class found in script '{script_filename}'")
    return candidates[0]


def _yaml_safe(value: Any) -> Any:
    from decimal import Decimal
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "model_dump"):  # nested pydantic model
        return _yaml_safe(value.model_dump())
    if isinstance(value, (list, tuple)):
        return [_yaml_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _yaml_safe(v) for k, v in value.items()}
    if hasattr(value, "value"):  # enums
        return value.value
    return str(value)  # last-resort: never let yaml.safe_dump choke


def template_config_data(config_class, fixed: dict) -> Tuple[dict, List[str]]:
    """Build a template config dict from a pydantic config class.

    Fields with defaults get them; required fields (no default) get None and are returned in the
    `required` list so the caller can tell the user what to fill. `fixed` overrides identity fields
    (controller_name/type or script_file_name).
    """
    from pydantic_core import PydanticUndefined

    data: dict = {}
    required: List[str] = []
    for name, field in config_class.model_fields.items():
        if field.default is not PydanticUndefined:
            data[name] = _yaml_safe(field.default)
        elif field.default_factory is not None:
            data[name] = _yaml_safe(field.default_factory())
        else:
            data[name] = None
            required.append(name)
    data.update(fixed)
    return data, [r for r in required if r not in fixed]


def _safe_attr(obj: Any, name: str) -> Any:
    """Read an attribute, tolerating ConfigVar properties (e.g. `required`) that evaluate
    `required_if` lambdas referencing other still-unset values and raise on access."""
    try:
        value = getattr(obj, name)
    except Exception:
        return None
    if callable(value):
        try:
            return value()
        except Exception:
            return None
    return value


def template_legacy_data(config_map: dict) -> Tuple[dict, List[str]]:
    """Build a template from a legacy ConfigVar map (strategies without a pydantic config)."""
    data: dict = {}
    required: List[str] = []
    for key, cvar in config_map.items():
        default = _safe_attr(cvar, "default")
        data[key] = _yaml_safe(default)
        if _safe_attr(cvar, "required") and default is None:
            required.append(key)
    return data, required


def create_config_file(stype: str, out_name: str, data: dict) -> Path:
    path = config_path(stype, out_name)
    if path.exists():
        raise FileExistsError(f"{stype} config already exists: {out_name}")
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    return path


def normalize_config_name(name: str) -> str:
    """A config filename always ends in .yml (accept 'conf_x' or 'conf_x.yml')."""
    return name if name.endswith(".yml") else f"{name}.yml"


def suggest_free_name(desired: str) -> str:
    """Return a config filename based on ``desired`` that exists in NO type dir (names are unique
    across v1-strategy/v2-script/controller so a config never needs a type flag to identify it)."""
    desired = normalize_config_name(desired)
    if not matching_config_types(desired):
        return desired
    base = re.sub(r"_\d+$", "", Path(desired).stem)  # strip a trailing _<n> before re-numbering
    n = 2
    while matching_config_types(f"{base}_{n}.yml"):
        n += 1
    return f"{base}_{n}.yml"


def parse_set_pairs(pairs: List[str]) -> Dict[str, str]:
    """Parse ``--set key=value`` strings into a {key: value} dict (string values)."""
    out: Dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"invalid --set '{p}', expected key=value")
        key, value = p.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --set '{p}', empty key")
        out[key] = value
    return out


def _set_in_template(data: dict, key: str, value: Any) -> None:
    """Set a dotted ``key`` in a scaffold dict, raising ValueError if the field doesn't exist. String
    values (from --set) are coerced to the placeholder's type; JSON values (from stdin) go in as-is."""
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"unknown field '{key}'")
        node = node[part]
    leaf = parts[-1]
    if not isinstance(node, dict) or leaf not in node:
        raise ValueError(f"unknown field '{key}'")
    node[leaf] = _coerce(node[leaf], value) if isinstance(value, str) else _yaml_safe(value)


def fill_template(data: dict, required: List[str], stype: str, values: Dict[str, Any]) -> List[str]:
    """Apply ``values`` into a scaffold ``data`` in place, then return the still-unfilled required
    fields. Validates each field exists and, once a controller has every required field, validates the
    whole pydantic model so a complete-but-invalid combination fails at create time. Raises ValueError.
    """
    for key, value in values.items():
        _set_in_template(data, key, value)
    remaining = [r for r in required if data.get(r) is None]
    if stype == "controller" and not remaining:
        config_class = controller_config_class(data)
        config_class(**data)  # full validation; raises on an invalid value/combination
    return remaining


def regenerate_controller_id(path: Path) -> str:
    """Give a controller config a fresh unique id (comment-preserving). A clone MUST get a new id:
    two controllers sharing an id break StrategyV2Base's live-reload matching and spawn a duplicate."""
    from hummingbot.strategy_v2.utils.common import generate_unique_id
    ruamel = YAML()
    ruamel.preserve_quotes = True
    with open(path) as f:
        data = ruamel.load(f)
    new_id = generate_unique_id()
    data["id"] = new_id
    with open(path, "w") as f:
        ruamel.dump(data, f)
    return new_id


def clone_config(stype: str, src_name: str, dest_name: str, values: Dict[str, Any]) -> Optional[str]:
    """Copy an existing config (comments/formatting preserved) to ``dest_name``, mint a fresh id for a
    controller, then apply ``values`` (validated for controllers). Atomic: any failure removes the copy.
    Returns the controller's new id (or None). Raises FileExistsError/FileNotFoundError/KeyError/ValueError.
    """
    src = config_path(stype, src_name)
    dest = config_path(stype, dest_name)
    if not src.exists():
        raise FileNotFoundError(f"{stype} config not found: {src_name}")
    if dest.exists():
        raise FileExistsError(f"{stype} config already exists: {dest_name}")
    shutil.copyfile(src, dest)
    try:
        new_id = regenerate_controller_id(dest) if stype == "controller" else None
        for key, value in values.items():
            edit_config(dest, stype, key, value)  # comment-preserving + controller validation
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return new_id


def controller_loader_name(controller_filename: str) -> str:
    """Loader-config filename for a controller — also the DB/log name once running.

    A controller can't run standalone, so we run it through a generated v2 'loader' script config; that
    config's name is what Hummingbot uses for the trades DB and structured log. Hummingbot derives the
    DB name via ``name.split('.')[0]`` (it means to strip the extension but truncates at the FIRST dot),
    so a dotted controller name like ``conf_generic.lp_jit.hype_usdc`` would collide on ``conf_generic``.
    We flatten dots to underscores so the loader (and thus DB/log) is named after the whole controller.
    """
    return Path(controller_filename).stem.replace(".", "_") + ".yml"


def wrap_controller_as_v2(controller_filename: str) -> str:
    """Create a v2 loader script config that runs the controllers runner with this controller.

    Returns the generated loader config filename (in conf/scripts/); its stem is the bot's DB/log name.
    """
    loader = controller_loader_name(controller_filename)
    content = {
        "script_file_name": V2_CONTROLLER_RUNNER,
        "controllers_config": [controller_filename],
        "max_global_drawdown_quote": None,
        "max_controller_drawdown_quote": None,
    }
    with open(config_path("v2-script", loader), "w") as f:
        yaml.safe_dump(content, f, default_flow_style=False, sort_keys=False)
    return loader
