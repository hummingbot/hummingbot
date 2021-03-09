from __future__ import unicode_literals
import six
from collections import deque
from typing import (
    List,
    Deque,
)

from prompt_toolkit.auto_suggest import DynamicAutoSuggest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import DynamicCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.widgets.toolbars import SearchToolbar
from prompt_toolkit.filters import (
    to_filter,
    Condition,
    is_true,
    has_focus,
    is_done,
)
from prompt_toolkit.layout.containers import Window, WindowAlign
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.margins import (
    ScrollbarMargin,
    NumberedMargin,
)
from prompt_toolkit.layout.processors import (
    PasswordProcessor,
    ConditionalProcessor,
    BeforeInput,
    AppendAutoSuggestion,
)
from prompt_toolkit.lexers import DynamicLexer


class CustomBuffer(Buffer):
    def validate_and_handle(self):
        valid = self.validate(set_cursor=True)
        if valid:
            if self.accept_handler:
                keep_text = self.accept_handler(self)
            else:
                keep_text = False
            if not keep_text:
                self.reset()


class CustomTextArea:
    def __init__(self, text='', multiline=True, password=False,
                 lexer=None, auto_suggest=None, completer=None,
                 complete_while_typing=True, accept_handler=None, history=None,
                 focusable=True, focus_on_click=False, wrap_lines=True,
                 read_only=False, width=None, height=None,
                 dont_extend_height=False, dont_extend_width=False,
                 line_numbers=False, get_line_prefix=None, scrollbar=False,
                 style='', search_field=None, preview_search=True, prompt='',
                 input_processors=None, max_line_count=1000, initial_text="", align=WindowAlign.LEFT):
        assert isinstance(text, six.text_type)
        assert search_field is None or isinstance(search_field, SearchToolbar)

        if search_field is None:
            search_control = None
        elif isinstance(search_field, SearchToolbar):
            search_control = search_field.control

        if input_processors is None:
            input_processors = []

        # Writeable attributes.
        self.completer = completer
        self.complete_while_typing = complete_while_typing
        self.lexer = lexer
        self.auto_suggest = auto_suggest
        self.read_only = read_only
        self.wrap_lines = wrap_lines
        self.max_line_count = max_line_count

        self.buffer = CustomBuffer(
            document=Document(text, 0),
            multiline=multiline,
            read_only=Condition(lambda: is_true(self.read_only)),
            completer=DynamicCompleter(lambda: self.completer),
            complete_while_typing=Condition(
                lambda: is_true(self.complete_while_typing)),
            auto_suggest=DynamicAutoSuggest(lambda: self.auto_suggest),
            accept_handler=accept_handler,
            history=history)

        self.control = BufferControl(
            buffer=self.buffer,
            lexer=DynamicLexer(lambda: self.lexer),
            input_processors=[
                ConditionalProcessor(
                    AppendAutoSuggestion(),
                    has_focus(self.buffer) & ~is_done),
                ConditionalProcessor(
                    processor=PasswordProcessor(),
                    filter=to_filter(password)
                ),
                BeforeInput(prompt, style='class:text-area.prompt'),
            ] + input_processors,
            search_buffer_control=search_control,
            preview_search=preview_search,
            focusable=focusable,
            focus_on_click=focus_on_click)

        if multiline:
            if scrollbar:
                right_margins = [ScrollbarMargin(display_arrows=True)]
            else:
                right_margins = []
            if line_numbers:
                left_margins = [NumberedMargin()]
            else:
                left_margins = []
        else:
            left_margins = []
            right_margins = []

        style = 'class:text-area ' + style

        self.window = Window(
            height=height,
            width=width,
            dont_extend_height=dont_extend_height,
            dont_extend_width=dont_extend_width,
            content=self.control,
            style=style,
            wrap_lines=Condition(lambda: is_true(self.wrap_lines)),
            left_margins=left_margins,
            right_margins=right_margins,
            get_line_prefix=get_line_prefix,
            align=align)

        self.log_lines: Deque[str] = deque()
        self.log(initial_text)

    @property
    def text(self):
        """
        The `Buffer` text.
        """
        return self.buffer.text

    @text.setter
    def text(self, value):
        self.buffer.set_document(Document(value, 0), bypass_readonly=True)

    @property
    def document(self):
        """
        The `Buffer` document (text + cursor position).
        """
        return self.buffer.document

    @document.setter
    def document(self, value):
        self.buffer.document = value

    @property
    def accept_handler(self):
        """
        The accept handler. Called when the user accepts the input.
        """
        return self.buffer.accept_handler

    @accept_handler.setter
    def accept_handler(self, value):
        self.buffer.accept_handler = value

    def __pt_container__(self):
        return self.window

    def log(self, text: str, save_log: bool = True, silent: bool = False):
        # Getting the max width of the window area
        if self.window.render_info is None:
            max_width = 100
        else:
            max_width = self.window.render_info.window_width - 2

        # remove simple formatting tags used by telegram
        repls = (('<b>', ''), ('</b>', ''), ('<pre>', ''), ('</pre>', ''))
        for r in repls:
            text = text.replace(*r)

        # Split the string into multiple lines if there is a "\n" or if the string exceeds max window width
        # This operation should not be too expensive because only the newly added lines are processed
        new_lines_raw: List[str] = str(text).split('\n')
        new_lines = []
        for line in new_lines_raw:
            while len(line) > max_width:
                new_lines.append(line[0:max_width])
                line = line[max_width:]
            new_lines.append(line)

        if save_log:
            self.log_lines.extend(new_lines)
            while len(self.log_lines) > self.max_line_count:
                self.log_lines.popleft()
            new_text: str = "\n".join(self.log_lines)
        else:
            new_text: str = "\n".join(new_lines)
        if not silent:
            self.buffer.document = Document(text=new_text, cursor_position=len(new_text))
