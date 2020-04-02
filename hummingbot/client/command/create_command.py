import os
from decimal import Decimal
import shutil

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    parse_cvar_value,
    default_strategy_file_path,
    save_to_yml,
    get_strategy_template_path
)
from hummingbot.client.settings import CONF_FILE_PATH
from hummingbot.client.config.global_config_map import global_config_map
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


def parse_config_default_to_text(config: ConfigVar) -> str:
    """
    :param config: ConfigVar object
    :return: text for default value prompt
    """
    if config.default is None:
        default = ""
    elif callable(config.default):
        default = config.default()
    elif config.type == 'bool' and isinstance(config.prompt, str) and "Yes/No" in config.prompt:
        default = "Yes" if config.default else "No"
    else:
        default = str(config.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


class CreateCommand:
    def create(self,  # type: HummingbotApplication
               file_name):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.toggle_hide_input()
        safe_ensure_future(self.prompt_for_configuration())

    async def prompt_for_configuration(self, config_map):
        strategy = global_config_map.get("strategy").value
        config_map = get_strategy_config_map(strategy)
        self._notify(f"Please see https://docs.hummingbot.io/strategies/{strategy.replace('_', '-')}/ "
                     f"while setting up these below configuration.")
        for config in config_map.values():
            if config.required:
                await self.prompt_a_config(config)
            else:
                config.value = config.default
        strategy = global_config_map.get("strategy").value
        self.strategy_file_name = await self.prompt_new_file_name(strategy)
        strategy_path = os.path.join(CONF_FILE_PATH, self.strategy_file_name)
        template = get_strategy_template_path(strategy)
        shutil.copy(template, strategy_path)
        await save_to_yml(strategy_path, config_map)
        self.placeholder_mode = False
        self.app.change_prompt(prompt=">>> ")

    async def prompt_a_config(self,  # type: HummingbotApplication
                              config: ConfigVar):
        self.app.set_text(parse_config_default_to_text(config))
        input = await self.app.prompt(prompt=config.prompt, is_password=config.is_secure)
        valid = config.validate(input)
        # ToDo: this should be from the above validate function.
        msg = "Invalid input."
        if not valid:
            self._notify(msg)
            await self.prompt_a_config(config)
        else:
            config.value = parse_cvar_value(config, input)

    async def prompt_new_file_name(self,  # type: HummingbotApplication
                                   strategy):
        file_name = default_strategy_file_path(strategy)
        self.app.set_text(file_name)
        input = await self.app.prompt(prompt="Enter a new file name for your configuration >>> ")
        file_path = os.path.join(CONF_FILE_PATH, input)
        if os.path.exists(file_path):
            self._notify(f"{input} file already exists, please enter a new name.")
            await self.prompt_new_file_name()
        else:
            return input
