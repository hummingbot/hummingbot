# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""Arguments provider class used to expose options."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pylint.config.arguments_manager import _ArgumentsManager
from pylint.typing import OptionDict, Options


class _ArgumentsProvider:
    """Base class for classes that provide arguments."""

    name: str
    """Name of the provider."""

    options: Options = ()
    """Options provided by this provider."""

    option_groups_descs: dict[str, str] = {}
    """Option groups of this provider and their descriptions."""

    def __init__(self, arguments_manager: _ArgumentsManager) -> None:
        self._arguments_manager = arguments_manager
        """The manager that will parse and register any options provided."""

        self._arguments_manager._register_options_provider(self)

    def _option_value(self, opt: str) -> Any:
        """Get the current value for the given option."""
        return getattr(self._arguments_manager.config, opt.replace("-", "_"), None)

    def _options_by_section(
        self,
    ) -> Iterator[
        tuple[str, list[tuple[str, OptionDict, Any]]]
        | tuple[None, dict[str, list[tuple[str, OptionDict, Any]]]]
    ]:
        """Return an iterator on options grouped by section.

        (section, [list of (optname, optdict, optvalue)])
        """
        sections: dict[str, list[tuple[str, OptionDict, Any]]] = {}
        for optname, optdict in self.options:
            sections.setdefault(optdict.get("group"), []).append(  # type: ignore[arg-type]
                (optname, optdict, self._option_value(optname))
            )
        if None in sections:
            yield None, sections.pop(None)  # type: ignore[call-overload]
        for section, options in sorted(sections.items()):
            yield section.upper(), options

    def _options_and_values(
        self, options: Options | None = None
    ) -> Iterator[tuple[str, OptionDict, Any]]:
        """DEPRECATED."""
        if options is None:
            options = self.options
        for optname, optdict in options:
            yield optname, optdict, self._option_value(optname)
