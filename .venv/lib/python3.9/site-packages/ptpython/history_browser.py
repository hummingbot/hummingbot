"""
Utility to easily select lines from the history and execute them again.

`create_history_application` creates an `Application` instance that runs will
run as a sub application of the Repl/PythonInput.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Container,
    Float,
    FloatContainer,
    HSplit,
    ScrollOffsets,
    VSplit,
    Window,
    WindowAlign,
    WindowRenderInfo,
)
from prompt_toolkit.layout.controls import (
    BufferControl,
    FormattedTextControl,
    UIContent,
)
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import Margin, ScrollbarMargin
from prompt_toolkit.layout.processors import (
    Processor,
    Transformation,
    TransformationInput,
)
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.mouse_events import MouseEvent
from prompt_toolkit.widgets import Frame
from prompt_toolkit.widgets.toolbars import ArgToolbar, SearchToolbar
from pygments.lexers import Python3Lexer as PythonLexer
from pygments.lexers import RstLexer

from ptpython.layout import get_inputmode_fragments

from .utils import if_mousedown

if TYPE_CHECKING:
    from .python_input import PythonInput

HISTORY_COUNT = 2000

__all__ = ["HistoryLayout", "PythonHistory"]

E = KeyPressEvent

HELP_TEXT = """
This interface is meant to select multiple lines from the
history and execute them together.

Typical usage
-------------

1. Move the ``cursor up`` in the history pane, until the
   cursor is on the first desired line.
2. Hold down the ``space bar``, or press it multiple
   times. Each time it will select one line and move to
   the next one. Each selected line will appear on the
   right side.
3. When all the required lines are displayed on the right
   side, press ``Enter``. This will go back to the Python
   REPL and show these lines as the current input. They
   can still be edited from there.

Key bindings
------------

Many Emacs and Vi navigation key bindings should work.
Press ``F4`` to switch between Emacs and Vi mode.

Additional bindings:

- ``Space``: Select or delect a line.
- ``Tab``: Move the focus between the history and input
  pane. (Alternative: ``Ctrl-W``)
- ``Ctrl-C``: Cancel. Ignore the result and go back to
  the REPL. (Alternatives: ``q`` and ``Control-G``.)
- ``Enter``: Accept the result and go back to the REPL.
- ``F1``: Show/hide help. Press ``Enter`` to quit this
  help message.

Further, remember that searching works like in Emacs
(using ``Ctrl-R``) or Vi (using ``/``).
"""


class BORDER:
    "Box drawing characters."

    HORIZONTAL = "\u2501"
    VERTICAL = "\u2503"
    TOP_LEFT = "\u250f"
    TOP_RIGHT = "\u2513"
    BOTTOM_LEFT = "\u2517"
    BOTTOM_RIGHT = "\u251b"
    LIGHT_VERTICAL = "\u2502"


def _create_popup_window(title: str, body: Container) -> Frame:
    """
    Return the layout for a pop-up window. It consists of a title bar showing
    the `title` text, and a body layout. The window is surrounded by borders.
    """
    return Frame(body=body, title=title)


class HistoryLayout:
    """
    Create and return a `Container` instance for the history
    application.
    """

    def __init__(self, history: PythonHistory) -> None:
        search_toolbar = SearchToolbar()

        self.help_buffer_control = BufferControl(
            buffer=history.help_buffer, lexer=PygmentsLexer(RstLexer)
        )

        help_window = _create_popup_window(
            title="History Help",
            body=Window(
                content=self.help_buffer_control,
                right_margins=[ScrollbarMargin(display_arrows=True)],
                scroll_offsets=ScrollOffsets(top=2, bottom=2),
            ),
        )

        self.default_buffer_control = BufferControl(
            buffer=history.default_buffer,
            input_processors=[GrayExistingText(history.history_mapping)],
            lexer=PygmentsLexer(PythonLexer),
        )

        self.history_buffer_control = BufferControl(
            buffer=history.history_buffer,
            lexer=PygmentsLexer(PythonLexer),
            search_buffer_control=search_toolbar.control,
            preview_search=True,
        )

        history_window = Window(
            content=self.history_buffer_control,
            wrap_lines=False,
            left_margins=[HistoryMargin(history)],
            scroll_offsets=ScrollOffsets(top=2, bottom=2),
        )

        self.root_container = HSplit(
            [
                #  Top title bar.
                Window(
                    content=FormattedTextControl(_get_top_toolbar_fragments),
                    align=WindowAlign.CENTER,
                    style="class:status-toolbar",
                ),
                FloatContainer(
                    content=VSplit(
                        [
                            # Left side: history.
                            history_window,
                            # Separator.
                            Window(
                                width=D.exact(1),
                                char=BORDER.LIGHT_VERTICAL,
                                style="class:separator",
                            ),
                            # Right side: result.
                            Window(
                                content=self.default_buffer_control,
                                wrap_lines=False,
                                left_margins=[ResultMargin(history)],
                                scroll_offsets=ScrollOffsets(top=2, bottom=2),
                            ),
                        ]
                    ),
                    floats=[
                        # Help text as a float.
                        Float(
                            width=60,
                            top=3,
                            bottom=2,
                            content=ConditionalContainer(
                                content=help_window,
                                filter=has_focus(history.help_buffer),
                            ),
                        )
                    ],
                ),
                # Bottom toolbars.
                ArgToolbar(),
                search_toolbar,
                Window(
                    content=FormattedTextControl(
                        partial(_get_bottom_toolbar_fragments, history=history)
                    ),
                    style="class:status-toolbar",
                ),
            ]
        )

        self.layout = Layout(self.root_container, history_window)


def _get_top_toolbar_fragments() -> StyleAndTextTuples:
    return [("class:status-bar.title", "History browser - Insert from history")]


def _get_bottom_toolbar_fragments(history: PythonHistory) -> StyleAndTextTuples:
    python_input = history.python_input

    @if_mousedown
    def f1(mouse_event: MouseEvent) -> None:
        _toggle_help(history)

    @if_mousedown
    def tab(mouse_event: MouseEvent) -> None:
        _select_other_window(history)

    return (
        [("class:status-toolbar", " ")]
        + get_inputmode_fragments(python_input)
        + [
            ("class:status-toolbar", " "),
            ("class:status-toolbar.key", "[Space]"),
            ("class:status-toolbar", " Toggle "),
            ("class:status-toolbar.key", "[Tab]", tab),
            ("class:status-toolbar", " Focus ", tab),
            ("class:status-toolbar.key", "[Enter]"),
            ("class:status-toolbar", " Accept "),
            ("class:status-toolbar.key", "[F1]", f1),
            ("class:status-toolbar", " Help ", f1),
        ]
    )


class HistoryMargin(Margin):
    """
    Margin for the history buffer.
    This displays a green bar for the selected entries.
    """

    def __init__(self, history: PythonHistory) -> None:
        self.history_buffer = history.history_buffer
        self.history_mapping = history.history_mapping

    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:
        return 2

    def create_margin(
        self, window_render_info: WindowRenderInfo, width: int, height: int
    ) -> StyleAndTextTuples:
        document = self.history_buffer.document

        lines_starting_new_entries = self.history_mapping.lines_starting_new_entries
        selected_lines = self.history_mapping.selected_lines

        current_lineno = document.cursor_position_row

        visible_line_to_input_line = window_render_info.visible_line_to_input_line
        result: StyleAndTextTuples = []

        for y in range(height):
            line_number = visible_line_to_input_line.get(y)

            # Show stars at the start of each entry.
            # (Visualises multiline entries.)
            if line_number in lines_starting_new_entries:
                char = "*"
            else:
                char = " "

            if line_number in selected_lines:
                t = "class:history-line,selected"
            else:
                t = "class:history-line"

            if line_number == current_lineno:
                t = t + ",current"

            result.append((t, char))
            result.append(("", "\n"))

        return result


class ResultMargin(Margin):
    """
    The margin to be shown in the result pane.
    """

    def __init__(self, history: PythonHistory) -> None:
        self.history_mapping = history.history_mapping
        self.history_buffer = history.history_buffer

    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:
        return 2

    def create_margin(
        self, window_render_info: WindowRenderInfo, width: int, height: int
    ) -> StyleAndTextTuples:
        document = self.history_buffer.document

        current_lineno = document.cursor_position_row
        offset = (
            self.history_mapping.result_line_offset
        )  # original_document.cursor_position_row

        visible_line_to_input_line = window_render_info.visible_line_to_input_line

        result: StyleAndTextTuples = []

        for y in range(height):
            line_number = visible_line_to_input_line.get(y)

            if (
                line_number is None
                or line_number < offset
                or line_number >= offset + len(self.history_mapping.selected_lines)
            ):
                t = ""
            elif line_number == current_lineno:
                t = "class:history-line,selected,current"
            else:
                t = "class:history-line,selected"

            result.append((t, " "))
            result.append(("", "\n"))

        return result

    def invalidation_hash(self, document: Document) -> int:
        return document.cursor_position_row


class GrayExistingText(Processor):
    """
    Turn the existing input, before and after the inserted code gray.
    """

    def __init__(self, history_mapping: HistoryMapping) -> None:
        self.history_mapping = history_mapping
        self._lines_before = len(
            history_mapping.original_document.text_before_cursor.splitlines()
        )

    def apply_transformation(
        self, transformation_input: TransformationInput
    ) -> Transformation:
        lineno = transformation_input.lineno
        fragments = transformation_input.fragments

        if lineno < self._lines_before or lineno >= self._lines_before + len(
            self.history_mapping.selected_lines
        ):
            text = fragment_list_to_text(fragments)
            return Transformation(fragments=[("class:history.existing-input", text)])
        else:
            return Transformation(fragments=fragments)


class HistoryMapping:
    """
    Keep a list of all the lines from the history and the selected lines.
    """

    def __init__(
        self,
        history: PythonHistory,
        python_history: History,
        original_document: Document,
    ) -> None:
        self.history = history
        self.python_history = python_history
        self.original_document = original_document

        self.lines_starting_new_entries = set()
        self.selected_lines: set[int] = set()

        # Process history.
        history_strings = python_history.get_strings()
        history_lines: list[str] = []

        for entry_nr, entry in list(enumerate(history_strings))[-HISTORY_COUNT:]:
            self.lines_starting_new_entries.add(len(history_lines))

            for line in entry.splitlines():
                history_lines.append(line)

        if len(history_strings) > HISTORY_COUNT:
            history_lines[0] = (
                f"# *** History has been truncated to {HISTORY_COUNT} lines ***"
            )

        self.history_lines = history_lines
        self.concatenated_history = "\n".join(history_lines)

        # Line offset.
        if self.original_document.text_before_cursor:
            self.result_line_offset = self.original_document.cursor_position_row + 1
        else:
            self.result_line_offset = 0

    def get_new_document(self, cursor_pos: int | None = None) -> Document:
        """
        Create a `Document` instance that contains the resulting text.
        """
        lines = []

        # Original text, before cursor.
        if self.original_document.text_before_cursor:
            lines.append(self.original_document.text_before_cursor)

        # Selected entries from the history.
        for line_no in sorted(self.selected_lines):
            lines.append(self.history_lines[line_no])

        # Original text, after cursor.
        if self.original_document.text_after_cursor:
            lines.append(self.original_document.text_after_cursor)

        # Create `Document` with cursor at the right position.
        text = "\n".join(lines)
        if cursor_pos is not None and cursor_pos > len(text):
            cursor_pos = len(text)
        return Document(text, cursor_pos)

    def update_default_buffer(self) -> None:
        b = self.history.default_buffer

        b.set_document(self.get_new_document(b.cursor_position), bypass_readonly=True)


def _toggle_help(history: PythonHistory) -> None:
    "Display/hide help."
    help_buffer_control = history.history_layout.help_buffer_control

    if history.app.layout.current_control == help_buffer_control:
        history.app.layout.focus_previous()
    else:
        history.app.layout.current_control = help_buffer_control


def _select_other_window(history: PythonHistory) -> None:
    "Toggle focus between left/right window."
    current_buffer = history.app.current_buffer
    layout = history.history_layout.layout

    if current_buffer == history.history_buffer:
        layout.current_control = history.history_layout.default_buffer_control

    elif current_buffer == history.default_buffer:
        layout.current_control = history.history_layout.history_buffer_control


def create_key_bindings(
    history: PythonHistory,
    python_input: PythonInput,
    history_mapping: HistoryMapping,
) -> KeyBindings:
    """
    Key bindings.
    """
    bindings = KeyBindings()
    handle = bindings.add

    @handle(" ", filter=has_focus(history.history_buffer))
    def _(event: E) -> None:
        """
        Space: select/deselect line from history pane.
        """
        b = event.current_buffer
        line_no = b.document.cursor_position_row

        if not history_mapping.history_lines:
            # If we've no history, then nothing to do
            return

        if line_no in history_mapping.selected_lines:
            # Remove line.
            history_mapping.selected_lines.remove(line_no)
            history_mapping.update_default_buffer()
        else:
            # Add line.
            history_mapping.selected_lines.add(line_no)
            history_mapping.update_default_buffer()

            # Update cursor position
            default_buffer = history.default_buffer
            default_lineno = (
                sorted(history_mapping.selected_lines).index(line_no)
                + history_mapping.result_line_offset
            )
            default_buffer.cursor_position = (
                default_buffer.document.translate_row_col_to_index(default_lineno, 0)
            )

        # Also move the cursor to the next line. (This way they can hold
        # space to select a region.)
        b.cursor_position = b.document.translate_row_col_to_index(line_no + 1, 0)

    @handle(" ", filter=has_focus(DEFAULT_BUFFER))
    @handle("delete", filter=has_focus(DEFAULT_BUFFER))
    @handle("c-h", filter=has_focus(DEFAULT_BUFFER))
    def _(event: E) -> None:
        """
        Space: remove line from default pane.
        """
        b = event.current_buffer
        line_no = b.document.cursor_position_row - history_mapping.result_line_offset

        if line_no >= 0:
            try:
                history_lineno = sorted(history_mapping.selected_lines)[line_no]
            except IndexError:
                pass  # When `selected_lines` is an empty set.
            else:
                history_mapping.selected_lines.remove(history_lineno)

            history_mapping.update_default_buffer()

    help_focussed = has_focus(history.help_buffer)
    main_buffer_focussed = has_focus(history.history_buffer) | has_focus(
        history.default_buffer
    )

    @handle("tab", filter=main_buffer_focussed)
    @handle("c-x", filter=main_buffer_focussed, eager=True)
    # Eager: ignore the Emacs [Ctrl-X Ctrl-X] binding.
    @handle("c-w", filter=main_buffer_focussed)
    def _(event: E) -> None:
        "Select other window."
        _select_other_window(history)

    @handle("f4")
    def _(event: E) -> None:
        "Switch between Emacs/Vi mode."
        python_input.vi_mode = not python_input.vi_mode

    @handle("f1")
    def _(event: E) -> None:
        "Display/hide help."
        _toggle_help(history)

    @handle("enter", filter=help_focussed)
    @handle("c-c", filter=help_focussed)
    @handle("c-g", filter=help_focussed)
    @handle("escape", filter=help_focussed)
    def _(event: E) -> None:
        "Leave help."
        event.app.layout.focus_previous()

    @handle("q", filter=main_buffer_focussed)
    @handle("f3", filter=main_buffer_focussed)
    @handle("c-c", filter=main_buffer_focussed)
    @handle("c-g", filter=main_buffer_focussed)
    def _(event: E) -> None:
        "Cancel and go back."
        event.app.exit(result=None)

    @handle("enter", filter=main_buffer_focussed)
    def _(event: E) -> None:
        "Accept input."
        event.app.exit(result=history.default_buffer.text)

    enable_system_bindings = Condition(lambda: python_input.enable_system_bindings)

    @handle("c-z", filter=enable_system_bindings)
    def _(event: E) -> None:
        "Suspend to background."
        event.app.suspend_to_background()

    return bindings


class PythonHistory:
    def __init__(self, python_input: PythonInput, original_document: Document) -> None:
        """
        Create an `Application` for the history screen.
        This has to be run as a sub application of `python_input`.

        When this application runs and returns, it returns the selected lines.
        """
        self.python_input = python_input

        history_mapping = HistoryMapping(self, python_input.history, original_document)
        self.history_mapping = history_mapping

        document = Document(history_mapping.concatenated_history)
        document = Document(
            document.text,
            cursor_position=document.cursor_position
            + document.get_start_of_line_position(),
        )

        def accept_handler(buffer: Buffer) -> bool:
            get_app().exit(result=self.default_buffer.text)
            return False

        self.history_buffer = Buffer(
            document=document,
            on_cursor_position_changed=self._history_buffer_pos_changed,
            accept_handler=accept_handler,
            read_only=True,
        )

        self.default_buffer = Buffer(
            name=DEFAULT_BUFFER,
            document=history_mapping.get_new_document(),
            on_cursor_position_changed=self._default_buffer_pos_changed,
            read_only=True,
        )

        self.help_buffer = Buffer(document=Document(HELP_TEXT, 0), read_only=True)

        self.history_layout = HistoryLayout(self)

        self.app: Application[str] = Application(
            layout=self.history_layout.layout,
            full_screen=True,
            style=python_input._current_style,
            mouse_support=Condition(lambda: python_input.enable_mouse_support),
            key_bindings=create_key_bindings(self, python_input, history_mapping),
        )

    def _default_buffer_pos_changed(self, _: Buffer) -> None:
        """When the cursor changes in the default buffer. Synchronize with
        history buffer."""
        # Only when this buffer has the focus.
        if self.app.current_buffer == self.default_buffer:
            try:
                line_no = (
                    self.default_buffer.document.cursor_position_row
                    - self.history_mapping.result_line_offset
                )

                if line_no < 0:  # When the cursor is above the inserted region.
                    raise IndexError

                history_lineno = sorted(self.history_mapping.selected_lines)[line_no]
            except IndexError:
                pass
            else:
                self.history_buffer.cursor_position = (
                    self.history_buffer.document.translate_row_col_to_index(
                        history_lineno, 0
                    )
                )

    def _history_buffer_pos_changed(self, _: Buffer) -> None:
        """When the cursor changes in the history buffer. Synchronize."""
        # Only when this buffer has the focus.
        if self.app.current_buffer == self.history_buffer:
            line_no = self.history_buffer.document.cursor_position_row

            if line_no in self.history_mapping.selected_lines:
                default_lineno = (
                    sorted(self.history_mapping.selected_lines).index(line_no)
                    + self.history_mapping.result_line_offset
                )

                self.default_buffer.cursor_position = (
                    self.default_buffer.document.translate_row_col_to_index(
                        default_lineno, 0
                    )
                )
