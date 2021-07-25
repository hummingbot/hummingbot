# import argparse
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.config_helpers import (
    # get_strategy_config_map,
    parse_cvar_value,
    # default_strategy_file_path,
    # save_to_yml,
    # get_strategy_template_path,
    # format_config_file_name,
    parse_config_default_to_text,
)
from hummingbot.client.config.config_var import ConfigVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class PreviousCommand:
    def previous_statrategy(
        self,  # type: HummingbotApplication
        option: str,
    ):
        if option is not None:
            pass
        #     self._notify(self.parser.format_help())
        # else:
        #     subparsers_actions = [
        #         action for action in self.parser._actions if isinstance(action, argparse._SubParsersAction)
        #     ]

        #     for subparsers_action in subparsers_actions:
        #         subparser = subparsers_action.choices.get(option)
        #         self._notify(subparser.format_help())
        safe_ensure_future(self.prompt_for_configuration2(option))

    async def prompt_for_configuration2(
        self,  # type: HummingbotApplication
        option,
    ):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True

        previous_strategy = ConfigVar(
            key="option", prompt="Dou you want to import previous strategy? >>> ", validator=validate_bool
        )

        await self.prompt_a_config2(previous_strategy)
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return
        # clean
        self.app.change_prompt(prompt=">>> ")

        self.placeholder_mode = False
        self.app.hide_input = False

    async def prompt_a_config2(
        self,  # type: HummingbotApplication
        config: ConfigVar,
        input_value=None,
        assign_default=True,
    ):
        # if config.key == "inventory_price":
        #     await self.inventory_price_prompt(self.strategy_config_map, input_value)
        #     return
        if input_value is None:
            if assign_default:
                self.app.set_text(parse_config_default_to_text(config))
            prompt = await config.get_prompt()
            input_value = await self.app.prompt(prompt=prompt)

        if self.app.to_stop_config:
            return
        config.value = parse_cvar_value(config, input_value)
        err_msg = await config.validate(input_value)
        if err_msg is not None:
            self._notify(err_msg)
            config.value = None
            await self.prompt_a_config2(config)
        else:
            config.value = parse_cvar_value(config, input_value)
