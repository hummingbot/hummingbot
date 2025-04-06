from __future__ import annotations

import ast
import collections.abc as collections_abc
import inspect
import keyword
import re
from enum import Enum
from itertools import islice
from typing import TYPE_CHECKING, Any, Callable, Iterable

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)
from prompt_toolkit.contrib.completers.system import SystemCompleter
from prompt_toolkit.contrib.regular_languages.compiler import compile as compile_grammar
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import fragment_list_to_text, to_formatted_text

from ptpython.utils import get_jedi_script_from_document

if TYPE_CHECKING:
    import jedi.api.classes
    from prompt_toolkit.contrib.regular_languages.compiler import _CompiledGrammar

__all__ = ["PythonCompleter", "CompletePrivateAttributes", "HidePrivateCompleter"]


class CompletePrivateAttributes(Enum):
    """
    Should we display private attributes in the completion pop-up?
    """

    NEVER = "NEVER"
    IF_NO_PUBLIC = "IF_NO_PUBLIC"
    ALWAYS = "ALWAYS"


class PythonCompleter(Completer):
    """
    Completer for Python code.
    """

    def __init__(
        self,
        get_globals: Callable[[], dict[str, Any]],
        get_locals: Callable[[], dict[str, Any]],
        enable_dictionary_completion: Callable[[], bool],
    ) -> None:
        super().__init__()

        self.get_globals = get_globals
        self.get_locals = get_locals
        self.enable_dictionary_completion = enable_dictionary_completion

        self._system_completer = SystemCompleter()
        self._jedi_completer = JediCompleter(get_globals, get_locals)
        self._dictionary_completer = DictionaryCompleter(get_globals, get_locals)

        self._path_completer_cache: GrammarCompleter | None = None
        self._path_completer_grammar_cache: _CompiledGrammar | None = None

    @property
    def _path_completer(self) -> GrammarCompleter:
        if self._path_completer_cache is None:
            self._path_completer_cache = GrammarCompleter(
                self._path_completer_grammar,
                {
                    "var1": PathCompleter(expanduser=True),
                    "var2": PathCompleter(expanduser=True),
                },
            )
        return self._path_completer_cache

    @property
    def _path_completer_grammar(self) -> _CompiledGrammar:
        """
        Return the grammar for matching paths inside strings inside Python
        code.
        """
        # We make this lazy, because it delays startup time a little bit.
        # This way, the grammar is build during the first completion.
        if self._path_completer_grammar_cache is None:
            self._path_completer_grammar_cache = self._create_path_completer_grammar()
        return self._path_completer_grammar_cache

    def _create_path_completer_grammar(self) -> _CompiledGrammar:
        def unwrapper(text: str) -> str:
            return re.sub(r"\\(.)", r"\1", text)

        def single_quoted_wrapper(text: str) -> str:
            return text.replace("\\", "\\\\").replace("'", "\\'")

        def double_quoted_wrapper(text: str) -> str:
            return text.replace("\\", "\\\\").replace('"', '\\"')

        grammar = r"""
                # Text before the current string.
                (
                    [^'"#]                                  |  # Not quoted characters.
                    '''  ([^'\\]|'(?!')|''(?!')|\\.])*  ''' |  # Inside single quoted triple strings
                    "" " ([^"\\]|"(?!")|""(?!^)|\\.])* "" " |  # Inside double quoted triple strings

                    \#[^\n]*(\n|$)           |  # Comment.
                    "(?!"") ([^"\\]|\\.)*"   |  # Inside double quoted strings.
                    '(?!'') ([^'\\]|\\.)*'      # Inside single quoted strings.

                        # Warning: The negative lookahead in the above two
                        #          statements is important. If we drop that,
                        #          then the regex will try to interpret every
                        #          triple quoted string also as a single quoted
                        #          string, making this exponentially expensive to
                        #          execute!
                )*
                # The current string that we're completing.
                (
                    ' (?P<var1>([^\n'\\]|\\.)*) |  # Inside a single quoted string.
                    " (?P<var2>([^\n"\\]|\\.)*)    # Inside a double quoted string.
                )
        """

        return compile_grammar(
            grammar,
            escape_funcs={"var1": single_quoted_wrapper, "var2": double_quoted_wrapper},
            unescape_funcs={"var1": unwrapper, "var2": unwrapper},
        )

    def _complete_path_while_typing(self, document: Document) -> bool:
        char_before_cursor = document.char_before_cursor
        return bool(
            document.text
            and (char_before_cursor.isalnum() or char_before_cursor in "/.~")
        )

    def _complete_python_while_typing(self, document: Document) -> bool:
        """
        When `complete_while_typing` is set, only return completions when this
        returns `True`.
        """
        text = document.text_before_cursor  # .rstrip()
        char_before_cursor = text[-1:]
        return bool(
            text and (char_before_cursor.isalnum() or char_before_cursor in "_.([,")
        )

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """
        Get Python completions.
        """
        # If the input starts with an exclamation mark. Use the system completer.
        if document.text.lstrip().startswith("!"):
            yield from self._system_completer.get_completions(
                Document(
                    text=document.text[1:], cursor_position=document.cursor_position - 1
                ),
                complete_event,
            )
            return

        # Do dictionary key completions.
        if complete_event.completion_requested or self._complete_python_while_typing(
            document
        ):
            if self.enable_dictionary_completion():
                has_dict_completions = False
                for c in self._dictionary_completer.get_completions(
                    document, complete_event
                ):
                    if c.text not in "[.":
                        # If we get the [ or . completion, still include the other
                        # completions.
                        has_dict_completions = True
                    yield c
                if has_dict_completions:
                    return

        # Do Path completions (if there were no dictionary completions).
        if complete_event.completion_requested or self._complete_path_while_typing(
            document
        ):
            yield from self._path_completer.get_completions(document, complete_event)

        # Do Jedi completions.
        if complete_event.completion_requested or self._complete_python_while_typing(
            document
        ):
            # If we are inside a string, Don't do Jedi completion.
            if not self._path_completer_grammar.match(document.text_before_cursor):
                # Do Jedi Python completions.
                yield from self._jedi_completer.get_completions(
                    document, complete_event
                )


class JediCompleter(Completer):
    """
    Autocompleter that uses the Jedi library.
    """

    def __init__(
        self,
        get_globals: Callable[[], dict[str, Any]],
        get_locals: Callable[[], dict[str, Any]],
    ) -> None:
        super().__init__()

        self.get_globals = get_globals
        self.get_locals = get_locals

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        script = get_jedi_script_from_document(
            document, self.get_locals(), self.get_globals()
        )

        if script:
            try:
                jedi_completions = script.complete(
                    column=document.cursor_position_col,
                    line=document.cursor_position_row + 1,
                )
            except TypeError:
                # Issue #9: bad syntax causes completions() to fail in jedi.
                # https://github.com/jonathanslenders/python-prompt-toolkit/issues/9
                pass
            except UnicodeDecodeError:
                # Issue #43: UnicodeDecodeError on OpenBSD
                # https://github.com/jonathanslenders/python-prompt-toolkit/issues/43
                pass
            except AttributeError:
                # Jedi issue #513: https://github.com/davidhalter/jedi/issues/513
                pass
            except ValueError:
                # Jedi issue: "ValueError: invalid \x escape"
                pass
            except KeyError:
                # Jedi issue: "KeyError: u'a_lambda'."
                # https://github.com/jonathanslenders/ptpython/issues/89
                pass
            except OSError:
                # Jedi issue: "IOError: No such file or directory."
                # https://github.com/jonathanslenders/ptpython/issues/71
                pass
            except AssertionError:
                # In jedi.parser.__init__.py: 227, in remove_last_newline,
                # the assertion "newline.value.endswith('\n')" can fail.
                pass
            except SystemError:
                # In jedi.api.helpers.py: 144, in get_stack_at_position
                # raise SystemError("This really shouldn't happen. There's a bug in Jedi.")
                pass
            except NotImplementedError:
                # See: https://github.com/jonathanslenders/ptpython/issues/223
                pass
            except Exception:
                # Suppress all other Jedi exceptions.
                pass
            else:
                # Move function parameters to the top.
                jedi_completions = sorted(
                    jedi_completions,
                    key=lambda jc: (
                        # Params first.
                        jc.type != "param",
                        # Private at the end.
                        jc.name.startswith("_"),
                        # Then sort by name.
                        jc.name_with_symbols.lower(),
                    ),
                )

                for jc in jedi_completions:
                    if jc.type == "function":
                        suffix = "()"
                    else:
                        suffix = ""

                    if jc.type == "param":
                        suffix = "..."

                    yield Completion(
                        jc.name_with_symbols,
                        len(jc.complete) - len(jc.name_with_symbols),
                        display=jc.name_with_symbols + suffix,
                        display_meta=jc.type,
                        style=_get_style_for_jedi_completion(jc),
                    )


class DictionaryCompleter(Completer):
    """
    Experimental completer for Python dictionary keys.

    Warning: This does an `eval` and `repr` on some Python expressions before
             the cursor, which is potentially dangerous. It doesn't match on
             function calls, so it only triggers attribute access.
    """

    def __init__(
        self,
        get_globals: Callable[[], dict[str, Any]],
        get_locals: Callable[[], dict[str, Any]],
    ) -> None:
        super().__init__()

        self.get_globals = get_globals
        self.get_locals = get_locals

        # Pattern for expressions that are "safe" to eval for auto-completion.
        # These are expressions that contain only attribute and index lookups.
        varname = r"[a-zA-Z_][a-zA-Z0-9_]*"

        expression = rf"""
            # Any expression safe enough to eval while typing.
            # No operators, except dot, and only other dict lookups.
            # Technically, this can be unsafe of course, if bad code runs
            # in `__getattr__` or ``__getitem__``.
            (
                # Variable name
                {varname}

                \s*

                (?:
                    # Attribute access.
                    \s* \. \s* {varname} \s*

                    |

                    # Item lookup.
                    # (We match the square brackets. The key can be anything.
                    # We don't care about matching quotes here in the regex.
                    # Nested square brackets are not supported.)
                    \s* \[ [^\[\]]+ \] \s*
                )*
            )
        """

        # Pattern for recognizing for-loops, so that we can provide
        # autocompletion on the iterator of the for-loop. (According to the
        # first item of the collection we're iterating over.)
        self.for_loop_pattern = re.compile(
            rf"""
                for \s+ ([a-zA-Z0-9_]+) \s+ in \s+ {expression} \s* :
            """,
            re.VERBOSE,
        )

        # Pattern for matching a simple expression (for completing [ or .
        # operators).
        self.expression_pattern = re.compile(
            rf"""
                {expression}
                $
            """,
            re.VERBOSE,
        )

        # Pattern for matching item lookups.
        self.item_lookup_pattern = re.compile(
            rf"""
                {expression}

                # Dict lookup to complete (square bracket open + start of
                # string).
                \[
                \s* ([^\[\]]*)$
            """,
            re.VERBOSE,
        )

        # Pattern for matching attribute lookups.
        self.attribute_lookup_pattern = re.compile(
            rf"""
                {expression}

                # Attribute lookup to complete (dot + varname).
                \.
                \s* ([a-zA-Z0-9_]*)$
            """,
            re.VERBOSE,
        )

    def _lookup(self, expression: str, temp_locals: dict[str, Any]) -> object:
        """
        Do lookup of `object_var` in the context.
        `temp_locals` is a dictionary, used for the locals.
        """
        try:
            return eval(expression.strip(), self.get_globals(), temp_locals)
        except BaseException:
            return None  # Many exception, like NameError can be thrown here.

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        # First, find all for-loops, and assign the first item of the
        # collections they're iterating to the iterator variable, so that we
        # can provide code completion on the iterators.
        temp_locals = self.get_locals().copy()

        for match in self.for_loop_pattern.finditer(document.text_before_cursor):
            varname, expression = match.groups()
            expression_val = self._lookup(expression, temp_locals)

            # We do this only for lists and tuples. Calling `next()` on any
            # collection would create undesired side effects.
            if isinstance(expression_val, (list, tuple)) and expression_val:
                temp_locals[varname] = expression_val[0]

        # Get all completions.
        yield from self._get_expression_completions(
            document, complete_event, temp_locals
        )
        yield from self._get_item_lookup_completions(
            document, complete_event, temp_locals
        )
        yield from self._get_attribute_completions(
            document, complete_event, temp_locals
        )

    def _do_repr(self, obj: object) -> str:
        try:
            return str(repr(obj))
        except BaseException:
            raise ReprFailedError

    def eval_expression(self, document: Document, locals: dict[str, Any]) -> object:
        """
        Evaluate
        """
        match = self.expression_pattern.search(document.text_before_cursor)
        if match is not None:
            object_var = match.groups()[0]
            return self._lookup(object_var, locals)

        return None

    def _get_expression_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
        temp_locals: dict[str, Any],
    ) -> Iterable[Completion]:
        """
        Complete the [ or . operator after an object.
        """
        result = self.eval_expression(document, temp_locals)

        if result is not None:
            if isinstance(
                result,
                (list, tuple, dict, collections_abc.Mapping, collections_abc.Sequence),
            ):
                yield Completion("[", 0)

            else:
                # Note: Don't call `if result` here. That can fail for types
                #       that have custom truthness checks.
                yield Completion(".", 0)

    def _get_item_lookup_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
        temp_locals: dict[str, Any],
    ) -> Iterable[Completion]:
        """
        Complete dictionary keys.
        """

        def meta_repr(obj: object, key: object) -> Callable[[], str]:
            "Abbreviate meta text, make sure it fits on one line."
            cached_result: str | None = None

            # We return a function, so that it gets computed when it's needed.
            # When there are many completions, that improves the performance
            # quite a bit (for the multi-column completion menu, we only need
            # to display one meta text).
            # Note that we also do the lookup itself in here (`obj[key]`),
            # because this part can also be slow for some mapping
            # implementations.
            def get_value_repr() -> str:
                nonlocal cached_result
                if cached_result is not None:
                    return cached_result

                try:
                    value = obj[key]  # type: ignore

                    text = self._do_repr(value)
                except BaseException:
                    return "-"

                # Take first line, if multiple lines.
                if "\n" in text:
                    text = text.split("\n", 1)[0] + "..."

                cached_result = text
                return text

            return get_value_repr

        match = self.item_lookup_pattern.search(document.text_before_cursor)
        if match is not None:
            object_var, key = match.groups()

            # Do lookup of `object_var` in the context.
            result = self._lookup(object_var, temp_locals)

            # If this object is a dictionary, complete the keys.
            if isinstance(result, (dict, collections_abc.Mapping)):
                # Try to evaluate the key.
                key_obj_str = str(key)
                for k in [key, key + '"', key + "'"]:
                    try:
                        key_obj_str = str(ast.literal_eval(k))
                    except (SyntaxError, ValueError):
                        continue
                    else:
                        break

                for k in result:
                    if str(k).startswith(key_obj_str):
                        try:
                            k_repr = self._do_repr(k)
                            yield Completion(
                                k_repr + "]",
                                -len(key),
                                display=f"[{k_repr}]",
                                display_meta=meta_repr(result, k),
                            )
                        except ReprFailedError:
                            pass

            # Complete list/tuple index keys.
            elif isinstance(result, (list, tuple, collections_abc.Sequence)):
                if not key or key.isdigit():
                    for k in range(min(len(result), 1000)):
                        if str(k).startswith(key):
                            try:
                                k_repr = self._do_repr(k)
                                yield Completion(
                                    k_repr + "]",
                                    -len(key),
                                    display=f"[{k_repr}]",
                                    display_meta=meta_repr(result, k),
                                )
                            except KeyError:
                                # `result[k]` lookup failed. Trying to complete
                                # broken object.
                                pass
                            except ReprFailedError:
                                pass

    def _get_attribute_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
        temp_locals: dict[str, Any],
    ) -> Iterable[Completion]:
        """
        Complete attribute names.
        """
        match = self.attribute_lookup_pattern.search(document.text_before_cursor)
        if match is not None:
            object_var, attr_name = match.groups()

            # Do lookup of `object_var` in the context.
            result = self._lookup(object_var, temp_locals)

            names = self._sort_attribute_names(dir(result))

            def get_suffix(name: str) -> str:
                try:
                    obj = getattr(result, name, None)
                    if inspect.isfunction(obj) or inspect.ismethod(obj):
                        return "()"
                    if isinstance(obj, collections_abc.Mapping):
                        return "{}"
                    if isinstance(obj, collections_abc.Sequence):
                        return "[]"
                except:
                    pass
                return ""

            for name in names:
                if name.startswith(attr_name):
                    suffix = get_suffix(name)
                    yield Completion(name, -len(attr_name), display=name + suffix)

    def _sort_attribute_names(self, names: list[str]) -> list[str]:
        """
        Sort attribute names alphabetically, but move the double underscore and
        underscore names to the end.
        """

        def sort_key(name: str) -> tuple[int, str]:
            if name.startswith("__"):
                return (2, name)  # Double underscore comes latest.
            if name.startswith("_"):
                return (1, name)  # Single underscore before that.
            return (0, name)  # Other names first.

        return sorted(names, key=sort_key)


class HidePrivateCompleter(Completer):
    """
    Wrapper around completer that hides private fields, depending on whether or
    not public fields are shown.

    (The reason this is implemented as a `Completer` wrapper is because this
    way it works also with `FuzzyCompleter`.)
    """

    def __init__(
        self,
        completer: Completer,
        complete_private_attributes: Callable[[], CompletePrivateAttributes],
    ) -> None:
        self.completer = completer
        self.complete_private_attributes = complete_private_attributes

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        completions = list(
            # Limit at 5k completions for performance.
            islice(self.completer.get_completions(document, complete_event), 0, 5000)
        )
        complete_private_attributes = self.complete_private_attributes()
        hide_private = False

        def is_private(completion: Completion) -> bool:
            text = fragment_list_to_text(to_formatted_text(completion.display))
            return text.startswith("_")

        if complete_private_attributes == CompletePrivateAttributes.NEVER:
            hide_private = True

        elif complete_private_attributes == CompletePrivateAttributes.IF_NO_PUBLIC:
            hide_private = any(not is_private(completion) for completion in completions)

        if hide_private:
            completions = [
                completion for completion in completions if not is_private(completion)
            ]

        return completions


class ReprFailedError(Exception):
    "Raised when the repr() call in `DictionaryCompleter` fails."


try:
    import builtins

    _builtin_names = dir(builtins)
except ImportError:  # Python 2.
    _builtin_names = []


def _get_style_for_jedi_completion(
    jedi_completion: jedi.api.classes.Completion,
) -> str:
    """
    Return completion style to use for this name.
    """
    name = jedi_completion.name_with_symbols

    if jedi_completion.type == "param":
        return "class:completion.param"

    if name in _builtin_names:
        return "class:completion.builtin"

    if keyword.iskeyword(name):
        return "class:completion.keyword"

    return ""
