#!/usr/bin/env python

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import (
    is_searching,
    to_filter,
)
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.search import (
    start_search,
    stop_search,
    do_incremental_search,
    SearchDirection,
)

from hummingbot.core.utils.async_utils import safe_ensure_future


def load_key_bindings(hb) -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("c-c", "c-c")
    def exit_(event):
        hb.app.log("\n[Double CTRL + C] keyboard exit")
        safe_ensure_future(hb.exit_loop())

    @bindings.add("c-s")
    def status(event):
        hb.app.log("\n[CTRL + S] Status")
        hb.status()

    @bindings.add("c-f", filter=to_filter(not is_searching()))
    def do_find(event):
        start_search(hb.app.log_field.control)

    @bindings.add("c-f", filter=is_searching)
    def do_exit_find(event):
        stop_search()
        get_app().layout.focus(hb.app.input_field.control)
        get_app().invalidate()

    @bindings.add("c-z")
    def do_undo(event):
        get_app().layout.current_buffer.undo()

    @bindings.add("c-m", filter=is_searching)
    def do_find_next(event):
        do_incremental_search(direction=SearchDirection.FORWARD)

    @bindings.add("c-c")
    def do_copy(event):
        data = get_app().layout.current_buffer.copy_selection()
        get_app().clipboard.set_data(data)

    @bindings.add("c-v")
    def do_paste(event):
        get_app().layout.current_buffer.paste_clipboard_data(get_app().clipboard.get_data())

    @bindings.add("c-a")
    def do_select_all(event):
        current_buffer = get_app().layout.current_buffer
        current_buffer.cursor_position = 0
        current_buffer.start_selection()
        current_buffer.cursor_position = len(current_buffer.text)

    return bindings
