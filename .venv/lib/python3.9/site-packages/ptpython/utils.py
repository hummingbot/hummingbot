"""
For internal use only.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable, Iterable, TypeVar, cast

from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

if TYPE_CHECKING:
    from jedi import Interpreter

    # See: prompt_toolkit/key_binding/key_bindings.py
    # Annotating these return types as `object` is what works best, because
    # `NotImplemented` is typed `Any`.
    NotImplementedOrNone = object

__all__ = [
    "has_unclosed_brackets",
    "get_jedi_script_from_document",
    "document_is_multiline_python",
    "unindent_code",
]


def has_unclosed_brackets(text: str) -> bool:
    """
    Starting at the end of the string. If we find an opening bracket
    for which we didn't had a closing one yet, return True.
    """
    stack = []

    # Ignore braces inside strings
    text = re.sub(r"""('[^']*'|"[^"]*")""", "", text)  # XXX: handle escaped quotes.!

    for c in reversed(text):
        if c in "])}":
            stack.append(c)

        elif c in "[({":
            if stack:
                if (
                    (c == "[" and stack[-1] == "]")
                    or (c == "{" and stack[-1] == "}")
                    or (c == "(" and stack[-1] == ")")
                ):
                    stack.pop()
            else:
                # Opening bracket for which we didn't had a closing one.
                return True

    return False


def get_jedi_script_from_document(
    document: Document, locals: dict[str, Any], globals: dict[str, Any]
) -> Interpreter:
    import jedi  # We keep this import in-line, to improve start-up time.

    # Importing Jedi is 'slow'.

    try:
        return jedi.Interpreter(
            document.text,
            path="input-text",
            namespaces=[locals, globals],
        )
    except ValueError:
        # Invalid cursor position.
        # ValueError('`column` parameter is not in a valid range.')
        return None
    except AttributeError:
        # Workaround for #65: https://github.com/jonathanslenders/python-prompt-toolkit/issues/65
        # See also: https://github.com/davidhalter/jedi/issues/508
        return None
    except IndexError:
        # Workaround Jedi issue #514: for https://github.com/davidhalter/jedi/issues/514
        return None
    except KeyError:
        # Workaround for a crash when the input is "u'", the start of a unicode string.
        return None
    except Exception:
        # Workaround for: https://github.com/jonathanslenders/ptpython/issues/91
        return None


_multiline_string_delims = re.compile("""[']{3}|["]{3}""")


def document_is_multiline_python(document: Document) -> bool:
    """
    Determine whether this is a multiline Python document.
    """

    def ends_in_multiline_string() -> bool:
        """
        ``True`` if we're inside a multiline string at the end of the text.
        """
        delims = _multiline_string_delims.findall(document.text)
        opening = None
        for delim in delims:
            if opening is None:
                opening = delim
            elif delim == opening:
                opening = None
        return bool(opening)

    if "\n" in document.text or ends_in_multiline_string():
        return True

    def line_ends_with_colon() -> bool:
        return document.current_line.rstrip()[-1:] == ":"

    # If we just typed a colon, or still have open brackets, always insert a real newline.
    if (
        line_ends_with_colon()
        or (
            document.is_cursor_at_the_end
            and has_unclosed_brackets(document.text_before_cursor)
        )
        or document.text.startswith("@")
    ):
        return True

    # If the character before the cursor is a backslash (line continuation
    # char), insert a new line.
    elif document.text_before_cursor[-1:] == "\\":
        return True

    return False


_T = TypeVar("_T", bound=Callable[[MouseEvent], None])


def if_mousedown(handler: _T) -> _T:
    """
    Decorator for mouse handlers.
    Only handle event when the user pressed mouse down.

    (When applied to a token list. Scroll events will bubble up and are handled
    by the Window.)
    """

    def handle_if_mouse_down(mouse_event: MouseEvent) -> NotImplementedOrNone:
        if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
            return handler(mouse_event)
        else:
            return NotImplemented

    return cast(_T, handle_if_mouse_down)


_T_type = TypeVar("_T_type", bound=type)


def ptrepr_to_repr(cls: _T_type) -> _T_type:
    """
    Generate a normal `__repr__` method for classes that have a `__pt_repr__`.
    """
    if not hasattr(cls, "__pt_repr__"):
        raise TypeError(
            "@ptrepr_to_repr can only be applied to classes that have a `__pt_repr__` method."
        )

    def __repr__(self: object) -> str:
        assert hasattr(cls, "__pt_repr__")
        return fragment_list_to_text(to_formatted_text(cls.__pt_repr__(self)))

    cls.__repr__ = __repr__  # type:ignore
    return cls


def unindent_code(text: str) -> str:
    """
    Remove common leading whitespace when all lines are indented.
    """
    lines = text.splitlines(keepends=True)

    # Look for common prefix.
    common_prefix = _common_whitespace_prefix(lines)

    # Remove indentation.
    lines = [line[len(common_prefix) :] for line in lines]

    return "".join(lines)


def _common_whitespace_prefix(strings: Iterable[str]) -> str:
    """
    Return common prefix for a list of lines.
    This will ignore lines that contain whitespace only.
    """
    # Ignore empty lines and lines that have whitespace only.
    strings = [s for s in strings if not s.isspace() and not len(s) == 0]

    if not strings:
        return ""

    else:
        s1 = min(strings)
        s2 = max(strings)

        for i, c in enumerate(s1):
            if c != s2[i] or c not in " \t":
                return s1[:i]

        return s1
