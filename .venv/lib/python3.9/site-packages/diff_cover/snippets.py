"""
Load snippets from source files to show violation lines
in HTML reports.
"""

import contextlib
from tokenize import open as openpy

import chardet
import pygments
from pygments.formatters.html import HtmlFormatter
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers import guess_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.util import ClassNotFound

from diff_cover.git_path import GitPathTool


class Snippet:
    """
    A source code snippet.
    """

    VIOLATION_COLOR = "#ffcccc"
    DIV_CSS_CLASS = "snippet"

    # Number of extra lines to include before and after
    # each snippet to provide context.
    NUM_CONTEXT_LINES = 4

    # Maximum distance between two violations within
    # a snippet.  If violations are further apart,
    # should split into two snippets.
    MAX_GAP_IN_SNIPPET = 4

    # See https://github.com/github/linguist/blob/master/lib/linguist/languages.yml
    # for typical values of accepted programming language hints in Markdown code fenced blocks
    LEXER_TO_MARKDOWN_CODE_HINT = {
        "Python": "python",
        "C++": "cpp",
        # TODO: expand this list...
    }

    def __init__(
        self,
        src_tokens,
        src_filename,
        start_line,
        last_line,
        violation_lines,
        lexer_name,
    ):
        """
        Create a source code snippet.

        `src_tokens` is a list of `(token_type, value)`
        tuples, parsed from the source file.
        NOTE: `value` must be `unicode`, not a `str`

        `src_filename` is the name of the source file,
        used to determine the source file language.

        `start_line` is the line number of first line
        in `src_str`.  The first line in the file is
        line number 1.

        `last_line` is the line number of last line
        in `src_str`.

        `violation_lines` is a list of line numbers
        to highlight as violations.

        `lexer_name` provides an hint on the
        programming language for this snippet.
        See https://pygments.org/docs/lexers/

        Raises a `ValueError` if `start_line` is less than 1
        """
        if start_line < 1:
            raise ValueError("Start line must be >= 1")

        self._src_tokens = src_tokens
        self._src_filename = src_filename
        self._start_line = start_line
        self._last_line = last_line
        self._violation_lines = violation_lines
        self._lexer_name = lexer_name

    @classmethod
    def style_defs(cls):
        """
        Return the CSS style definitions required
        by the formatted snippet.
        """
        formatter = HtmlFormatter()
        formatter.style.highlight_color = cls.VIOLATION_COLOR
        return formatter.get_style_defs()

    def html(self):
        """
        Return an HTML representation of the snippet.
        """
        formatter = HtmlFormatter(
            cssclass=self.DIV_CSS_CLASS,
            linenos=True,
            linenostart=self._start_line,
            hl_lines=self._shift_lines(self._violation_lines, self._start_line),
            lineanchors=self._src_filename,
        )

        return pygments.format(self.src_tokens(), formatter)

    def markdown(self):
        """
        Return a Markdown representation of the snippet using Markdown fenced code blocks.
        See https://github.github.com/gfm/#fenced-code-blocks.
        """

        line_number_length = len(str(self._last_line))

        text = ""
        for i, line in enumerate(self.text().splitlines(), start=self._start_line):
            if i > self._start_line:
                text += "\n"

            notice = " "
            if i in self._violation_lines:
                notice = "!"

            format_string = "{} {:>" + str(line_number_length) + "} {}"
            text += format_string.format(notice, i, line)

        header = "Lines %d-%d\n\n" % (self._start_line, self._last_line)
        if self._lexer_name in self.LEXER_TO_MARKDOWN_CODE_HINT:
            return header + (
                "```"
                + self.LEXER_TO_MARKDOWN_CODE_HINT[self._lexer_name]
                + "\n"
                + text
                + "\n```\n"
            )

        # unknown programming language, return a non-decorated fenced code block:
        return "```\n" + text + "\n```\n"

    def terminal(self):
        """
        Return a Terminal-friendly (with ANSI color sequences) representation of the snippet.
        """
        formatter = TerminalFormatter(
            linenos=True,
            colorscheme=None,
            linenostart=self._start_line,
        )

        return pygments.format(self.src_tokens(), formatter)

    def src_tokens(self):
        """
        Return a list of `(token_type, value)` tokens
        parsed from the source file.
        """
        return self._src_tokens

    def line_range(self):
        """
        Return a tuple of the form `(start_line, end_line)`
        indicating the start and end line number of the snippet.
        """
        num_lines = len(self.text().split("\n"))
        end_line = self._start_line + num_lines - 1
        return (self._start_line, end_line)

    def text(self):
        """
        Return the source text for the snippet.
        """
        return "".join([val for _, val in self._src_tokens])

    @classmethod
    def load_formatted_snippets(cls, src_path, violation_lines):
        """
        Load snippets from the file at `src_path` and format
        them as HTML and as plain text.
        Returns a dictionary containing the two types of formatting
        results for code snippets.

        See `load_snippets()` for details.
        """

        # load once...
        snippet_list = cls.load_snippets(src_path, violation_lines)

        # ...render twice in different formats
        return {
            "html": [snippet.html() for snippet in snippet_list],
            "markdown": [snippet.markdown() for snippet in snippet_list],
            "terminal": [snippet.terminal() for snippet in snippet_list],
        }

    @classmethod
    def load_contents(cls, src_path):
        try:
            with openpy(GitPathTool.relative_path(src_path)) as src_file:
                contents = src_file.read()
        except (SyntaxError, UnicodeDecodeError):
            # this tool was originally written with python in mind.
            # for processing non python files encoded in anything other than ascii or utf-8 that
            # code wont work
            with open(GitPathTool.relative_path(src_path), "rb") as src_file:
                contents = src_file.read()

        if isinstance(contents, bytes):
            encoding = chardet.detect(contents).get("encoding", "utf-8")
            with contextlib.suppress(UnicodeDecodeError):
                contents = contents.decode(encoding)

        if isinstance(contents, bytes):
            # We failed to decode the file.
            # if this is happening a lot I should just bite the bullet
            # and write a parameter to let people list their file encodings
            print(
                "Warning: I was not able to decode your src file. "
                "I can continue but code snippets in the final report may look wrong"
            )
            contents = contents.decode("utf-8", "replace")
        return contents

    @classmethod
    def load_snippets(cls, src_path, violation_lines):
        """
        Load snippets from the file at `src_path` to show
        violations on lines in the list `violation_lines`
        (list of line numbers, starting at index 0).

        The file at `src_path` should be a text file (not binary).

        Returns a list of `Snippet` instances.

        Raises an `IOError` if the file could not be loaded.
        """
        contents = cls.load_contents(src_path)

        # Construct a list of snippet ranges
        src_lines = contents.split("\n")
        snippet_ranges = cls._snippet_ranges(len(src_lines), violation_lines)

        # Parse the source into tokens
        token_stream, lexer = cls._parse_src(contents, src_path)

        # Group the tokens by snippet
        token_groups = cls._group_tokens(token_stream, snippet_ranges)

        return [
            Snippet(tokens, src_path, start, end, violation_lines, lexer.name)
            for (start, end), tokens in sorted(token_groups.items())
        ]

    @classmethod
    def _parse_src(cls, src_contents, src_filename):
        """
        Return a stream of `(token_type, value)` tuples
        parsed from `src_contents` (str)

        Uses `src_filename` to guess the type of file
        so it can highlight syntax correctly.
        """

        # Parse the source into tokens
        try:
            lexer = guess_lexer_for_filename(src_filename, src_contents)
        except ClassNotFound:
            lexer = TextLexer()

        # Ensure that we don't strip newlines from
        # the source file when lexing.
        lexer.stripnl = False

        return pygments.lex(src_contents, lexer), lexer

    @classmethod
    def _group_tokens(cls, token_stream, range_list):
        """
        Group tokens into snippet ranges.

        `token_stream` is a generator that produces
        `(token_type, value)` tuples,

        `range_list` is a list of `(start, end)` tuples representing
        the (inclusive) range of line numbers for each snippet.

        Assumes that `range_list` is an ascending order by start value.

        Returns a dict mapping ranges to lists of tokens:
        {
            (4, 10): [(ttype_1, val_1), (ttype_2, val_2), ...],
            (29, 39): [(ttype_3, val_3), ...],
            ...
        }

        The algorithm is slightly complicated because a single token
        can contain multiple line breaks.
        """

        # Create a map from ranges (start/end tuples) to tokens
        token_map = {rng: [] for rng in range_list}

        # Keep track of the current line number; we will
        # increment this as we encounter newlines in token values
        line_num = 1

        for ttype, val in token_stream:
            # If there are newlines in this token,
            # we need to split it up and check whether
            # each line within the token is within one
            # of our ranges.
            if "\n" in val:
                val_lines = val.split("\n")

                # Check if the tokens match each range
                for (start, end), filtered_tokens in token_map.items():
                    # Filter out lines that are not in this range
                    include_vals = [
                        val_lines[i]
                        for i in range(len(val_lines))
                        if i + line_num in range(start, end + 1)
                    ]

                    # If we found any lines, store the tokens
                    if len(include_vals) > 0:
                        token = (ttype, "\n".join(include_vals))
                        filtered_tokens.append(token)

                # Increment the line number
                # by the number of lines we found
                line_num += len(val_lines) - 1

            # No newline in this token
            # If we're in the line range, add it
            else:
                # Check if the tokens match each range
                for (start, end), filtered_tokens in token_map.items():
                    # If we got a match, store the token
                    if line_num in range(start, end + 1):
                        filtered_tokens.append((ttype, val))

                    # Otherwise, ignore the token

        return token_map

    @classmethod
    def _snippet_ranges(cls, num_src_lines, violation_lines):
        """
        Given the number of source file lines and list of
        violation line numbers, return a list of snippet
        ranges of the form `(start_line, end_line)`.

        Each snippet contains a few extra lines of context
        before/after the first/last violation.  Nearby
        violations are grouped within the same snippet.
        """
        current_range = (None, None)
        lines_since_last_violation = 0
        snippet_ranges = []
        for line_num in range(1, num_src_lines + 1):
            # If we have not yet started a snippet,
            # check if we can (is this line a violation?)
            if current_range[0] is None:
                if line_num in violation_lines:
                    # Expand to include extra context, but not before line 1
                    snippet_start = max(1, line_num - cls.NUM_CONTEXT_LINES)
                    current_range = (snippet_start, None)
                    lines_since_last_violation = 0

            # If we are within a snippet, check if we
            # can end the snippet (have we gone enough
            # lines without hitting a violation?)
            elif current_range[1] is None:
                if line_num in violation_lines:
                    lines_since_last_violation = 0

                elif lines_since_last_violation > cls.MAX_GAP_IN_SNIPPET:
                    # Expand to include extra context, but not after last line
                    snippet_end = line_num - lines_since_last_violation
                    snippet_end = min(
                        num_src_lines, snippet_end + cls.NUM_CONTEXT_LINES
                    )
                    current_range = (current_range[0], snippet_end)

                    # Store the snippet and start looking for the next one
                    snippet_ranges.append(current_range)
                    current_range = (None, None)

            # Another line since the last violation
            lines_since_last_violation += 1

        # If we started a snippet but didn't finish it, do so now
        if current_range[0] is not None and current_range[1] is None:
            snippet_ranges.append((current_range[0], num_src_lines))

        return snippet_ranges

    @staticmethod
    def _shift_lines(line_num_list, start_line):
        """
        Shift all line numbers in `line_num_list` so that
        `start_line` is treated as line 1.

        For example, `[5, 8, 9]` with `start_line=3` would
        become `[3, 6, 7]`.

        Assumes that all entries in `line_num_list` are greater
        than or equal to `start_line`; otherwise, they will
        be excluded from the list.
        """
        return [
            line_num - start_line + 1
            for line_num in line_num_list
            if line_num >= start_line
        ]
