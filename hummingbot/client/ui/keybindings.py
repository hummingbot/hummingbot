#!/usr/bin/env python

import asyncio
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application.current import get_app
from prompt_toolkit.search import start_search, stop_search


def load_key_bindings(hb) -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("c-c", "c-c")
    def _(event):
        hb.app.log("\n[Double CTRL + C] keyboard exit")
        asyncio.ensure_future(hb.exit())

    @bindings.add("c-s")
    def _(event):
        hb.app.log("\n[CTRL + S] Status")
        hb.status()

    @bindings.add("c-f")
    def _(event):
        start_search(hb.app.log_field.control)

    @bindings.add("c-w")
    def _(event):
        stop_search(hb.app.log_field.control)
        hb.app.input_field.buffer.focus()

    @bindings.add("c-d")
    def _(event):
        search_state = get_app().current_search_state
        text_field = hb.app.log_field.control
        cursor_position = text_field.buffer.get_search_position(
            search_state, include_current_position=False)
        text_field.buffer.cursor_position = cursor_position

    return bindings
