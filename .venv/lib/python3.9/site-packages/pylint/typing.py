# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""A collection of typing utilities."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from re import Pattern
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    NamedTuple,
    Optional,
    Protocol,
    TypedDict,
    Union,
)

if TYPE_CHECKING:
    from pylint.config.callback_actions import _CallbackAction
    from pylint.pyreverse.inspector import Project
    from pylint.reporters.ureports.nodes import Section
    from pylint.utils import LinterStats


class FileItem(NamedTuple):
    """Represents data about a file handled by pylint.

    Each file item has:
    - name: full name of the module
    - filepath: path of the file
    - modname: module name
    """

    name: str
    filepath: str
    modpath: str


class ModuleDescriptionDict(TypedDict):
    """Represents data about a checked module."""

    path: str
    name: str
    isarg: bool
    basepath: str
    basename: str
    isignored: bool


class ErrorDescriptionDict(TypedDict):
    """Represents data about errors collected during checking of a module."""

    key: Literal["fatal"]
    mod: str
    ex: ImportError | SyntaxError


class MessageLocationTuple(NamedTuple):
    """Tuple with information about the location of a to-be-displayed message."""

    abspath: str
    path: str
    module: str
    obj: str
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None


class ManagedMessage(NamedTuple):
    """Tuple with information about a managed message of the linter."""

    name: str | None
    msgid: str
    symbol: str
    line: int | None
    is_disabled: bool


MessageTypesFullName = Literal[
    "convention", "error", "fatal", "info", "refactor", "statement", "warning"
]
"""All possible message categories."""


OptionDict = dict[
    str,
    Union[
        None,
        str,
        bool,
        int,
        Pattern[str],
        Iterable[Union[str, int, Pattern[str]]],
        type["_CallbackAction"],
        Callable[[Any], Any],
        Callable[[Any, Any, Any, Any], Any],
    ],
]
Options = tuple[tuple[str, OptionDict], ...]


ReportsCallable = Callable[["Section", "LinterStats", Optional["LinterStats"]], None]
"""Callable to create a report."""


class ExtraMessageOptions(TypedDict, total=False):
    """All allowed keys in the extra options for message definitions."""

    scope: str
    old_names: list[tuple[str, str]]
    maxversion: tuple[int, int]
    minversion: tuple[int, int]
    shared: bool
    default_enabled: bool


MessageDefinitionTuple = Union[
    tuple[str, str, str],
    tuple[str, str, str, ExtraMessageOptions],
]
DirectoryNamespaceDict = dict[Path, tuple[argparse.Namespace, "DirectoryNamespaceDict"]]


class GetProjectCallable(Protocol):
    def __call__(
        self, module: str, name: str | None = "No Name"
    ) -> Project: ...  # pragma: no cover
