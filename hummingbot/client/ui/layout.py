#!/usr/bin/env python

from os.path import join, realpath, dirname
import sys;sys.path.insert(0, realpath(join(__file__, "../../../")))

from prompt_toolkit.layout.containers import (
    ConditionalContainer,
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
from hummingbot.client.ui.custom_widgets import CustomTextArea as TextArea
from prompt_toolkit.utils import is_windows
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.controls import FormattedTextControl

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

================================================================================================
Press CTRL + C to quit at any time.
Enter "help" for a list of commands.
"""

with open(join(dirname(__file__), '../../VERSION')) as version_file:
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


def create_log_field():
    return TextArea(
        style='class:log-field',
        text="Running logs\n",
        focus_on_click=False,
        read_only=False,
        scrollbar=True,
        max_line_count=MAXIMUM_LOG_PANE_LINE_COUNT,
        initial_text="Running Logs \n"
    )


def get_version():
    return [("class:title", f"Version: {version}")]


def get_bounty_status():
    from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
    enabled = liquidity_bounty_config_map["liquidity_bounty_enabled"].value is True and \
        liquidity_bounty_config_map["liquidity_bounty_client_id"].value is not None
    bounty_status = "ON" if enabled else "OFF"
    style = "class:primary" if enabled else "class:warning"
    return [(style, f"bounty_status: {bounty_status}")]


def get_title_bar_right_text():
    copy_key = "CTRL + SHIFT" if is_windows() else "fn"
    return [
        ("class:title", f"[Double Ctrl + C] QUIT      "),
        ("class:title", f"[Ctrl + S] STATUS      "),
        ("class:title", f"Hold down \"{copy_key}\" for selecting and copying text"),
    ]


def generate_layout(input_field: TextArea, output_field: TextArea, log_field: TextArea):
    root_container = HSplit([
        ConditionalContainer(
            content=VSplit([
                Window(FormattedTextControl(get_version), style="class:title"),
                Window(FormattedTextControl(get_bounty_status), style="class:title"),
                Window(FormattedTextControl(get_title_bar_right_text), align=WindowAlign.RIGHT, style="class:title"),
            ], height=1),
            filter=Condition(lambda: True),
        ),
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
            log_field,
        ]),

    ])
    return Layout(root_container, focused_element=input_field)

