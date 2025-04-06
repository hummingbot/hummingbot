from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Generator, Iterable

from prompt_toolkit.formatted_text import (
    HTML,
    AnyFormattedText,
    FormattedText,
    OneStyleAndTextTuple,
    StyleAndTextTuples,
    fragment_list_width,
    merge_formatted_text,
    to_formatted_text,
)
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.output import Output
from prompt_toolkit.shortcuts import PromptSession, print_formatted_text
from prompt_toolkit.styles import BaseStyle, StyleTransformation
from prompt_toolkit.styles.pygments import pygments_token_to_classname
from prompt_toolkit.utils import get_cwidth
from pygments.lexers import PythonLexer, PythonTracebackLexer

__all__ = ["OutputPrinter"]

# Never reformat results larger than this:
MAX_REFORMAT_SIZE = 1_000_000


@dataclass
class OutputPrinter:
    """
    Result printer.

    Usage::

        printer = OutputPrinter(...)
        printer.display_result(...)
        printer.display_exception(...)
    """

    output: Output
    input: Input
    style: BaseStyle
    title: AnyFormattedText
    style_transformation: StyleTransformation

    def display_result(
        self,
        result: object,
        *,
        out_prompt: AnyFormattedText,
        reformat: bool,
        highlight: bool,
        paginate: bool,
    ) -> None:
        """
        Show __repr__ (or `__pt_repr__`) for an `eval` result and print to output.

        :param reformat: Reformat result using 'black' before printing if the
            result is parsable as Python code.
        :param highlight: Syntax highlight the result.
        :param paginate: Show paginator when the result does not fit on the
            screen.
        """
        out_prompt = to_formatted_text(out_prompt)
        out_prompt_width = fragment_list_width(out_prompt)

        result = self._insert_out_prompt_and_split_lines(
            self._format_result_output(
                result,
                reformat=reformat,
                highlight=highlight,
                line_length=self.output.get_size().columns - out_prompt_width,
                paginate=paginate,
            ),
            out_prompt=out_prompt,
        )
        self._display_result(result, paginate=paginate)

    def display_exception(
        self, e: BaseException, *, highlight: bool, paginate: bool
    ) -> None:
        """
        Render an exception.
        """
        result = self._insert_out_prompt_and_split_lines(
            self._format_exception_output(e, highlight=highlight),
            out_prompt="",
        )
        self._display_result(result, paginate=paginate)

    def display_style_and_text_tuples(
        self,
        result: Iterable[OneStyleAndTextTuple],
        *,
        paginate: bool,
    ) -> None:
        self._display_result(
            self._insert_out_prompt_and_split_lines(result, out_prompt=""),
            paginate=paginate,
        )

    def _display_result(
        self,
        lines: Iterable[StyleAndTextTuples],
        *,
        paginate: bool,
    ) -> None:
        if paginate:
            self._print_paginated_formatted_text(lines)
        else:
            for line in lines:
                self._print_formatted_text(line)

        self.output.flush()

    def _print_formatted_text(self, line: StyleAndTextTuples, end: str = "\n") -> None:
        print_formatted_text(
            FormattedText(line),
            style=self.style,
            style_transformation=self.style_transformation,
            include_default_pygments_style=False,
            output=self.output,
            end=end,
        )

    def _format_result_output(
        self,
        result: object,
        *,
        reformat: bool,
        highlight: bool,
        line_length: int,
        paginate: bool,
    ) -> Generator[OneStyleAndTextTuple, None, None]:
        """
        Format __repr__ for an `eval` result.

        Note: this can raise `KeyboardInterrupt` if either calling `__repr__`,
              `__pt_repr__` or formatting the output with "Black" takes to long
              and the user presses Control-C.
        """
        # If __pt_repr__ is present, take this. This can return prompt_toolkit
        # formatted text.
        try:
            if hasattr(result, "__pt_repr__"):
                formatted_result_repr = to_formatted_text(
                    getattr(result, "__pt_repr__")()
                )
                yield from formatted_result_repr
                return
        except (GeneratorExit, KeyboardInterrupt):
            raise  # Don't catch here.
        except:
            # For bad code, `__getattr__` can raise something that's not an
            # `AttributeError`. This happens already when calling `hasattr()`.
            pass

        # Call `__repr__` of given object first, to turn it in a string.
        try:
            result_repr = repr(result)
        except KeyboardInterrupt:
            raise  # Don't catch here.
        except BaseException as e:
            # Calling repr failed.
            self.display_exception(e, highlight=highlight, paginate=paginate)
            return

        # Determine whether it's valid Python code. If not,
        # reformatting/highlighting won't be applied.
        if len(result_repr) < MAX_REFORMAT_SIZE:
            try:
                compile(result_repr, "", "eval")
            except SyntaxError:
                valid_python = False
            else:
                valid_python = True
        else:
            valid_python = False

        if valid_python and reformat:
            # Inline import. Slightly speed up start-up time if black is
            # not used.
            try:
                import black

                if not hasattr(black, "Mode"):
                    raise ImportError
            except ImportError:
                pass  # no Black package in your installation
            else:
                result_repr = black.format_str(
                    result_repr,
                    mode=black.Mode(line_length=line_length),
                )

        if valid_python and highlight:
            yield from _lex_python_result(result_repr)
        else:
            yield ("", result_repr)

    def _insert_out_prompt_and_split_lines(
        self, result: Iterable[OneStyleAndTextTuple], out_prompt: AnyFormattedText
    ) -> Iterable[StyleAndTextTuples]:
        r"""
        Split styled result in lines (based on the \n characters in the result)
        an insert output prompt on whitespace in front of each line. (This does
        not yet do the soft wrapping.)

        Yield lines as a result.
        """
        out_prompt = to_formatted_text(out_prompt)
        out_prompt_width = fragment_list_width(out_prompt)
        prefix = ("", " " * out_prompt_width)

        for i, line in enumerate(split_lines(result)):
            if i == 0:
                line = [*out_prompt, *line]
            else:
                line = [prefix, *line]
            yield line

    def _apply_soft_wrapping(
        self, lines: Iterable[StyleAndTextTuples]
    ) -> Iterable[StyleAndTextTuples]:
        """
        Apply soft wrapping to the given lines. Wrap according to the terminal
        width. Insert whitespace in front of each wrapped line to align it with
        the output prompt.
        """
        line_length = self.output.get_size().columns

        # Iterate over hard wrapped lines.
        for lineno, line in enumerate(lines):
            columns_in_buffer = 0
            current_line: list[OneStyleAndTextTuple] = []

            for style, text, *_ in line:
                for c in text:
                    width = get_cwidth(c)

                    # (Soft) wrap line if it doesn't fit.
                    if columns_in_buffer + width > line_length:
                        yield current_line
                        columns_in_buffer = 0
                        current_line = []

                    columns_in_buffer += width
                    current_line.append((style, c))

            if len(current_line) > 0:
                yield current_line

    def _print_paginated_formatted_text(
        self, lines: Iterable[StyleAndTextTuples]
    ) -> None:
        """
        Print formatted text, using --MORE-- style pagination.
        (Avoid filling up the terminal's scrollback buffer.)
        """
        lines = self._apply_soft_wrapping(lines)
        pager_prompt = create_pager_prompt(
            self.style, self.title, output=self.output, input=self.input
        )

        abort = False
        print_all = False

        # Max number of lines allowed in the buffer before painting.
        size = self.output.get_size()
        max_rows = size.rows - 1

        # Page buffer.
        page: StyleAndTextTuples = []

        def show_pager() -> None:
            nonlocal abort, max_rows, print_all

            # Run pager prompt in another thread.
            # Same as for the input. This prevents issues with nested event
            # loops.
            pager_result = pager_prompt.prompt(in_thread=True)

            if pager_result == PagerResult.ABORT:
                print("...")
                abort = True

            elif pager_result == PagerResult.NEXT_LINE:
                max_rows = 1

            elif pager_result == PagerResult.NEXT_PAGE:
                max_rows = size.rows - 1

            elif pager_result == PagerResult.PRINT_ALL:
                print_all = True

        # Loop over lines. Show --MORE-- prompt when page is filled.
        rows = 0

        for lineno, line in enumerate(lines):
            page.extend(line)
            page.append(("", "\n"))
            rows += 1

            if rows >= max_rows:
                self._print_formatted_text(page, end="")
                page = []
                rows = 0

                if not print_all:
                    show_pager()
                    if abort:
                        return

        self._print_formatted_text(page)

    def _format_exception_output(
        self, e: BaseException, highlight: bool
    ) -> Generator[OneStyleAndTextTuple, None, None]:
        # Instead of just calling ``traceback.format_exc``, we take the
        # traceback and skip the bottom calls of this framework.
        t, v, tb = sys.exc_info()

        # Required for pdb.post_mortem() to work.
        sys.last_type, sys.last_value, sys.last_traceback = t, v, tb

        tblist = list(traceback.extract_tb(tb))

        for line_nr, tb_tuple in enumerate(tblist):
            if tb_tuple[0] == "<stdin>":
                tblist = tblist[line_nr:]
                break

        tb_list = traceback.format_list(tblist)
        if tb_list:
            tb_list.insert(0, "Traceback (most recent call last):\n")
        tb_list.extend(traceback.format_exception_only(t, v))

        tb_str = "".join(tb_list)

        # Format exception and write to output.
        # (We use the default style. Most other styles result
        # in unreadable colors for the traceback.)
        if highlight:
            for index, tokentype, text in PythonTracebackLexer().get_tokens_unprocessed(
                tb_str
            ):
                yield ("class:" + pygments_token_to_classname(tokentype), text)
        else:
            yield ("", tb_str)


class PagerResult(Enum):
    ABORT = "ABORT"
    NEXT_LINE = "NEXT_LINE"
    NEXT_PAGE = "NEXT_PAGE"
    PRINT_ALL = "PRINT_ALL"


def create_pager_prompt(
    style: BaseStyle,
    title: AnyFormattedText = "",
    input: Input | None = None,
    output: Output | None = None,
) -> PromptSession[PagerResult]:
    """
    Create a "--MORE--" prompt for paginated output.
    """
    bindings = KeyBindings()

    @bindings.add("enter")
    @bindings.add("down")
    def next_line(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.NEXT_LINE)

    @bindings.add("space")
    def next_page(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.NEXT_PAGE)

    @bindings.add("a")
    def print_all(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.PRINT_ALL)

    @bindings.add("q")
    @bindings.add("c-c")
    @bindings.add("c-d")
    @bindings.add("escape", eager=True)
    def no(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.ABORT)

    @bindings.add("<any>")
    def _(event: KeyPressEvent) -> None:
        "Disallow inserting other text."
        pass

    session: PromptSession[PagerResult] = PromptSession(
        merge_formatted_text(
            [
                title,
                HTML(
                    "<status-toolbar>"
                    "<more> -- MORE -- </more> "
                    "<key>[Enter]</key> Scroll "
                    "<key>[Space]</key> Next page "
                    "<key>[a]</key> Print all "
                    "<key>[q]</key> Quit "
                    "</status-toolbar>: "
                ),
            ]
        ),
        key_bindings=bindings,
        erase_when_done=True,
        style=style,
        input=input,
        output=output,
    )
    return session


def _lex_python_result(result: str) -> Generator[tuple[str, str], None, None]:
    "Return token list for Python string."
    lexer = PythonLexer()
    # Use `get_tokens_unprocessed`, so that we get exactly the same string,
    # without line endings appended. `print_formatted_text` already appends a
    # line ending, and otherwise we'll have two line endings.
    tokens = lexer.get_tokens_unprocessed(result)

    for index, tokentype, text in tokens:
        yield ("class:" + pygments_token_to_classname(tokentype), text)
