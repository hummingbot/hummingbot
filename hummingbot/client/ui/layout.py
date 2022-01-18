from os.path import join, realpath, dirname
from prompt_toolkit.layout import Dimension
from prompt_toolkit.layout.containers import (
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
    ConditionalContainer,
)
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Box, Button, SearchToolbar
from typing import Dict

from hummingbot.client.ui.custom_widgets import CustomTextArea as TextArea, FormattedTextLexer
from hummingbot.client.tab.data_types import CommandTab
from hummingbot.client.settings import (
    MAXIMUM_OUTPUT_PANE_LINE_COUNT,
    MAXIMUM_LOG_PANE_LINE_COUNT,
)


HEADER = """
                                                *,.
                                                *,,,*
                                            ,,,,,,,               *
                                            ,,,,,,,,            ,,,,
                                            *,,,,,,,,(        .,,,,,,
                                        /,,,,,,,,,,     .*,,,,,,,,
                                        .,,,,,,,,,,,.  ,,,,,,,,,,,*
                                        ,,,,,,,,,,,,,,,,,,,,,,,,,,,
                            //      ,,,,,,,,,,,,,,,,,,,,,,,,,,,,#*%
                        .,,,,,,,,. *,,,,,,,,,,,,,,,,,,,,,,,,,,,%%%%%%&@
                        ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,%%%%%%%&
                    ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,%%%%%%%&
                    /*,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,(((((%%&
                **.         #,,,,,,,,,,,,,,,,,,,,,,,,,,,,,((((((((((#.
            **               *,,,,,,,,,,,,,,,,,,,,,,,,**/(((((((((((((*
                                ,,,,,,,,,,,,,,,,,,,,*********((((((((((((
                                ,,,,,,,,,,,,,,,**************((((((((@
                                (,,,,,,,,,,,,,,,***************(#
                                    *,,,,,,,,,,,,,,,,**************/
                                    ,,,,,,,,,,,,,,,***************/
                                        ,,,,,,,,,,,,,,****************
                                        .,,,,,,,,,,,,**************/
                                            ,,,,,,,,*******,
                                            *,,,,,,,,********
                                            ,,,,,,,,,/******/
                                            ,,,,,,,,,@  /****/
                                            ,,,,,,,,
                                            , */


██   ██ ██    ██ ███    ███ ███    ███ ██ ███    ██  ██████  ██████   ██████  ████████
██   ██ ██    ██ ████  ████ ████  ████ ██ ████   ██ ██       ██   ██ ██    ██    ██
███████ ██    ██ ██ ████ ██ ██ ████ ██ ██ ██ ██  ██ ██   ███ ██████  ██    ██    ██
██   ██ ██    ██ ██  ██  ██ ██  ██  ██ ██ ██  ██ ██ ██    ██ ██   ██ ██    ██    ██
██   ██  ██████  ██      ██ ██      ██ ██ ██   ████  ██████  ██████   ██████     ██

=======================================================================================
Welcome to Hummingbot, an open source software client that helps you build and run
high-frequency trading (HFT) bots.

Helpful Links:
- Get 24/7 support: https://discord.hummingbot.io
- Learn how to use Hummingbot: https://docs.hummingbot.io
- Earn liquidity rewards: https://miner.hummingbot.io

Useful Commands:
- connect     List available exchanges and add API keys to them
- create      Create a new bot
- import      Import an existing bot by loading the configuration file
- help        List available commands

"""

with open(realpath(join(dirname(__file__), '../../VERSION'))) as version_file:
    version = version_file.read().strip()


def create_input_field(lexer=None, completer: Completer = None):
    return TextArea(
        height=10,
        prompt='>>> ',
        style='class:input-field',
        multiline=False,
        focus_on_click=True,
        lexer=lexer,
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        complete_while_typing=True,
    )


def create_output_field():
    return TextArea(
        style='class:output-field',
        focus_on_click=False,
        read_only=False,
        scrollbar=True,
        max_line_count=MAXIMUM_OUTPUT_PANE_LINE_COUNT,
        initial_text=HEADER,
        lexer=FormattedTextLexer()
    )


def create_timer():
    return TextArea(
        style='class:footer',
        focus_on_click=False,
        read_only=False,
        scrollbar=False,
        max_line_count=1,
        width=20,
    )


def create_process_monitor():
    return TextArea(
        style='class:footer',
        focus_on_click=False,
        read_only=False,
        scrollbar=False,
        max_line_count=1,
        align=WindowAlign.RIGHT
    )


def create_trade_monitor():
    return TextArea(
        style='class:footer',
        focus_on_click=False,
        read_only=False,
        scrollbar=False,
        max_line_count=1,
    )


def create_search_field() -> SearchToolbar:
    return SearchToolbar(text_if_not_searching=[('class:primary', "[CTRL + F] to start searching.")],
                         forward_search_prompt=[('class:primary', "Search logs [Press CTRL + F to hide search] >>> ")],
                         ignore_case=True)


def create_log_field(search_field: SearchToolbar):
    return TextArea(
        style='class:log-field',
        text="Running Logs\n",
        focus_on_click=False,
        read_only=False,
        scrollbar=True,
        max_line_count=MAXIMUM_LOG_PANE_LINE_COUNT,
        initial_text="Running Logs \n",
        search_field=search_field,
        preview_search=False,
    )


def create_live_field():
    return TextArea(
        style='class:log-field',
        focus_on_click=False,
        read_only=False,
        scrollbar=True,
        max_line_count=MAXIMUM_OUTPUT_PANE_LINE_COUNT,
    )


def create_log_toggle(function):
    return Button(
        text='> log pane',
        width=13,
        handler=function,
        left_symbol='',
        right_symbol='',
    )


def create_tab_button(text, function, margin=2, left_symbol=' ', right_symbol=' '):
    return Button(
        text=text,
        width=len(text) + margin,
        handler=function,
        left_symbol=left_symbol,
        right_symbol=right_symbol
    )


def get_version():
    return [("class:header", f"Version: {version}")]


def get_active_strategy():
    from hummingbot.client.hummingbot_application import HummingbotApplication
    hb = HummingbotApplication.main_application()
    style = "class:log-field"
    return [(style, f"Strategy: {hb.strategy_name}")]


"""def get_active_markets():
    from hummingbot.client.hummingbot_application import HummingbotApplication
    hb = HummingbotApplication.main_application()
    style = "class:primary"
    markets = "None" if len(hb.market_trading_pairs_map) == 0 \
              else eval(str(hb.market_trading_pairs_map))
    return [(style, f"Market(s): {markets}")]"""


"""def get_script_file():
    from hummingbot.client.config.global_config_map import global_config_map
    script = global_config_map["script_file_path"].value
    style = "class:primary"
    return [(style, f"Script_file: {script}")]"""


def get_strategy_file():
    from hummingbot.client.hummingbot_application import HummingbotApplication
    hb = HummingbotApplication.main_application()
    style = "class:log-field"
    return [(style, f"Strategy File: {hb._strategy_file_name}")]


def generate_layout(input_field: TextArea,
                    output_field: TextArea,
                    log_field: TextArea,
                    right_pane_toggle: Button,
                    log_field_button: Button,
                    search_field: SearchToolbar,
                    timer: TextArea,
                    process_monitor: TextArea,
                    trade_monitor: TextArea,
                    command_tabs: Dict[str, CommandTab],
                    ):
    components = {}

    components["item_top_version"] = Window(FormattedTextControl(get_version), style="class:header")
    components["item_top_active"] = Window(FormattedTextControl(get_active_strategy), style="class:header")
    components["item_top_file"] = Window(FormattedTextControl(get_strategy_file), style="class:header")
    components["item_top_toggle"] = right_pane_toggle
    components["pane_top"] = VSplit([components["item_top_version"],
                                     components["item_top_active"],
                                     components["item_top_file"],
                                     components["item_top_toggle"]], height=1)
    components["pane_bottom"] = VSplit([trade_monitor,
                                        process_monitor,
                                        timer], height=1)
    output_pane = Box(body=output_field, padding=0, padding_left=2, style="class:output-field")
    input_pane = Box(body=input_field, padding=0, padding_left=2, padding_top=1, style="class:input-field")
    components["pane_left"] = HSplit([output_pane, input_pane], width=Dimension(weight=1))
    if all(not t.is_selected for t in command_tabs.values()):
        log_field_button.window.style = "class:tab_button.focused"
    else:
        log_field_button.window.style = "class:tab_button"
    tab_buttons = [log_field_button]
    for tab in sorted(command_tabs.values(), key=lambda x: x.tab_index):
        if tab.button is not None:
            if tab.is_selected:
                tab.button.window.style = "class:tab_button.focused"
            else:
                tab.button.window.style = "class:tab_button"
            tab.close_button.window.style = tab.button.window.style
            tab_buttons.append(VSplit([tab.button, tab.close_button]))
    pane_right_field = log_field
    focused_right_field = [tab.output_field for tab in command_tabs.values() if tab.is_selected]
    if focused_right_field:
        pane_right_field = focused_right_field[0]
    components["pane_right_top"] = VSplit(tab_buttons, height=1, style="class:log-field", padding_char=" ", padding=2)
    components["pane_right"] = ConditionalContainer(
        Box(body=HSplit([components["pane_right_top"], pane_right_field, search_field], width=Dimension(weight=1)),
            padding=0, padding_left=2, style="class:log-field"),
        filter=True
    )
    components["hint_menus"] = [Float(xcursor=True,
                                      ycursor=True,
                                      transparent=True,
                                      content=CompletionsMenu(max_height=16,
                                                              scroll_offset=1))]

    root_container = HSplit([
        components["pane_top"],
        VSplit(
            [FloatContainer(components["pane_left"], components["hint_menus"]),
             components["pane_right"]]),
        components["pane_bottom"],
    ])
    return Layout(root_container, focused_element=input_field), components
