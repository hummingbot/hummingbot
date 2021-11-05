import asyncio

from dataclasses import dataclass
from prompt_toolkit.widgets import Button
from typing import Type, Optional

from hummingbot.client.ui.custom_widgets import CustomTextArea
from .tab_base import TabBase


@dataclass
class CommandTab:
    name: str
    button: Button
    close_button: Button
    output_field: CustomTextArea
    tab_class: Type[TabBase]
    is_selected: bool = False
    tab_index: int = 0
    task: Optional[asyncio.Task] = None
