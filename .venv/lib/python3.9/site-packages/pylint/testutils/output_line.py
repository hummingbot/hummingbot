# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NamedTuple, TypeVar

from astroid import nodes

from pylint.interfaces import UNDEFINED, Confidence
from pylint.message.message import Message

_T = TypeVar("_T")


class MessageTest(NamedTuple):
    msg_id: str
    line: int | None = None
    node: nodes.NodeNG | None = None
    args: Any | None = None
    confidence: Confidence | None = UNDEFINED
    col_offset: int | None = None
    end_line: int | None = None
    end_col_offset: int | None = None
    """Used to test messages produced by pylint.

    Class name cannot start with Test as pytest doesn't allow constructors in test classes.
    """


class OutputLine(NamedTuple):
    symbol: str
    lineno: int
    column: int
    end_lineno: int | None
    end_column: int | None
    object: str
    msg: str
    confidence: str

    @classmethod
    def from_msg(cls, msg: Message, check_endline: bool = True) -> OutputLine:
        """Create an OutputLine from a Pylint Message."""
        column = cls._get_column(msg.column)
        end_line = cls._get_end_line_and_end_col(msg.end_line, check_endline)
        end_column = cls._get_end_line_and_end_col(msg.end_column, check_endline)
        return cls(
            msg.symbol,
            msg.line,
            column,
            end_line,
            end_column,
            msg.obj or "",
            msg.msg.replace("\r\n", "\n"),
            msg.confidence.name,
        )

    @staticmethod
    def _get_column(column: str | int) -> int:
        """Handle column numbers."""
        return int(column)

    @staticmethod
    def _get_end_line_and_end_col(value: _T, check_endline: bool) -> _T | None:
        """Used to make end_line and end_column None as indicated by our version
        compared to `min_pyver_end_position`.
        """
        if not check_endline:
            return None  # pragma: no cover
        return value

    @classmethod
    def from_csv(
        cls, row: Sequence[str] | str, check_endline: bool = True
    ) -> OutputLine:
        """Create an OutputLine from a comma separated list (the functional tests
        expected output .txt files).
        """
        if isinstance(row, str):
            row = row.split(",")
        try:
            line = int(row[1])
            column = cls._get_column(row[2])
            end_line = cls._value_to_optional_int(
                cls._get_end_line_and_end_col(row[3], check_endline)
            )
            end_column = cls._value_to_optional_int(
                cls._get_end_line_and_end_col(row[4], check_endline)
            )
            # symbol, line, column, end_line, end_column, node, msg, confidences
            assert len(row) == 8
            return cls(
                row[0], line, column, end_line, end_column, row[5], row[6], row[7]
            )
        except Exception:  # pylint: disable=broad-except
            # We need this to not fail for the update script to work.
            return cls("", 0, 0, None, None, "", "", "")

    def to_csv(self) -> tuple[str, str, str, str, str, str, str, str]:
        """Convert an OutputLine to a tuple of string to be written by a
        csv-writer.
        """
        return (
            str(self.symbol),
            str(self.lineno),
            str(self.column),
            str(self.end_lineno),
            str(self.end_column),
            str(self.object),
            str(self.msg),
            str(self.confidence),
        )

    @staticmethod
    def _value_to_optional_int(value: str | None) -> int | None:
        """Checks if a (stringified) value should be None or a Python integer."""
        if value == "None" or not value:
            return None
        return int(value)
