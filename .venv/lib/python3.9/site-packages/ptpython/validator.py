from __future__ import annotations

from typing import Callable

from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError, Validator

from .utils import unindent_code

__all__ = ["PythonValidator"]


class PythonValidator(Validator):
    """
    Validation of Python input.

    :param get_compiler_flags: Callable that returns the currently
        active compiler flags.
    """

    def __init__(self, get_compiler_flags: Callable[[], int] | None = None) -> None:
        self.get_compiler_flags = get_compiler_flags

    def validate(self, document: Document) -> None:
        """
        Check input for Python syntax errors.
        """
        text = unindent_code(document.text)

        # When the input starts with Ctrl-Z, always accept. This means EOF in a
        # Python REPL.
        if text.startswith("\x1a"):
            return

        # When the input starts with an exclamation mark. Accept as shell
        # command.
        if text.lstrip().startswith("!"):
            return

        try:
            if self.get_compiler_flags:
                flags = self.get_compiler_flags()
            else:
                flags = 0

            compile(text, "<input>", "exec", flags=flags, dont_inherit=True)
        except SyntaxError as e:
            # Note, the 'or 1' for offset is required because Python 2.7
            # gives `None` as offset in case of '4=4' as input. (Looks like
            # fixed in Python 3.)
            # TODO: This is not correct if indentation was removed.
            index = document.translate_row_col_to_index(
                (e.lineno or 1) - 1, (e.offset or 1) - 1
            )
            raise ValidationError(index, f"Syntax Error: {e}")
        except TypeError as e:
            # e.g. "compile() expected string without null bytes"
            raise ValidationError(0, str(e))
        except ValueError as e:
            # In Python 2, compiling "\x9" (an invalid escape sequence) raises
            # ValueError instead of SyntaxError.
            raise ValidationError(0, f"Syntax Error: {e}")
