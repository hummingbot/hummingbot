#!/usr/bin/env python

from os.path import join, realpath, dirname
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from prompt_toolkit.layout.containers import (
    VSplit,
    HSplit,
    Window,
    FloatContainer,
    Float,
    WindowAlign,
)
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer
from prompt_toolkit.utils import is_windows
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import SearchToolbar

from hummingbot.client.ui.custom_widgets import CustomTextArea as TextArea
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


██╗  ██╗██╗   ██╗███╗   ███╗███╗   ███╗██╗███╗   ██╗ ██████╗ ██████╗  ██████╗ ████████╗
██║  ██║██║   ██║████╗ ████║████╗ ████║██║████╗  ██║██╔════╝ ██╔══██╗██╔═══██╗╚══██╔══╝
███████║██║   ██║██╔████╔██║██╔████╔██║██║██╔██╗ ██║██║  ███╗██████╔╝██║   ██║   ██║
██╔══██║██║   ██║██║╚██╔╝██║██║╚██╔╝██║██║██║╚██╗██║██║   ██║██╔══██╗██║   ██║   ██║
██║  ██║╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║██║██║ ╚████║╚██████╔╝██████╔╝╚██████╔╝   ██║
╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝

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
- import      Import a existing bot by loading the configuration file
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
    )


def create_search_field() -> SearchToolbar:
    return SearchToolbar(text_if_not_searching=[('class:primary', "[CTRL + F] to start searching.")],
                         forward_search_prompt=[('class:primary', "Search logs [Press CTRL + F to hide search] >>> ")],
                         ignore_case=True)


def create_log_field(search_field: SearchToolbar):
    return TextArea(
        style='class:log-field',
        text="Running logs\n",
        focus_on_click=False,
        read_only=False,
        scrollbar=True,
        max_line_count=MAXIMUM_LOG_PANE_LINE_COUNT,
        initial_text="Running Logs \n",
        search_field=search_field,
        preview_search=False,
    )


def get_version():
    return [("class:title", f"Version: {version}")]


def get_paper_trade_status():
    from hummingbot.client.config.global_config_map import global_config_map
    enabled = global_config_map["paper_trade_enabled"].value is True
    paper_trade_status = "ON" if enabled else "OFF"
    style = "class:primary" if enabled else "class:warning"
    return [(style, f"paper_trade_mode: {paper_trade_status}")]


def get_title_bar_right_text():
    copy_key = "CTRL + SHIFT" if is_windows() else "fn"
    return [
        ("class:title", f"[Double Ctrl + C] QUIT      "),
        ("class:title", f"[Ctrl + S] STATUS      "),
        ("class:title", f"Hold down \"{copy_key}\" for selecting and copying text"),
    ]


def generate_layout(input_field: TextArea,
                    output_field: TextArea,
                    log_field: TextArea,
                    search_field: SearchToolbar):
    root_container = HSplit([
        VSplit([
            Window(FormattedTextControl(get_version), style="class:title"),
            Window(FormattedTextControl(get_paper_trade_status), style="class:title"),
            Window(FormattedTextControl(get_title_bar_right_text), align=WindowAlign.RIGHT, style="class:title"),
        ], height=1),
        VSplit([
            FloatContainer(
                HSplit([
                    output_field,
                    Window(height=1, char='-', style='class:primary'),
                    input_field,
                ]),
                [
                    # Completion menus.
                    Float(xcursor=True,
                          ycursor=True,
                          transparent=True,
                          content=CompletionsMenu(
                              max_height=16,
                              scroll_offset=1)),
                ]
            ),
            Window(width=1, char='|', style='class:primary'),
            HSplit([
                log_field,
                search_field,
            ]),
        ]),

    ])
    return Layout(root_container, focused_element=input_field)
