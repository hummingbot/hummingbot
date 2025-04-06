from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import (
    Condition,
    emacs_insert_mode,
    emacs_mode,
    has_focus,
    has_selection,
    vi_insert_mode,
)
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys

from .utils import document_is_multiline_python

if TYPE_CHECKING:
    from .python_input import PythonInput

__all__ = [
    "load_python_bindings",
    "load_sidebar_bindings",
    "load_confirm_exit_bindings",
]

E = KeyPressEvent


@Condition
def tab_should_insert_whitespace() -> bool:
    """
    When the 'tab' key is pressed with only whitespace character before the
    cursor, do autocompletion. Otherwise, insert indentation.

    Except for the first character at the first line. Then always do a
    completion. It doesn't make sense to start the first line with
    indentation.
    """
    b = get_app().current_buffer
    before_cursor = b.document.current_line_before_cursor

    return bool(b.text and (not before_cursor or before_cursor.isspace()))


def load_python_bindings(python_input: PythonInput) -> KeyBindings:
    """
    Custom key bindings.
    """
    bindings = KeyBindings()

    sidebar_visible = Condition(lambda: python_input.show_sidebar)
    handle = bindings.add

    @handle("c-l")
    def _(event: E) -> None:
        """
        Clear whole screen and render again -- also when the sidebar is visible.
        """
        event.app.renderer.clear()

    @handle("c-z")
    def _(event: E) -> None:
        """
        Suspend.
        """
        if python_input.enable_system_bindings:
            event.app.suspend_to_background()

    # Delete word before cursor, but use all Python symbols as separators
    # (WORD=False).
    handle("c-w")(get_by_name("backward-kill-word"))

    @handle("f2")
    def _(event: E) -> None:
        """
        Show/hide sidebar.
        """
        python_input.show_sidebar = not python_input.show_sidebar
        if python_input.show_sidebar:
            event.app.layout.focus(python_input.ptpython_layout.sidebar)
        else:
            event.app.layout.focus_last()

    @handle("f3")
    def _(event: E) -> None:
        """
        Select from the history.
        """
        python_input.enter_history()

    @handle("f4")
    def _(event: E) -> None:
        """
        Toggle between Vi and Emacs mode.
        """
        python_input.vi_mode = not python_input.vi_mode

    @handle("f6")
    def _(event: E) -> None:
        """
        Enable/Disable paste mode.
        """
        python_input.paste_mode = not python_input.paste_mode

    @handle(
        "tab", filter=~sidebar_visible & ~has_selection & tab_should_insert_whitespace
    )
    def _(event: E) -> None:
        """
        When tab should insert whitespace, do that instead of completion.
        """
        event.app.current_buffer.insert_text("    ")

    @Condition
    def is_multiline() -> bool:
        return document_is_multiline_python(python_input.default_buffer.document)

    @handle(
        "enter",
        filter=~sidebar_visible
        & ~has_selection
        & (vi_insert_mode | emacs_insert_mode)
        & has_focus(DEFAULT_BUFFER)
        & ~is_multiline,
    )
    @handle(Keys.Escape, Keys.Enter, filter=~sidebar_visible & emacs_mode)
    def _(event: E) -> None:
        """
        Accept input (for single line input).
        """
        b = event.current_buffer

        if b.validate():
            # When the cursor is at the end, and we have an empty line:
            # drop the empty lines, but return the value.
            b.document = Document(
                text=b.text.rstrip(), cursor_position=len(b.text.rstrip())
            )

            b.validate_and_handle()

    @handle(
        "enter",
        filter=~sidebar_visible
        & ~has_selection
        & (vi_insert_mode | emacs_insert_mode)
        & has_focus(DEFAULT_BUFFER)
        & is_multiline,
    )
    def _(event: E) -> None:
        """
        Behaviour of the Enter key.

        Auto indent after newline/Enter.
        (When not in Vi navigation mode, and when multiline is enabled.)
        """
        b = event.current_buffer
        empty_lines_required = python_input.accept_input_on_enter or 10000

        def at_the_end(b: Buffer) -> bool:
            """we consider the cursor at the end when there is no text after
            the cursor, or only whitespace."""
            text = b.document.text_after_cursor
            return text == "" or (text.isspace() and "\n" not in text)

        if python_input.paste_mode:
            # In paste mode, always insert text.
            b.insert_text("\n")

        elif at_the_end(b) and b.document.text.replace(" ", "").endswith(
            "\n" * (empty_lines_required - 1)
        ):
            # When the cursor is at the end, and we have an empty line:
            # drop the empty lines, but return the value.
            if b.validate():
                b.document = Document(
                    text=b.text.rstrip(), cursor_position=len(b.text.rstrip())
                )

                b.validate_and_handle()
        else:
            auto_newline(b)

    @handle(
        "c-d",
        filter=~sidebar_visible
        & has_focus(python_input.default_buffer)
        & Condition(
            lambda:
            # The current buffer is empty.
            not get_app().current_buffer.text
        ),
    )
    def _(event: E) -> None:
        """
        Override Control-D exit, to ask for confirmation.
        """
        if python_input.confirm_exit:
            # Show exit confirmation and focus it (focusing is important for
            # making sure the default buffer key bindings are not active).
            python_input.show_exit_confirmation = True
            python_input.app.layout.focus(
                python_input.ptpython_layout.exit_confirmation
            )
        else:
            event.app.exit(exception=EOFError)

    @handle("c-c", filter=has_focus(python_input.default_buffer))
    def _(event: E) -> None:
        "Abort when Control-C has been pressed."
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    return bindings


def load_sidebar_bindings(python_input: PythonInput) -> KeyBindings:
    """
    Load bindings for the navigation in the sidebar.
    """
    bindings = KeyBindings()

    handle = bindings.add
    sidebar_visible = Condition(lambda: python_input.show_sidebar)

    @handle("up", filter=sidebar_visible)
    @handle("c-p", filter=sidebar_visible)
    @handle("k", filter=sidebar_visible)
    def _(event: E) -> None:
        "Go to previous option."
        python_input.selected_option_index = (
            python_input.selected_option_index - 1
        ) % python_input.option_count

    @handle("down", filter=sidebar_visible)
    @handle("c-n", filter=sidebar_visible)
    @handle("j", filter=sidebar_visible)
    def _(event: E) -> None:
        "Go to next option."
        python_input.selected_option_index = (
            python_input.selected_option_index + 1
        ) % python_input.option_count

    @handle("right", filter=sidebar_visible)
    @handle("l", filter=sidebar_visible)
    @handle(" ", filter=sidebar_visible)
    def _(event: E) -> None:
        "Select next value for current option."
        option = python_input.selected_option
        option.activate_next()

    @handle("left", filter=sidebar_visible)
    @handle("h", filter=sidebar_visible)
    def _(event: E) -> None:
        "Select previous value for current option."
        option = python_input.selected_option
        option.activate_previous()

    @handle("c-c", filter=sidebar_visible)
    @handle("c-d", filter=sidebar_visible)
    @handle("c-d", filter=sidebar_visible)
    @handle("enter", filter=sidebar_visible)
    @handle("escape", filter=sidebar_visible)
    def _(event: E) -> None:
        "Hide sidebar."
        python_input.show_sidebar = False
        event.app.layout.focus_last()

    return bindings


def load_confirm_exit_bindings(python_input: PythonInput) -> KeyBindings:
    """
    Handle yes/no key presses when the exit confirmation is shown.
    """
    bindings = KeyBindings()

    handle = bindings.add
    confirmation_visible = Condition(lambda: python_input.show_exit_confirmation)

    @handle("y", filter=confirmation_visible)
    @handle("Y", filter=confirmation_visible)
    @handle("enter", filter=confirmation_visible)
    @handle("c-d", filter=confirmation_visible)
    def _(event: E) -> None:
        """
        Really quit.
        """
        event.app.exit(exception=EOFError, style="class:exiting")

    @handle(Keys.Any, filter=confirmation_visible)
    def _(event: E) -> None:
        """
        Cancel exit.
        """
        python_input.show_exit_confirmation = False
        python_input.app.layout.focus_previous()

    return bindings


def auto_newline(buffer: Buffer) -> None:
    r"""
    Insert \n at the cursor position. Also add necessary padding.
    """
    insert_text = buffer.insert_text

    if buffer.document.current_line_after_cursor:
        # When we are in the middle of a line. Always insert a newline.
        insert_text("\n")
    else:
        # Go to new line, but also add indentation.
        current_line = buffer.document.current_line_before_cursor.rstrip()
        insert_text("\n")

        # Unident if the last line ends with 'pass', remove four spaces.
        unindent = current_line.rstrip().endswith(" pass")

        # Copy whitespace from current line
        current_line2 = current_line[4:] if unindent else current_line

        for c in current_line2:
            if c.isspace():
                insert_text(c)
            else:
                break

        # If the last line ends with a colon, add four extra spaces.
        if current_line[-1:] == ":":
            for x in range(4):
                insert_text(" ")
