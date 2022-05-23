#!/usr/bin/env python

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import is_searching, to_filter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.search import SearchDirection, do_incremental_search, start_search, stop_search

from hummingbot.client.ui.scroll_handlers import scroll_down, scroll_up
from hummingbot.client.ui.style import reset_style
from hummingbot.core.utils.async_utils import safe_ensure_future


def load_key_bindings(hb) -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("c-c", "c-c")
    def exit_(event):
        hb.app.log("\n[Double CTRL + C] keyboard exit")
        safe_ensure_future(hb.exit_loop())

    @bindings.add("c-x")
    def stop_configuration(event):
        hb.app.log("\n[CTRL + X] Exiting config...")
        hb.app.to_stop_config = True
        hb.app.pending_input = " "
        hb.app.input_event.set()
        hb.app.change_prompt(prompt=">>> ")
        hb.placeholder_mode = False
        hb.app.hide_input = False

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

    @bindings.add("c-d")
    def scroll_down_output(event):
        event.app.layout.current_window = hb.app.output_field.window
        event.app.layout.focus = hb.app.output_field.buffer
        scroll_down(event, hb.app.output_field.window, hb.app.output_field.buffer)
        event.app.layout.current_window = hb.app.input_field.window
        event.app.layout.focus = hb.app.input_field.buffer

    @bindings.add("c-e")
    def scroll_up_output(event):
        event.app.layout.current_window = hb.app.output_field.window
        event.app.layout.focus = hb.app.output_field.buffer
        scroll_up(event, hb.app.output_field.window, hb.app.output_field.buffer)
        event.app.layout.current_window = hb.app.input_field.window
        event.app.layout.focus = hb.app.input_field.buffer

    @bindings.add("escape")
    def stop_live_update(event):
        hb.app.live_updates = False

    @bindings.add("c-r")
    def do_reset_style(event):
        hb.app.app.style = reset_style(hb.client_config_map)

    @bindings.add("c-t")
    def toggle_logs(event):
        hb.app.toggle_right_pane()

    @bindings.add('c-b')
    def do_tab_navigate_left(event):
        hb.app.tab_navigate_left()

    @bindings.add('c-n')
    def do_tab_navigate_right(event):
        hb.app.tab_navigate_right()

    return bindings
