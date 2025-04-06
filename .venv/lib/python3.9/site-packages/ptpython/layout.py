"""
Creation of the `Layout` instance for the Python input/REPL.
"""

from __future__ import annotations

import platform
import sys
from enum import Enum
from inspect import _ParameterKind as ParameterKind
from typing import TYPE_CHECKING, Any

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER
from prompt_toolkit.filters import (
    Condition,
    has_focus,
    is_done,
    renderer_height_is_known,
)
from prompt_toolkit.formatted_text import fragment_list_width, to_formatted_text
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout.containers import (
    AnyContainer,
    ConditionalContainer,
    Container,
    Float,
    FloatContainer,
    HSplit,
    ScrollOffsets,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import AnyDimension, Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import PromptMargin
from prompt_toolkit.layout.menus import CompletionsMenu, MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import (
    AppendAutoSuggestion,
    ConditionalProcessor,
    DisplayMultipleCursors,
    HighlightIncrementalSearchProcessor,
    HighlightMatchingBracketProcessor,
    HighlightSelectionProcessor,
    Processor,
    TabsProcessor,
)
from prompt_toolkit.lexers import Lexer, SimpleLexer
from prompt_toolkit.mouse_events import MouseEvent
from prompt_toolkit.selection import SelectionType
from prompt_toolkit.widgets.toolbars import (
    ArgToolbar,
    CompletionsToolbar,
    SearchToolbar,
    SystemToolbar,
    ValidationToolbar,
)

from .filters import HasSignature, ShowDocstring, ShowSidebar, ShowSignature
from .prompt_style import PromptStyle
from .utils import if_mousedown

if TYPE_CHECKING:
    from .python_input import OptionCategory, PythonInput

__all__ = ["PtPythonLayout", "CompletionVisualisation"]


class CompletionVisualisation(Enum):
    "Visualisation method for the completions."

    NONE = "none"
    POP_UP = "pop-up"
    MULTI_COLUMN = "multi-column"
    TOOLBAR = "toolbar"


def show_completions_toolbar(python_input: PythonInput) -> Condition:
    return Condition(
        lambda: python_input.completion_visualisation == CompletionVisualisation.TOOLBAR
    )


def show_completions_menu(python_input: PythonInput) -> Condition:
    return Condition(
        lambda: python_input.completion_visualisation == CompletionVisualisation.POP_UP
    )


def show_multi_column_completions_menu(python_input: PythonInput) -> Condition:
    return Condition(
        lambda: python_input.completion_visualisation
        == CompletionVisualisation.MULTI_COLUMN
    )


def python_sidebar(python_input: PythonInput) -> Window:
    """
    Create the `Layout` for the sidebar with the configurable options.
    """

    def get_text_fragments() -> StyleAndTextTuples:
        tokens: StyleAndTextTuples = []

        def append_category(category: OptionCategory[Any]) -> None:
            tokens.extend(
                [
                    ("class:sidebar", "  "),
                    ("class:sidebar.title", "   %-36s" % category.title),
                    ("class:sidebar", "\n"),
                ]
            )

        def append(index: int, label: str, status: str) -> None:
            selected = index == python_input.selected_option_index

            @if_mousedown
            def select_item(mouse_event: MouseEvent) -> None:
                python_input.selected_option_index = index

            @if_mousedown
            def goto_next(mouse_event: MouseEvent) -> None:
                "Select item and go to next value."
                python_input.selected_option_index = index
                option = python_input.selected_option
                option.activate_next()

            sel = ",selected" if selected else ""

            tokens.append(("class:sidebar" + sel, " >" if selected else "  "))
            tokens.append(("class:sidebar.label" + sel, "%-24s" % label, select_item))
            tokens.append(("class:sidebar.status" + sel, " ", select_item))
            tokens.append(("class:sidebar.status" + sel, f"{status}", goto_next))

            if selected:
                tokens.append(("[SetCursorPosition]", ""))

            tokens.append(
                ("class:sidebar.status" + sel, " " * (13 - len(status)), goto_next)
            )
            tokens.append(("class:sidebar", "<" if selected else ""))
            tokens.append(("class:sidebar", "\n"))

        i = 0
        for category in python_input.options:
            append_category(category)

            for option in category.options:
                append(i, option.title, str(option.get_current_value()))
                i += 1

        tokens.pop()  # Remove last newline.

        return tokens

    class Control(FormattedTextControl):
        def move_cursor_down(self) -> None:
            python_input.selected_option_index += 1

        def move_cursor_up(self) -> None:
            python_input.selected_option_index -= 1

    return Window(
        Control(get_text_fragments),
        style="class:sidebar",
        width=Dimension.exact(43),
        height=Dimension(min=3),
        scroll_offsets=ScrollOffsets(top=1, bottom=1),
    )


def python_sidebar_navigation(python_input: PythonInput) -> Window:
    """
    Create the `Layout` showing the navigation information for the sidebar.
    """

    def get_text_fragments() -> StyleAndTextTuples:
        # Show navigation info.
        return [
            ("class:sidebar", "    "),
            ("class:sidebar.key", "[Arrows]"),
            ("class:sidebar", " "),
            ("class:sidebar.description", "Navigate"),
            ("class:sidebar", " "),
            ("class:sidebar.key", "[Enter]"),
            ("class:sidebar", " "),
            ("class:sidebar.description", "Hide menu"),
        ]

    return Window(
        FormattedTextControl(get_text_fragments),
        style="class:sidebar",
        width=Dimension.exact(43),
        height=Dimension.exact(1),
    )


def python_sidebar_help(python_input: PythonInput) -> Container:
    """
    Create the `Layout` for the help text for the current item in the sidebar.
    """
    token = "class:sidebar.helptext"

    def get_current_description() -> str:
        """
        Return the description of the selected option.
        """
        i = 0
        for category in python_input.options:
            for option in category.options:
                if i == python_input.selected_option_index:
                    return option.description
                i += 1
        return ""

    def get_help_text() -> StyleAndTextTuples:
        return [(token, get_current_description())]

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_help_text),
            style=token,
            height=Dimension(min=3),
            wrap_lines=True,
        ),
        filter=ShowSidebar(python_input)
        & Condition(lambda: python_input.show_sidebar_help)
        & ~is_done,
    )


def signature_toolbar(python_input: PythonInput) -> Container:
    """
    Return the `Layout` for the signature.
    """

    def get_text_fragments() -> StyleAndTextTuples:
        result: StyleAndTextTuples = []
        append = result.append
        Signature = "class:signature-toolbar"

        if python_input.signatures:
            sig = python_input.signatures[0]  # Always take the first one.

            append((Signature, " "))
            try:
                append((Signature, sig.name))
            except IndexError:
                # Workaround for #37: https://github.com/jonathanslenders/python-prompt-toolkit/issues/37
                # See also: https://github.com/davidhalter/jedi/issues/490
                return []

            append((Signature + ",operator", "("))

            got_positional_only = False
            got_keyword_only = False

            for i, p in enumerate(sig.parameters):
                # Detect transition between positional-only and not positional-only.
                if p.kind == ParameterKind.POSITIONAL_ONLY:
                    got_positional_only = True
                if got_positional_only and p.kind != ParameterKind.POSITIONAL_ONLY:
                    got_positional_only = False
                    append((Signature, "/"))
                    append((Signature + ",operator", ", "))

                if not got_keyword_only and p.kind == ParameterKind.KEYWORD_ONLY:
                    got_keyword_only = True
                    append((Signature, "*"))
                    append((Signature + ",operator", ", "))

                sig_index = getattr(sig, "index", 0)

                if i == sig_index:
                    # Note: we use `_Param.description` instead of
                    #       `_Param.name`, that way we also get the '*' before args.
                    append((Signature + ",current-name", p.description))
                else:
                    append((Signature, p.description))

                if p.default:
                    # NOTE: For the jedi-based completion, the default is
                    #       currently still part of the name.
                    append((Signature, f"={p.default}"))

                append((Signature + ",operator", ", "))

            if sig.parameters:
                # Pop last comma
                result.pop()

            append((Signature + ",operator", ")"))
            append((Signature, " "))
        return result

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_text_fragments), height=Dimension.exact(1)
        ),
        # Show only when there is a signature
        filter=HasSignature(python_input)
        &
        # Signature needs to be shown.
        ShowSignature(python_input)
        &
        # And no sidebar is visible.
        ~ShowSidebar(python_input)
        &
        # Not done yet.
        ~is_done,
    )


class PythonPromptMargin(PromptMargin):
    """
    Create margin that displays the prompt.
    It shows something like "In [1]:".
    """

    def __init__(self, python_input: PythonInput) -> None:
        self.python_input = python_input

        def get_prompt_style() -> PromptStyle:
            return python_input.all_prompt_styles[python_input.prompt_style]

        def get_prompt() -> StyleAndTextTuples:
            return to_formatted_text(get_prompt_style().in_prompt())

        def get_continuation(
            width: int, line_number: int, is_soft_wrap: bool
        ) -> StyleAndTextTuples:
            if python_input.show_line_numbers and not is_soft_wrap:
                text = ("%i " % (line_number + 1)).rjust(width)
                return [("class:line-number", text)]
            else:
                return to_formatted_text(get_prompt_style().in2_prompt(width))

        super().__init__(get_prompt, get_continuation)


def status_bar(python_input: PythonInput) -> Container:
    """
    Create the `Layout` for the status bar.
    """
    TB = "class:status-toolbar"

    @if_mousedown
    def toggle_paste_mode(mouse_event: MouseEvent) -> None:
        python_input.paste_mode = not python_input.paste_mode

    @if_mousedown
    def enter_history(mouse_event: MouseEvent) -> None:
        python_input.enter_history()

    def get_text_fragments() -> StyleAndTextTuples:
        python_buffer = python_input.default_buffer

        result: StyleAndTextTuples = []
        append = result.append

        append((TB, " "))
        result.extend(get_inputmode_fragments(python_input))
        append((TB, " "))

        # Position in history.
        append(
            (
                TB,
                "%i/%i "
                % (python_buffer.working_index + 1, len(python_buffer._working_lines)),
            )
        )

        # Shortcuts.
        app = get_app()
        if (
            not python_input.vi_mode
            and app.current_buffer == python_input.search_buffer
        ):
            append((TB, "[Ctrl-G] Cancel search [Enter] Go to this position."))
        elif bool(app.current_buffer.selection_state) and not python_input.vi_mode:
            # Emacs cut/copy keys.
            append((TB, "[Ctrl-W] Cut [Meta-W] Copy [Ctrl-Y] Paste [Ctrl-G] Cancel"))
        else:
            result.extend(
                [
                    (TB + " class:status-toolbar.key", "[F3]", enter_history),
                    (TB, " History ", enter_history),
                    (TB + " class:status-toolbar.key", "[F6]", toggle_paste_mode),
                    (TB, " ", toggle_paste_mode),
                ]
            )

            if python_input.paste_mode:
                append(
                    (TB + " class:paste-mode-on", "Paste mode (on)", toggle_paste_mode)
                )
            else:
                append((TB, "Paste mode", toggle_paste_mode))

        return result

    return ConditionalContainer(
        content=Window(content=FormattedTextControl(get_text_fragments), style=TB),
        filter=~is_done
        & renderer_height_is_known
        & Condition(
            lambda: python_input.show_status_bar
            and not python_input.show_exit_confirmation
        ),
    )


def get_inputmode_fragments(python_input: PythonInput) -> StyleAndTextTuples:
    """
    Return current input mode as a list of (token, text) tuples for use in a
    toolbar.
    """
    app = get_app()

    @if_mousedown
    def toggle_vi_mode(mouse_event: MouseEvent) -> None:
        python_input.vi_mode = not python_input.vi_mode

    token = "class:status-toolbar"
    input_mode_t = "class:status-toolbar.input-mode"

    mode = app.vi_state.input_mode
    result: StyleAndTextTuples = []
    append = result.append

    if python_input.title:
        result.extend(to_formatted_text(python_input.title))

    append((input_mode_t, "[F4] ", toggle_vi_mode))

    # InputMode
    if python_input.vi_mode:
        recording_register = app.vi_state.recording_register
        if recording_register:
            append((token, " "))
            append((token + " class:record", f"RECORD({recording_register})"))
            append((token, " - "))

        if app.current_buffer.selection_state is not None:
            if app.current_buffer.selection_state.type == SelectionType.LINES:
                append((input_mode_t, "Vi (VISUAL LINE)", toggle_vi_mode))
            elif app.current_buffer.selection_state.type == SelectionType.CHARACTERS:
                append((input_mode_t, "Vi (VISUAL)", toggle_vi_mode))
                append((token, " "))
            elif app.current_buffer.selection_state.type == SelectionType.BLOCK:
                append((input_mode_t, "Vi (VISUAL BLOCK)", toggle_vi_mode))
                append((token, " "))
        elif mode in (InputMode.INSERT, "vi-insert-multiple"):
            append((input_mode_t, "Vi (INSERT)", toggle_vi_mode))
            append((token, "  "))
        elif mode == InputMode.NAVIGATION:
            append((input_mode_t, "Vi (NAV)", toggle_vi_mode))
            append((token, "     "))
        elif mode == InputMode.REPLACE:
            append((input_mode_t, "Vi (REPLACE)", toggle_vi_mode))
            append((token, " "))
    else:
        if app.emacs_state.is_recording:
            append((token, " "))
            append((token + " class:record", "RECORD"))
            append((token, " - "))

        append((input_mode_t, "Emacs", toggle_vi_mode))
        append((token, " "))

    return result


def show_sidebar_button_info(python_input: PythonInput) -> Container:
    """
    Create `Layout` for the information in the right-bottom corner.
    (The right part of the status bar.)
    """

    @if_mousedown
    def toggle_sidebar(mouse_event: MouseEvent) -> None:
        "Click handler for the menu."
        python_input.show_sidebar = not python_input.show_sidebar

    version = sys.version_info
    tokens: StyleAndTextTuples = [
        ("class:status-toolbar.key", "[F2]", toggle_sidebar),
        ("class:status-toolbar", " Menu", toggle_sidebar),
        ("class:status-toolbar", " - "),
        (
            "class:status-toolbar.python-version",
            "%s %i.%i.%i"
            % (platform.python_implementation(), version[0], version[1], version[2]),
        ),
        ("class:status-toolbar", " "),
    ]
    width = fragment_list_width(tokens)

    def get_text_fragments() -> StyleAndTextTuples:
        # Python version
        return tokens

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_text_fragments),
            style="class:status-toolbar",
            height=Dimension.exact(1),
            width=Dimension.exact(width),
        ),
        filter=~is_done
        & renderer_height_is_known
        & Condition(
            lambda: python_input.show_status_bar
            and not python_input.show_exit_confirmation
        ),
    )


def create_exit_confirmation(
    python_input: PythonInput, style: str = "class:exit-confirmation"
) -> Container:
    """
    Create `Layout` for the exit message.
    """

    def get_text_fragments() -> StyleAndTextTuples:
        # Show "Do you really want to exit?"
        return [
            (style, f"\n {python_input.exit_message} ([y]/n) "),
            ("[SetCursorPosition]", ""),
            (style, "  \n"),
        ]

    visible = ~is_done & Condition(lambda: python_input.show_exit_confirmation)

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_text_fragments, focusable=True), style=style
        ),
        filter=visible,
    )


def meta_enter_message(python_input: PythonInput) -> Container:
    """
    Create the `Layout` for the 'Meta+Enter` message.
    """

    def get_text_fragments() -> StyleAndTextTuples:
        return [("class:accept-message", " [Meta+Enter] Execute ")]

    @Condition
    def extra_condition() -> bool:
        "Only show when..."
        b = python_input.default_buffer

        return (
            python_input.show_meta_enter_message
            and (
                not b.document.is_cursor_at_the_end
                or python_input.accept_input_on_enter is None
            )
            and "\n" in b.text
        )

    visible = ~is_done & has_focus(DEFAULT_BUFFER) & extra_condition

    return ConditionalContainer(
        content=Window(FormattedTextControl(get_text_fragments)), filter=visible
    )


class PtPythonLayout:
    def __init__(
        self,
        python_input: PythonInput,
        lexer: Lexer,
        extra_body: AnyContainer | None = None,
        extra_toolbars: list[AnyContainer] | None = None,
        extra_buffer_processors: list[Processor] | None = None,
        input_buffer_height: AnyDimension | None = None,
    ) -> None:
        D = Dimension
        extra_body_list: list[AnyContainer] = [extra_body] if extra_body else []
        extra_toolbars = extra_toolbars or []

        input_buffer_height = input_buffer_height or D(min=6)

        search_toolbar = SearchToolbar(python_input.search_buffer)

        def create_python_input_window() -> Window:
            def menu_position() -> int | None:
                """
                When there is no autocompletion menu to be shown, and we have a
                signature, set the pop-up position at `bracket_start`.
                """
                b = python_input.default_buffer

                if python_input.signatures:
                    row, col = python_input.signatures[0].bracket_start
                    index = b.document.translate_row_col_to_index(row - 1, col)
                    return index
                return None

            return Window(
                BufferControl(
                    buffer=python_input.default_buffer,
                    search_buffer_control=search_toolbar.control,
                    lexer=lexer,
                    include_default_input_processors=False,
                    input_processors=[
                        ConditionalProcessor(
                            processor=HighlightIncrementalSearchProcessor(),
                            filter=has_focus(SEARCH_BUFFER)
                            | has_focus(search_toolbar.control),
                        ),
                        HighlightSelectionProcessor(),
                        DisplayMultipleCursors(),
                        TabsProcessor(),
                        # Show matching parentheses, but only while editing.
                        ConditionalProcessor(
                            processor=HighlightMatchingBracketProcessor(chars="[](){}"),
                            filter=has_focus(DEFAULT_BUFFER)
                            & ~is_done
                            & Condition(
                                lambda: python_input.highlight_matching_parenthesis
                            ),
                        ),
                        ConditionalProcessor(
                            processor=AppendAutoSuggestion(), filter=~is_done
                        ),
                    ]
                    + (extra_buffer_processors or []),
                    menu_position=menu_position,
                    # Make sure that we always see the result of an reverse-i-search:
                    preview_search=True,
                ),
                left_margins=[PythonPromptMargin(python_input)],
                # Scroll offsets. The 1 at the bottom is important to make sure
                # the cursor is never below the "Press [Meta+Enter]" message
                # which is a float.
                scroll_offsets=ScrollOffsets(bottom=1, left=4, right=4),
                # As long as we're editing, prefer a minimal height of 6.
                height=(
                    lambda: (
                        None
                        if get_app().is_done or python_input.show_exit_confirmation
                        else input_buffer_height
                    )
                ),
                wrap_lines=Condition(lambda: python_input.wrap_lines),
            )

        sidebar = python_sidebar(python_input)
        self.exit_confirmation = create_exit_confirmation(python_input)

        self.root_container = HSplit(
            [
                VSplit(
                    [
                        HSplit(
                            [
                                FloatContainer(
                                    content=HSplit(
                                        [create_python_input_window()] + extra_body_list
                                    ),
                                    floats=[
                                        Float(
                                            xcursor=True,
                                            ycursor=True,
                                            content=HSplit(
                                                [
                                                    signature_toolbar(python_input),
                                                    ConditionalContainer(
                                                        content=CompletionsMenu(
                                                            scroll_offset=(
                                                                lambda: python_input.completion_menu_scroll_offset
                                                            ),
                                                            max_height=12,
                                                        ),
                                                        filter=show_completions_menu(
                                                            python_input
                                                        ),
                                                    ),
                                                    ConditionalContainer(
                                                        content=MultiColumnCompletionsMenu(),
                                                        filter=show_multi_column_completions_menu(
                                                            python_input
                                                        ),
                                                    ),
                                                ]
                                            ),
                                        ),
                                        Float(
                                            left=2,
                                            bottom=1,
                                            content=self.exit_confirmation,
                                        ),
                                        Float(
                                            bottom=0,
                                            right=0,
                                            height=1,
                                            content=meta_enter_message(python_input),
                                            hide_when_covering_content=True,
                                        ),
                                        Float(
                                            bottom=1,
                                            left=1,
                                            right=0,
                                            content=python_sidebar_help(python_input),
                                        ),
                                    ],
                                ),
                                ArgToolbar(),
                                search_toolbar,
                                SystemToolbar(),
                                ValidationToolbar(),
                                ConditionalContainer(
                                    content=CompletionsToolbar(),
                                    filter=show_completions_toolbar(python_input)
                                    & ~is_done,
                                ),
                                # Docstring region.
                                ConditionalContainer(
                                    content=Window(
                                        height=D.exact(1),
                                        char="\u2500",
                                        style="class:separator",
                                    ),
                                    filter=HasSignature(python_input)
                                    & ShowDocstring(python_input)
                                    & ~is_done,
                                ),
                                ConditionalContainer(
                                    content=Window(
                                        BufferControl(
                                            buffer=python_input.docstring_buffer,
                                            lexer=SimpleLexer(style="class:docstring"),
                                            # lexer=PythonLexer,
                                        ),
                                        height=D(max=12),
                                    ),
                                    filter=HasSignature(python_input)
                                    & ShowDocstring(python_input)
                                    & ~is_done,
                                ),
                            ]
                        ),
                        ConditionalContainer(
                            content=HSplit(
                                [
                                    sidebar,
                                    Window(style="class:sidebar,separator", height=1),
                                    python_sidebar_navigation(python_input),
                                ]
                            ),
                            filter=ShowSidebar(python_input) & ~is_done,
                        ),
                    ]
                )
            ]
            + extra_toolbars
            + [
                VSplit(
                    [status_bar(python_input), show_sidebar_button_info(python_input)]
                )
            ]
        )

        self.layout = Layout(self.root_container)
        self.sidebar = sidebar
