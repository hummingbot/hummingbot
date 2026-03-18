import importlib
import importlib.util
import sys
from os import listdir
from os.path import isfile, join
from pathlib import Path
from typing import List, Optional

from hummingbot.client.settings import SCRIPT_STRATEGIES_MODULE


def get_script_file_path(name: str, builtin_path: Path, external_path: Optional[Path] = None) -> Optional[Path]:
    """Resolve a script name to its .py file path.

    Uses ONLY external directory when set, ONLY built-in when unset.
    """
    if external_path is not None:
        ext_file = external_path / f"{name}.py"
        return ext_file if ext_file.is_file() else None

    builtin_file = builtin_path / f"{name}.py"
    return builtin_file if builtin_file.is_file() else None


def load_script_module(name: str, builtin_path: Path, external_path: Optional[Path] = None):
    """Load (or reload) a script module by name.

    When ``external_path`` is set, loads ONLY from there via
    ``spec_from_file_location``.  When unset, uses ONLY built-in
    ``importlib.import_module``.
    """
    if external_path is not None:
        ext_dir = str(external_path)
        if ext_dir not in sys.path:
            sys.path.insert(0, ext_dir)
        try:
            module_key = name
            existing = sys.modules.get(module_key)
            if existing is not None:
                return importlib.reload(existing)
            return importlib.import_module(name)
        finally:
            if ext_dir in sys.path:
                sys.path.remove(ext_dir)
    else:
        module_key = f"{SCRIPT_STRATEGIES_MODULE}.{name}"
        existing = sys.modules.get(module_key)
        if existing is not None:
            return importlib.reload(existing)
        return importlib.import_module(f".{name}", package=SCRIPT_STRATEGIES_MODULE)


def list_script_names(builtin_path: Path, external_path: Optional[Path] = None) -> List[str]:
    """List .py script names from the active directory.

    Uses ONLY external directory when set, ONLY built-in when unset.
    """
    target = external_path if external_path is not None else builtin_path

    if not target.is_dir():
        return []

    return sorted(
        f[:-3]
        for f in listdir(str(target))
        if isfile(join(str(target), f)) and f.endswith(".py") and not f.startswith("__")
    )
