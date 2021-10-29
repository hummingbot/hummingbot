from hummingbot.client.ui.custom_widgets import CustomTextArea
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class TabBase:

    @classmethod
    def get_command_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    def get_command_help_message(cls) -> str:
        raise NotImplementedError

    @classmethod
    def get_command_arguments(cls):
        raise NotImplementedError

    @classmethod
    async def display(cls, output_field: CustomTextArea, hummingbot: "HummingbotApplication", **kwargs):
        raise NotImplementedError
