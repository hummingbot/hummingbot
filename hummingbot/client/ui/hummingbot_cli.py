#!/usr/bin/env python

import asyncio
from typing import Callable
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import Application
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.document import Document
from prompt_toolkit.eventloop import use_asyncio_event_loop
from prompt_toolkit.layout.processors import BeforeInput, PasswordProcessor
from prompt_toolkit.completion import Completer

from hummingbot.client.ui.layout import (
    create_input_field,
    create_log_field,
    create_output_field,
    create_search_field,
    generate_layout,
)
from hummingbot.client.ui.style import load_style


class HummingbotCLI:
    def __init__(self,
                 input_handler: Callable,
                 bindings: KeyBindings,
                 completer: Completer):
        use_asyncio_event_loop()
        self.search_field = create_search_field()
        self.input_field = create_input_field(completer=completer)
        self.output_field = create_output_field()
        self.log_field = create_log_field(self.search_field)
        self.layout = generate_layout(self.input_field, self.output_field, self.log_field, self.search_field)

        self.bindings = bindings
        self.input_handler = input_handler
        self.input_field.accept_handler = self.accept
        self.app = Application(layout=self.layout, full_screen=True, key_bindings=self.bindings, style=load_style(),
                               mouse_support=True, clipboard=PyperclipClipboard())

        # settings
        self.prompt_text = ">>> "
        self.pending_input = None
        self.input_event = None
        self.hide_input = False

    async def run(self):
        await self.app.run_async().to_asyncio_future()

    def accept(self, buff):
        self.pending_input = self.input_field.text.strip()

        if self.input_event:
            self.input_event.set()

        try:
            if self.hide_input:
                output = ''
            else:
                output = '\n>>>  {}'.format(self.input_field.text,)
                self.input_field.buffer.append_to_history()
        except BaseException as e:
            output = str(e)

        self.log(output)
        self.input_handler(self.input_field.text)

    def clear_input(self):
        self.pending_input = None

    def log(self, text: str):
        self.output_field.log(text)

    def change_prompt(self, prompt: str, is_password: bool = False):
        self.prompt_text = prompt
        processors = []
        if is_password:
            processors.append(PasswordProcessor())
        processors.append(BeforeInput(prompt))
        self.input_field.control.input_processors = processors

    async def prompt(self, prompt: str, is_password: bool = False) -> str:
        self.change_prompt(prompt, is_password)
        self.app.invalidate()
        self.input_event = asyncio.Event()
        await self.input_event.wait()

        temp = self.pending_input
        self.clear_input()
        self.input_event = None

        if is_password:
            masked_string = "*" * len(temp)
            self.log(f"{prompt}{masked_string}")
        else:
            self.log(f"{prompt}{temp}")
        return temp

    def set_text(self, new_text: str):
        self.input_field.document = Document(text=new_text, cursor_position=len(new_text))

    def toggle_hide_input(self):
        self.hide_input = not self.hide_input

    def exit(self):
        self.app.exit()


