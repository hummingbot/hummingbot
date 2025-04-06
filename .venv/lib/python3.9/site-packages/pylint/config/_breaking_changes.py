# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""List the breaking changes in configuration files and their solutions."""

from __future__ import annotations

import enum
from typing import NamedTuple


class BreakingChange(enum.Enum):
    MESSAGE_MADE_DISABLED_BY_DEFAULT = "{symbol} ({msgid}) was disabled by default"
    MESSAGE_MADE_ENABLED_BY_DEFAULT = "{symbol} ({msgid}) was enabled by default"
    MESSAGE_MOVED_TO_EXTENSION = "{symbol} ({msgid}) was moved to {extension}"
    EXTENSION_REMOVED = "{extension} was removed"
    # This kind of upgrade is non-breaking but if we want to automatically upgrade it,
    # then we should use the message store and old_names values instead of duplicating
    # MESSAGE_RENAMED= "{symbol} ({msgid}) was renamed"


class Condition(enum.Enum):
    MESSAGE_IS_ENABLED = "{symbol} ({msgid}) is enabled"
    MESSAGE_IS_NOT_ENABLED = "{symbol} ({msgid}) is not enabled"
    MESSAGE_IS_DISABLED = "{symbol} ({msgid}) is disabled"
    MESSAGE_IS_NOT_DISABLED = "{symbol} ({msgid}) is not disabled"
    EXTENSION_IS_LOADED = "{extension} is loaded"
    EXTENSION_IS_NOT_LOADED = "{extension} is not loaded"


class Information(NamedTuple):
    msgid_or_symbol: str
    extension: str | None


class Solution(enum.Enum):
    ADD_EXTENSION = "Add {extension} in 'load-plugins' option"
    REMOVE_EXTENSION = "Remove {extension} from the 'load-plugins' option"
    ENABLE_MESSAGE_EXPLICITLY = (
        "{symbol} ({msgid}) should be added in the 'enable' option"
    )
    ENABLE_MESSAGE_IMPLICITLY = (
        "{symbol} ({msgid}) should be removed from the 'disable' option"
    )
    DISABLE_MESSAGE_EXPLICITLY = (
        "{symbol} ({msgid}) should be added in the 'disable' option"
    )
    DISABLE_MESSAGE_IMPLICITLY = (
        "{symbol} ({msgid}) should be removed from the 'enable' option"
    )


ConditionsToBeAffected = list[Condition]
# A solution to a breaking change might imply multiple actions
MultipleActionSolution = list[Solution]
# Sometimes there's multiple solutions and the user needs to choose
Solutions = list[MultipleActionSolution]
BreakingChangeWithSolution = tuple[
    BreakingChange, Information, ConditionsToBeAffected, Solutions
]

NO_SELF_USE = Information(
    msgid_or_symbol="no-self-use", extension="pylint.extensions.no_self_use"
)
COMPARE_TO_ZERO = Information(
    msgid_or_symbol="compare-to-zero", extension="pylint.extensions.comparetozero"
)
COMPARE_TO_EMPTY_STRING = Information(
    msgid_or_symbol="compare-to-empty-string",
    extension="pylint.extensions.emptystring",
)

CONFIGURATION_BREAKING_CHANGES: dict[str, list[BreakingChangeWithSolution]] = {
    "2.14.0": [
        (
            BreakingChange.MESSAGE_MOVED_TO_EXTENSION,
            NO_SELF_USE,
            [Condition.MESSAGE_IS_ENABLED, Condition.EXTENSION_IS_NOT_LOADED],
            [[Solution.ADD_EXTENSION], [Solution.DISABLE_MESSAGE_IMPLICITLY]],
        ),
    ],
    "3.0.0": [
        (
            BreakingChange.EXTENSION_REMOVED,
            COMPARE_TO_ZERO,
            [Condition.MESSAGE_IS_NOT_DISABLED, Condition.EXTENSION_IS_LOADED],
            [[Solution.REMOVE_EXTENSION, Solution.ENABLE_MESSAGE_EXPLICITLY]],
        ),
        (
            BreakingChange.EXTENSION_REMOVED,
            COMPARE_TO_EMPTY_STRING,
            [Condition.MESSAGE_IS_NOT_DISABLED, Condition.EXTENSION_IS_LOADED],
            [[Solution.REMOVE_EXTENSION, Solution.ENABLE_MESSAGE_EXPLICITLY]],
        ),
    ],
}
