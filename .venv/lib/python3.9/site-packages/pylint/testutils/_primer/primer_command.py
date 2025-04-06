# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import abc
import argparse
from pathlib import Path
from typing import TypedDict

from pylint.reporters.json_reporter import OldJsonExport
from pylint.testutils._primer import PackageToLint


class PackageData(TypedDict):
    commit: str
    messages: list[OldJsonExport]


PackageMessages = dict[str, PackageData]


class PrimerCommand:
    """Generic primer action with required arguments."""

    def __init__(
        self,
        primer_directory: Path,
        packages: dict[str, PackageToLint],
        config: argparse.Namespace,
    ) -> None:
        self.primer_directory = primer_directory
        self.packages = packages
        self.config = config

    @abc.abstractmethod
    def run(self) -> None:
        pass
