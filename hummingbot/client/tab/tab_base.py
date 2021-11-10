from abc import (
    ABCMeta,
    abstractmethod,
)
from typing import TYPE_CHECKING, Dict, Any
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

from hummingbot.client.ui.custom_widgets import CustomTextArea


class TabBase(metaclass=ABCMeta):
    """
    Defines functions needed to be implemented by all tab classes.
    """

    @classmethod
    @abstractmethod
    def get_command_name(cls) -> str:
        """
        Returns a command name for the tab, once issued a new tab will be created. The command name will also appear on
        auto complete list of commands.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_command_help_message(cls) -> str:
        """
        Returns a help message to describe what the command does.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_command_arguments(cls) -> Dict[str, Dict[str, Any]]:
        """
        Returns a dictionary of command argument and all its properties. See hummingbot.client.ui.parser for examples.
        """

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def display(cls, output_field: CustomTextArea, hummingbot: "HummingbotApplication", **kwargs):
        """
        Displays message on the tab
        :param output_field: The output pane for the tab messages
        :param hummingbot: The current running Hummingbot application including strategy, connectors and all
        other application properties
        :param **kargs: All the command arguments defined in get_command_arguments method will be supplied here
        """

        raise NotImplementedError
