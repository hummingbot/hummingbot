from typing import TYPE_CHECKING, Optional

from hummingbot.client.config.config_helpers import parse_config_default_to_text, parse_cvar_value
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.async_utils import safe_ensure_future

from .import_command import ImportCommand

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class PreviousCommand:
    def previous_strategy(
        self,  # type: HummingbotApplication
        option: str,
    ):
        if option is not None:
            # Handle specific options if necessary
            pass

        previous_strategy_file = self.client_config_map.previous_strategy
        if previous_strategy_file is not None:
            safe_ensure_future(self.prompt_for_previous_strategy(previous_strategy_file))
        else:
            self.notify("No previous strategy found.")

    async def prompt_for_previous_strategy(
        self,  # type: HummingbotApplication
        file_name: str,
    ):
        try:
            self.prepare_for_user_input()
            previous_strategy = self.create_previous_strategy_configvar(file_name)

            await self.prompt_and_process_answer(previous_strategy)
            if self.should_stop_config():
                return

            if self.is_strategy_accepted(previous_strategy):
                ImportCommand.import_command(self, file_name)
        finally:
            self.cleanup_after_prompt()

    def prepare_for_user_input(self):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True

    def create_previous_strategy_configvar(self, file_name: str) -> ConfigVar:
        return ConfigVar(
            key="previous_strategy_answer",
            prompt=f"Do you want to import the previously stored config? [{file_name}] (Yes/No) >>>",
            type_str="bool",
            validator=validate_bool,
        )

    async def prompt_and_process_answer(self, config: ConfigVar):
        input_value = None
        if not self.app.to_stop_config:
            self.app.set_text(parse_config_default_to_text(config))
            prompt = await config.get_prompt()
            input_value = await self.app.prompt(prompt=prompt)

        if self.app.to_stop_config:
            return
        config.value = parse_cvar_value(config, input_value)
        err_msg = await config.validate(input_value)
        if err_msg is not None:
            self.notify(err_msg)
            config.value = None
            await self.prompt_and_process_answer(config)

    def should_stop_config(self) -> bool:
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return True
        return False

    def is_strategy_accepted(self, config: ConfigVar) -> bool:
        return config.value

    def cleanup_after_prompt(self):
        self.app.change_prompt(prompt=">>> ")
        self.placeholder_mode = False
        self.app.hide_input = False
