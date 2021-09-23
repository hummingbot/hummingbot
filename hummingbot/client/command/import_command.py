import asyncio
import os

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    update_strategy_config_map_from_file,
    short_strategy_name,
    format_config_file_name,
    validate_strategy_file
)
from hummingbot.client.settings import CONF_FILE_PATH, CONF_PREFIX, required_exchanges
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ImportCommand:

    def import_command(self,  # type: HummingbotApplication
                       file_name):
        if file_name is not None:
            file_name = format_config_file_name(file_name)

        safe_ensure_future(self.import_config_file(file_name))

    async def import_config_file(self,  # type: HummingbotApplication
                                 file_name):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        required_exchanges.clear()
        if file_name is None:
            file_name = await self.prompt_a_file_name()
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return
        strategy_path = os.path.join(CONF_FILE_PATH, file_name)
        strategy = await update_strategy_config_map_from_file(strategy_path)
        self.strategy_file_name = file_name
        self.strategy_name = strategy
        self._notify(f"Configuration from {self.strategy_file_name} file is imported.")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")
        try:
            all_status_go = await self.status_check_all()
        except asyncio.TimeoutError:
            self.strategy_file_name = None
            self.strategy_name = None
            raise
        if all_status_go:
            self._notify("\nEnter \"start\" to start market making.")
            autofill_import = global_config_map.get("autofill_import").value
            if autofill_import is not None:
                self.app.set_text(autofill_import)

    async def prompt_a_file_name(self  # type: HummingbotApplication
                                 ):
        example = f"{CONF_PREFIX}{short_strategy_name('pure_market_making')}_{1}.yml"
        file_name = await self.app.prompt(prompt=f'Enter path to your strategy file (e.g. "{example}") >>> ')
        if self.app.to_stop_config:
            return
        file_path = os.path.join(CONF_FILE_PATH, file_name)
        err_msg = validate_strategy_file(file_path)
        if err_msg is not None:
            self._notify(f"Error: {err_msg}")
            return await self.prompt_a_file_name()
        else:
            return file_name
