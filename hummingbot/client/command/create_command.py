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
    get_strategy_template_path,
    missing_required_configs
)
from hummingbot.client.settings import CONF_FILE_PATH
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
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

    async def prompt_for_configuration(self):
        strategy = global_config_map.get("strategy").value
        config_map = get_strategy_config_map(strategy)
        self._notify(f"Please see https://docs.hummingbot.io/strategies/{strategy.replace('_', '-')}/ "
                     f"while setting up these below configuration.")
        # assign default values and reset those not required
        for config in config_map.values():
            if config.required:
                config.value = config.default
            else:
                config.value = None
        for config in config_map.values():
            if config.prompt_on_new:
                await self.prompt_a_config(config)
            else:
                config.value = config.default
        strategy = global_config_map.get("strategy").value
        self.strategy_file_name = await self.prompt_new_file_name(strategy)
        strategy_path = os.path.join(CONF_FILE_PATH, self.strategy_file_name)
        template = get_strategy_template_path(strategy)
        shutil.copy(template, strategy_path)
        save_to_yml(strategy_path, config_map)
        self._notify(f"A new config file {self.strategy_file_name} created.")
        if not await self.notify_missing_configs():
            self._notify("Enter \"start\" to start market making.")
            self.app.set_text("start")
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
            await self.prompt_new_file_name(strategy)
        else:
            return input

    async def notify_missing_configs(self,  # type: HummingbotApplication
                                     ):
        await Security.wait_til_decryption_done()
        for config in global_config_map.values():
            if config.is_secure and config.value is None:
                config.value = Security.decrypted_value(config.key)
        missing_globals = missing_required_configs(global_config_map)
        if missing_globals:
            self._notify("\nIncomplete global configuration (conf_global.yml). The following values are missing.\n")
            for config in missing_globals:
                self._notify(config.key)
        missing_configs = missing_required_configs(get_strategy_config_map(global_config_map["strategy"].value))
        if missing_configs:
            self._notify(f"\nIncomplete strategy configuration ({self.strategy_file_name}). "
                         f"The following values are missing.\n")
            for config in missing_configs:
                self._notify(config.key)
        any_missing = missing_globals or missing_configs
        if any_missing:
            self._notify(f"\nPlease run config config_name (e.g. config kill_switch) "
                         f"to update the missing config values.")
        return any_missing
