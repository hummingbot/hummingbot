import os

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    load_yml_into_cm,
    short_strategy_name,
    get_strategy_template_path,
    format_config_file_name
)
from hummingbot.client.settings import CONF_FILE_PATH, CONF_PREFIX
from hummingbot.client.config.global_config_map import global_config_map
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ImportCommand:

    def import_command(self,  # type: HummingbotApplication
                       file_name):
        strategy_file_name = None
        if file_name is not None:
            strategy_file_name = format_config_file_name(file_name)
            if strategy_file_name is None:
                self._notify(f"{file_name} is a not valid yml file.")
                return
            if not os.path.exists(os.path.join(CONF_FILE_PATH, strategy_file_name)):
                self._notify(f"{strategy_file_name} does not exist.")
                return
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.toggle_hide_input()
        safe_ensure_future(self.import_config_file(strategy_file_name))

    async def import_config_file(self,  # type: HummingbotApplication
                                 file_name):
        strategy = global_config_map.get("strategy").value
        config_map = get_strategy_config_map(strategy)
        if file_name is not None:
            self.strategy_file_name = file_name
        else:
            self.strategy_file_name = await self.prompt_a_file_name(strategy)
        strategy_path = os.path.join(CONF_FILE_PATH, self.strategy_file_name)
        template_path = get_strategy_template_path(strategy)
        load_yml_into_cm(strategy_path, template_path, config_map)
        self._notify(f"Configuration from {self.strategy_file_name} file is imported.")
        if not await self.notify_missing_configs():
            self._notify("Enter \"start\" to start market making.")
            self.app.set_text("start")
        self.placeholder_mode = False
        self.app.change_prompt(prompt=">>> ")

    async def prompt_a_file_name(self,  # type: HummingbotApplication
                                 strategy):
        example = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{1}.yml"
        file_name = await self.app.prompt(prompt=f'Enter path to your strategy file (e.g. "{example}") >>> ')
        file_path = os.path.join(CONF_FILE_PATH, file_name)
        if not os.path.exists(file_path):
            self._notify(f"{file_name} does not  exists, please enter a valid file name.")
            await self.prompt_a_file_name()
        else:
            return file_name
