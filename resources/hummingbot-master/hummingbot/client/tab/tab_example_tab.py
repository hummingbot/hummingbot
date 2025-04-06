from typing import TYPE_CHECKING, Dict, Any
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.ui.custom_widgets import CustomTextArea
from .tab_base import TabBase


class TabExampleTab(TabBase):
    @classmethod
    def get_command_name(cls) -> str:
        return "tab_example"

    @classmethod
    def get_command_help_message(cls) -> str:
        return "Display hello world"

    @classmethod
    def get_command_arguments(cls) -> Dict[str, Dict[str, Any]]:
        return {}

    @classmethod
    async def display(cls,
                      output_field: CustomTextArea,
                      hummingbot: "HummingbotApplication",
                      ):
        output_field.log("Hello World!")
