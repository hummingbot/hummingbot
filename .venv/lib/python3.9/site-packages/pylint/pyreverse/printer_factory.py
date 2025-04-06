# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from pylint.pyreverse.dot_printer import DotPrinter
from pylint.pyreverse.mermaidjs_printer import HTMLMermaidJSPrinter, MermaidJSPrinter
from pylint.pyreverse.plantuml_printer import PlantUmlPrinter
from pylint.pyreverse.printer import Printer

filetype_to_printer: dict[str, type[Printer]] = {
    "plantuml": PlantUmlPrinter,
    "puml": PlantUmlPrinter,
    "mmd": MermaidJSPrinter,
    "html": HTMLMermaidJSPrinter,
    "dot": DotPrinter,
}


def get_printer_for_filetype(filetype: str) -> type[Printer]:
    return filetype_to_printer.get(filetype, DotPrinter)
