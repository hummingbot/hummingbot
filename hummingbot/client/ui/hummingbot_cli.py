#!/usr/bin/env python

import asyncio
from typing import Callable
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import Application
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.document import Document
from prompt_toolkit.layout.processors import BeforeInput, PasswordProcessor
from prompt_toolkit.completion import Completer

from hummingbot.client.ui.layout import (
    create_input_field,
    create_log_field,
    create_output_field,
    create_search_field,
    generate_layout,
    create_timer,
    create_process_monitor,
    create_trade_monitor
)
from hummingbot.client.ui.interface_utils import start_timer, start_process_monitor, start_trade_monitor
from hummingbot.client.ui.style import load_style
import logging


# Monkey patching here as _handle_exception gets the UI hanged into Press ENTER screen mode
def _handle_exception_patch(self, loop, context):
    if "exception" in context:
        logging.getLogger(__name__).error(f"Unhandled error in prompt_toolkit: {context.get('exception')}",
                                          exc_info=True)


Application._handle_exception = _handle_exception_patch


class HummingbotCLI:
    def __init__(self,
                 input_handler: Callable,
                 bindings: KeyBindings,
                 completer: Completer):
        self.search_field = create_search_field()
        self.input_field = create_input_field(completer=completer)
        self.output_field = create_output_field()
        self.log_field = create_log_field(self.search_field)
        self.timer = create_timer()
        self.process_usage = create_process_monitor()
        self.trade_monitor = create_trade_monitor()
        self.layout = generate_layout(self.input_field, self.output_field, self.log_field, self.search_field, self.timer, self.process_usage, self.trade_monitor)
        # add self.to_stop_config to know if cancel is triggered
        self.to_stop_config: bool = False

        self.live_updates = False
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

        # start ui tasks
        loop = asyncio.get_event_loop()
        loop.create_task(start_timer(self.timer))
        loop.create_task(start_process_monitor(self.process_usage))
        loop.create_task(start_trade_monitor(self.trade_monitor))

    async def run(self):
        await self.app.run_async()

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

    def log(self, text: str, save_log: bool = True):
        if save_log:
            if self.live_updates:
                self.output_field.log(text, silent=True)
            else:
                self.output_field.log(text)
        else:
            self.output_field.log(text, save_log=False)

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
