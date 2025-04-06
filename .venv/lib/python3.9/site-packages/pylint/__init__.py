# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

__all__ = [
    "__version__",
    "version",
    "modify_sys_path",
    "run_pylint",
    "run_symilar",
    "run_pyreverse",
]

import os
import sys
from collections.abc import Sequence
from typing import NoReturn

from pylint.__pkginfo__ import __version__

# pylint: disable=import-outside-toplevel


def run_pylint(argv: Sequence[str] | None = None) -> None:
    """Run pylint.

    argv can be a sequence of strings normally supplied as arguments on the command line
    """
    from pylint.lint import Run as PylintRun

    try:
        PylintRun(argv or sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)


def _run_pylint_config(argv: Sequence[str] | None = None) -> None:
    """Run pylint-config.

    argv can be a sequence of strings normally supplied as arguments on the command line
    """
    from pylint.lint.run import _PylintConfigRun

    _PylintConfigRun(argv or sys.argv[1:])


def run_pyreverse(argv: Sequence[str] | None = None) -> NoReturn:
    """Run pyreverse.

    argv can be a sequence of strings normally supplied as arguments on the command line
    """
    from pylint.pyreverse.main import Run as PyreverseRun

    PyreverseRun(argv or sys.argv[1:])


def run_symilar(argv: Sequence[str] | None = None) -> NoReturn:
    """Run symilar.

    argv can be a sequence of strings normally supplied as arguments on the command line
    """
    from pylint.checkers.symilar import Run as SymilarRun

    SymilarRun(argv or sys.argv[1:])


def modify_sys_path() -> None:
    """Modify sys path for execution as Python module.

    Strip out the current working directory from sys.path.
    Having the working directory in `sys.path` means that `pylint` might
    inadvertently import user code from modules having the same name as
    stdlib or pylint's own modules.
    CPython issue: https://bugs.python.org/issue33053

    - Remove the first entry. This will always be either "" or the working directory
    - Remove the working directory from the second and third entries
      if PYTHONPATH includes a ":" at the beginning or the end.
      https://github.com/pylint-dev/pylint/issues/3636
      Don't remove it if PYTHONPATH contains the cwd or '.' as the entry will
      only be added once.
    - Don't remove the working directory from the rest. It will be included
      if pylint is installed in an editable configuration (as the last item).
      https://github.com/pylint-dev/pylint/issues/4161
    """
    cwd = os.getcwd()
    if sys.path[0] in ("", ".", cwd):
        sys.path.pop(0)
    env_pythonpath = os.environ.get("PYTHONPATH", "")
    if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
        sys.path.pop(0)
    elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):
        sys.path.pop(1)


def _catch_valueerror(unraisable: sys.UnraisableHookArgs) -> None:  # pragma: no cover
    """Overwrite sys.unraisablehook to catch incorrect ValueError.

    Python 3.12 introduced changes that sometimes cause astroid to emit ValueErrors
    with 'generator already executing'. Fixed in Python 3.12.3 and 3.13.

    https://github.com/pylint-dev/pylint/issues/9138
    """
    if (
        isinstance(unraisable.exc_value, ValueError)
        and unraisable.exc_value.args[0] == "generator already executing"
    ):
        return

    sys.__unraisablehook__(unraisable)


if (3, 12, 0) <= sys.version_info[:3] < (3, 12, 3):
    sys.unraisablehook = _catch_valueerror


version = __version__
