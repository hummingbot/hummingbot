"""
Helpers for retrieving the function signature of the function call that we are
editing.

Either with the Jedi library, or using `inspect.signature` if Jedi fails and we
can use `eval()` to evaluate the function object.
"""

from __future__ import annotations

import inspect
from inspect import Signature as InspectSignature
from inspect import _ParameterKind as ParameterKind
from typing import TYPE_CHECKING, Any, Sequence

from prompt_toolkit.document import Document

from .completer import DictionaryCompleter
from .utils import get_jedi_script_from_document

if TYPE_CHECKING:
    import jedi.api.classes

__all__ = ["Signature", "get_signatures_using_jedi", "get_signatures_using_eval"]


class Parameter:
    def __init__(
        self,
        name: str,
        annotation: str | None,
        default: str | None,
        kind: ParameterKind,
    ) -> None:
        self.name = name
        self.kind = kind

        self.annotation = annotation
        self.default = default

    def __repr__(self) -> str:
        return f"Parameter(name={self.name!r})"

    @property
    def description(self) -> str:
        """
        Name + annotation.
        """
        description = self.name

        if self.annotation is not None:
            description += f": {self.annotation}"

        return description


class Signature:
    """
    Signature definition used wrap around both Jedi signatures and
    python-inspect signatures.

    :param index: Parameter index of the current cursor position.
    :param bracket_start: (line, column) tuple for the open bracket that starts
        the function call.
    """

    def __init__(
        self,
        name: str,
        docstring: str,
        parameters: Sequence[Parameter],
        index: int | None = None,
        returns: str = "",
        bracket_start: tuple[int, int] = (0, 0),
    ) -> None:
        self.name = name
        self.docstring = docstring
        self.parameters = parameters
        self.index = index
        self.returns = returns
        self.bracket_start = bracket_start

    @classmethod
    def from_inspect_signature(
        cls,
        name: str,
        docstring: str,
        signature: InspectSignature,
        index: int,
    ) -> Signature:
        parameters = []

        def get_annotation_name(annotation: object) -> str:
            """
            Get annotation as string from inspect signature.
            """
            try:
                # In case the annotation is a class like "int", "float", ...
                return str(annotation.__name__)  # type: ignore
            except AttributeError:
                pass  # No attribute `__name__`, e.g., in case of `List[int]`.

            annotation = str(annotation)
            if annotation.startswith("typing."):
                annotation = annotation[len("typing:") :]
            return annotation

        for p in signature.parameters.values():
            parameters.append(
                Parameter(
                    name=p.name,
                    annotation=get_annotation_name(p.annotation),
                    default=repr(p.default)
                    if p.default is not inspect.Parameter.empty
                    else None,
                    kind=p.kind,
                )
            )

        return cls(
            name=name,
            docstring=docstring,
            parameters=parameters,
            index=index,
            returns="",
        )

    @classmethod
    def from_jedi_signature(cls, signature: jedi.api.classes.Signature) -> Signature:
        parameters = []

        for p in signature.params:
            if p is None:
                # We just hit the "*".
                continue

            parameters.append(
                Parameter(
                    name=p.to_string(),  # p.name, (`to_string()` already includes the annotation).
                    annotation=None,  # p.infer_annotation()
                    default=None,  # p.infer_default()
                    kind=p.kind,
                )
            )

        docstring = signature.docstring()
        if not isinstance(docstring, str):
            docstring = docstring.decode("utf-8")

        return cls(
            name=signature.name,
            docstring=docstring,
            parameters=parameters,
            index=signature.index,
            returns="",
            bracket_start=signature.bracket_start,
        )

    def __repr__(self) -> str:
        return f"Signature({self.name!r}, parameters={self.parameters!r})"


def get_signatures_using_jedi(
    document: Document, locals: dict[str, Any], globals: dict[str, Any]
) -> list[Signature]:
    script = get_jedi_script_from_document(document, locals, globals)

    # Show signatures in help text.
    if not script:
        return []

    try:
        signatures = script.get_signatures()
    except ValueError:
        # e.g. in case of an invalid \\x escape.
        signatures = []
    except Exception:
        # Sometimes we still get an exception (TypeError), because
        # of probably bugs in jedi. We can silence them.
        # See: https://github.com/davidhalter/jedi/issues/492
        signatures = []
    else:
        # Try to access the params attribute just once. For Jedi
        # signatures containing the keyword-only argument star,
        # this will crash when retrieving it the first time with
        # AttributeError. Every following time it works.
        # See: https://github.com/jonathanslenders/ptpython/issues/47
        #      https://github.com/davidhalter/jedi/issues/598
        try:
            if signatures:
                signatures[0].params
        except AttributeError:
            pass

    return [Signature.from_jedi_signature(sig) for sig in signatures]


def get_signatures_using_eval(
    document: Document, locals: dict[str, Any], globals: dict[str, Any]
) -> list[Signature]:
    """
    Look for the signature of the function before the cursor position without
    use of Jedi. This uses a similar approach as the `DictionaryCompleter` of
    running `eval()` over the detected function name.
    """
    # Look for open parenthesis, before cursor position.
    pos = document.cursor_position - 1

    paren_mapping = {")": "(", "}": "{", "]": "["}
    paren_stack = [
        ")"
    ]  # Start stack with closing ')'. We are going to look for the matching open ')'.
    comma_count = 0  # Number of comma's between start of function call and cursor pos.
    found_start = False  # Found something.

    while pos >= 0:
        char = document.text[pos]
        if char in ")]}":
            paren_stack.append(char)
        elif char in "([{":
            if not paren_stack:
                # Open paren, while no closing paren was found. Mouse cursor is
                # positioned in nested parentheses. Not at the "top-level" of a
                # function call.
                break
            if paren_mapping[paren_stack[-1]] != char:
                # Unmatching parentheses: syntax error?
                break

            paren_stack.pop()

            if len(paren_stack) == 0:
                found_start = True
                break

        elif char == "," and len(paren_stack) == 1:
            comma_count += 1

        pos -= 1

    if not found_start:
        return []

    # We found the start of the function call. Now look for the object before
    # this position on which we can do an 'eval' to retrieve the function
    # object.
    obj = DictionaryCompleter(lambda: globals, lambda: locals).eval_expression(
        Document(document.text, cursor_position=pos), locals
    )
    if obj is None:
        return []

    try:
        name = obj.__name__  # type:ignore
    except Exception:
        name = obj.__class__.__name__

    try:
        signature = inspect.signature(obj)  # type: ignore
    except TypeError:
        return []  # Not a callable object.
    except ValueError:
        return []  # No signature found, like for build-ins like "print".

    try:
        doc = obj.__doc__ or ""
    except:
        doc = ""

    # TODO: `index` is not yet correct when dealing with keyword-only arguments.
    return [Signature.from_inspect_signature(name, doc, signature, index=comma_count)]
