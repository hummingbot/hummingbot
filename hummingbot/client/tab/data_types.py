import asyncio

from dataclasses import dataclass
from prompt_toolkit.widgets import Button
from typing import Type, Optional

from hummingbot.client.ui.custom_widgets import CustomTextArea
from .tab_base import TabBase


@dataclass
class CommandTab:
    """
    Defines all data points for a tab.
    """
    name: str  # Command name of the tab
    button: Optional[Button]  # Tab toggle button
    close_button: Optional[Button]  # Tab close button
    output_field: Optional[CustomTextArea]  # Output pane where tab messages display
    tab_class: Type[TabBase]  # The tab class (Subclass of TabBase)
    is_selected: bool = False  # If the tab is currently selected by a user
    tab_index: int = 0  # The index position of the tab in relation of all other displayed tabs
    task: Optional[asyncio.Task] = None  # The currently running task, None if there isn't one
