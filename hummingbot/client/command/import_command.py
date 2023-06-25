import asyncio
import threading
from typing import TYPE_CHECKING

from hummingbot.client.config.client_config_map import AutofillImportEnum
from hummingbot.client.config.config_helpers import (
    format_config_file_name,
    load_strategy_config_map_from_file,
    save_previous_strategy_value,
    short_strategy_name,
    validate_strategy_file,
)
from hummingbot.client.settings import CONF_PREFIX, STRATEGIES_CONF_DIR_PATH, required_exchanges
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class ImportCommand:

    def import_command(self,  # type: HummingbotApplication
                       file_name):
        if file_name is not None:
            file_name = format_config_file_name(file_name)

        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.import_command, file_name)
            return
        safe_ensure_future(self.import_config_file(file_name))

    async def import_config_file(self,  # type: HummingbotApplication
                                 file_name):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        required_exchanges.clear()
        if file_name is None:
            file_name = await self.prompt_a_file_name()
            if file_name is not None:
                save_previous_strategy_value(file_name, self.client_config_map)
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return
        strategy_path = STRATEGIES_CONF_DIR_PATH / file_name
        try:
            config_map = await load_strategy_config_map_from_file(strategy_path)
        except Exception as e:
            self.notify(f'Strategy import error: {str(e)}')
            # Reset prompt settings
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")
            raise
        self.strategy_file_name = file_name
        self.strategy_name = (
            config_map.strategy
            if not isinstance(config_map, dict)
            else config_map.get("strategy").value  # legacy
        )
        self.strategy_config_map = config_map
        self.notify(f"Configuration from {self.strategy_file_name} file is imported.")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")
        try:
            all_status_go = await self.status_check_all()
        except asyncio.TimeoutError:
            self.strategy_file_name = None
            self.strategy_name = None
            self.strategy_config_map = None
            raise
        if all_status_go:
            self.notify("\nEnter \"start\" to start market making.")
            autofill_import = self.client_config_map.autofill_import
            if autofill_import != AutofillImportEnum.disabled:
                self.app.set_text(autofill_import)

    async def prompt_a_file_name(self  # type: HummingbotApplication
                                 ):
        example = f"{CONF_PREFIX}{short_strategy_name('pure_market_making')}_{1}.yml"
        file_name = await self.app.prompt(prompt=f'Enter path to your strategy file (e.g. "{example}") >>> ')
        if self.app.to_stop_config:
            return
        file_path = STRATEGIES_CONF_DIR_PATH / file_name
        err_msg = validate_strategy_file(file_path)
        if err_msg is not None:
            self.notify(f"Error: {err_msg}")
            return await self.prompt_a_file_name()
        else:
            return file_name
