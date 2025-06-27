import asyncio
import logging
import threading
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

from prompt_toolkit.application import Application
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.completion import Completer
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.processors import BeforeInput, PasswordProcessor

from hummingbot import init_logging
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.tab.data_types import CommandTab
from hummingbot.client.ui.interface_utils import start_process_monitor, start_timer, start_trade_monitor
from hummingbot.client.ui.layout import (
    create_input_field,
    create_live_field,
    create_log_field,
    create_log_toggle,
    create_output_field,
    create_process_monitor,
    create_search_field,
    create_tab_button,
    create_timer,
    create_trade_monitor,
    generate_layout,
)
from hummingbot.client.ui.stdout_redirection import patch_stdout
from hummingbot.client.ui.style import load_style
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.pubsub import PubSub
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


# Monkey patching here as _handle_exception gets the UI hanged into Press ENTER screen mode
def _handle_exception_patch(self, loop, context):
    if "exception" in context:
        logging.getLogger(__name__).error(f"Unhandled error in prompt_toolkit: {context.get('exception')}",
                                          exc_info=True)


Application._handle_exception = _handle_exception_patch


class HummingbotCLI(PubSub):
    def __init__(self,
                 client_config_map: ClientConfigAdapter,
                 input_handler: Callable,
                 bindings: KeyBindings,
                 completer: Completer,
                 command_tabs: Dict[str, CommandTab]):
        super().__init__()
        self.client_config_map: Union[ClientConfigAdapter, ClientConfigMap] = client_config_map
        self.command_tabs = command_tabs
        self.search_field = create_search_field()
        self.input_field = create_input_field(completer=completer)
        self.output_field = create_output_field(client_config_map)
        self.log_field = create_log_field(self.search_field)
        self.right_pane_toggle = create_log_toggle(self.toggle_right_pane)
        self.live_field = create_live_field()
        self.log_field_button = create_tab_button("logs", self.log_button_clicked)
        self.timer = create_timer()
        self.process_usage = create_process_monitor()
        self.trade_monitor = create_trade_monitor()
        self.layout, self.layout_components = generate_layout(self.input_field, self.output_field, self.log_field,
                                                              self.right_pane_toggle, self.log_field_button,
                                                              self.search_field, self.timer,
                                                              self.process_usage, self.trade_monitor,
                                                              self.command_tabs)
        # add self.to_stop_config to know if cancel is triggered
        self.to_stop_config: bool = False

        self.live_updates = False
        self.bindings = bindings
        self.input_handler = input_handler
        self.input_field.accept_handler = self.accept
        self.app: Optional[Application] = None

        # settings
        self.prompt_text = ">>> "
        self.pending_input = None
        self.input_event = None
        self.hide_input = False

        # stdout redirection stack
        self._stdout_redirect_context: ExitStack = ExitStack()

        # start ui tasks
        loop = asyncio.get_event_loop()
        loop.create_task(start_timer(self.timer))
        loop.create_task(start_process_monitor(self.process_usage))
        loop.create_task(start_trade_monitor(self.trade_monitor))

    def did_start_ui(self):
        self._stdout_redirect_context.enter_context(patch_stdout(log_field=self.log_field))

        log_level = self.client_config_map.log_level
        init_logging("hummingbot_logs.yml", self.client_config_map, override_log_level=log_level)

        self.trigger_event(HummingbotUIEvent.Start, self)

    async def run(self):
        self.app = Application(
            layout=self.layout,
            full_screen=True,
            key_bindings=self.bindings,
            style=load_style(self.client_config_map),
            mouse_support=True,
            clipboard=PyperclipClipboard(),
        )
        await self.app.run_async(pre_run=self.did_start_ui)
        self._stdout_redirect_context.close()

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

    def toggle_right_pane(self):
        if self.layout_components["pane_right"].filter():
            self.layout_components["pane_right"].filter = lambda: False
            self.layout_components["item_top_toggle"].text = '< log pane'
        else:
            self.layout_components["pane_right"].filter = lambda: True
            self.layout_components["item_top_toggle"].text = '> log pane'

    def log_button_clicked(self):
        for tab in self.command_tabs.values():
            tab.is_selected = False
        self.redraw_app()

    def tab_button_clicked(self, command_name: str):
        for tab in self.command_tabs.values():
            tab.is_selected = False
        self.command_tabs[command_name].is_selected = True
        self.redraw_app()

    def exit(self):
        self.app.exit()

    def redraw_app(self):
        self.layout, self.layout_components = generate_layout(self.input_field, self.output_field, self.log_field,
                                                              self.right_pane_toggle, self.log_field_button,
                                                              self.search_field, self.timer,
                                                              self.process_usage, self.trade_monitor, self.command_tabs)
        self.app.layout = self.layout
        self.app.invalidate()

    def tab_navigate_left(self):
        selected_tabs = [t for t in self.command_tabs.values() if t.is_selected]
        if not selected_tabs:
            return
        selected_tab: CommandTab = selected_tabs[0]
        if selected_tab.tab_index == 1:
            self.log_button_clicked()
        else:
            left_tab = [t for t in self.command_tabs.values() if t.tab_index == selected_tab.tab_index - 1][0]
            self.tab_button_clicked(left_tab.name)

    def tab_navigate_right(self):
        current_tabs = [t for t in self.command_tabs.values() if t.tab_index > 0]
        if not current_tabs:
            return
        selected_tab = [t for t in current_tabs if t.is_selected]
        if selected_tab:
            right_tab = [t for t in current_tabs if t.tab_index == selected_tab[0].tab_index + 1]
        else:
            right_tab = [t for t in current_tabs if t.tab_index == 1]
        if right_tab:
            self.tab_button_clicked(right_tab[0].name)

    def close_buton_clicked(self, command_name: str):
        self.command_tabs[command_name].button = None
        self.command_tabs[command_name].close_button = None
        self.command_tabs[command_name].output_field = None
        self.command_tabs[command_name].is_selected = False
        for tab in self.command_tabs.values():
            if tab.tab_index > self.command_tabs[command_name].tab_index:
                tab.tab_index -= 1
        self.command_tabs[command_name].tab_index = 0
        if self.command_tabs[command_name].task is not None:
            self.command_tabs[command_name].task.cancel()
            self.command_tabs[command_name].task = None
        self.redraw_app()

    def handle_tab_command(self, hummingbot: "HummingbotApplication", command_name: str, kwargs: Dict[str, Any]):
        if command_name not in self.command_tabs:
            return
        cmd_tab = self.command_tabs[command_name]
        if "close" in kwargs and kwargs["close"]:
            if cmd_tab.close_button is not None:
                self.close_buton_clicked(command_name)
            return
        if "close" in kwargs:
            kwargs.pop("close")
        if cmd_tab.button is None:
            cmd_tab.button = create_tab_button(command_name, lambda: self.tab_button_clicked(command_name))
            cmd_tab.close_button = create_tab_button("x", lambda: self.close_buton_clicked(command_name), 1, '', ' ')
            cmd_tab.output_field = create_live_field()
            cmd_tab.tab_index = max(t.tab_index for t in self.command_tabs.values()) + 1
        self.tab_button_clicked(command_name)
        self.display_tab_output(cmd_tab, hummingbot, kwargs)

    def display_tab_output(self,
                           command_tab: CommandTab,
                           hummingbot: "HummingbotApplication",
                           kwargs: Dict[Any, Any]):
        if command_tab.task is not None and not command_tab.task.done():
            return
        if threading.current_thread() != threading.main_thread():
            hummingbot.ev_loop.call_soon_threadsafe(self.display_tab_output, command_tab, hummingbot, kwargs)
            return
        command_tab.task = safe_ensure_future(command_tab.tab_class.display(command_tab.output_field, hummingbot,
                                                                            **kwargs))
