import asyncio
import copy
import importlib
import inspect
import json
import os
import shutil
import sys
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import yaml

from hummingbot.client import settings
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    ConfigValidationError,
    default_strategy_file_path,
    format_config_file_name,
    get_strategy_config_map,
    get_strategy_template_path,
    parse_config_default_to_text,
    parse_cvar_value,
    save_previous_strategy_value,
    save_to_yml,
    save_to_yml_legacy,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.strategy_config_data_types import BaseStrategyConfigMap
from hummingbot.client.settings import SCRIPT_STRATEGY_CONF_DIR_PATH, STRATEGIES_CONF_DIR_PATH, required_exchanges
from hummingbot.client.ui.completer import load_completer
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.exceptions import InvalidController, InvalidScriptModule
from hummingbot.strategy.strategy_v2_base import StrategyV2ConfigBase
from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.controllers.market_making_controller_base import MarketMakingControllerConfigBase

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class OrderedDumper(yaml.SafeDumper):
    pass


class CreateCommand:
    def create(self,  # type: HummingbotApplication
               script_to_config: Optional[str] = None,
               controller_name: Optional[str] = None, ) -> None:
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        required_exchanges.clear()
        if script_to_config and controller_name:
            self.notify("Please provide only one of script or controller name.")
            return
        if script_to_config:
            safe_ensure_future(self.prompt_for_configuration_v2(script_to_config))
        elif controller_name:
            safe_ensure_future(self.prompt_for_controller_config(controller_name))
        else:
            safe_ensure_future(self.prompt_for_configuration())

    async def prompt_for_controller_config(self,  # type: HummingbotApplication
                                           controller_name: str):
        try:

            # Attempt to find and load the correct module
            module = None
            try:
                module_path = f"{settings.CONTROLLERS_MODULE}.{controller_name}"
                module = importlib.import_module(module_path)
            except ImportError:
                pass

            if not module:
                raise InvalidController(f"The controller {controller_name} was not found in any subfolder.")

            # Load the configuration class from the module
            config_class = next((member for member_name, member in inspect.getmembers(module)
                                 if inspect.isclass(member) and member not in [ControllerConfigBase,
                                                                               MarketMakingControllerConfigBase,
                                                                               DirectionalTradingControllerConfigBase,]
                                 and (issubclass(member, ControllerConfigBase))), None)
            if not config_class:
                raise InvalidController(f"No configuration class found in the module {controller_name}.")

            config_class_instance = config_class.construct()
            config_class_instance.id = config_class_instance.set_id(None)
            config_map = ClientConfigAdapter(config_class_instance)

            await self.prompt_for_model_config(config_map)
            if not self.app.to_stop_config:
                file_name = await self.save_config(controller_name, config_map, settings.CONTROLLERS_CONF_DIR_PATH)
                self.notify(f"A new config file has been created: {file_name}")

            self.app.change_prompt(prompt=">>> ")
            self.app.input_field.completer = load_completer(self)
            self.placeholder_mode = False
            self.app.hide_input = False

        except StopIteration:
            raise InvalidController(f"The module {controller_name} does not contain any subclass of BaseModel")
        except Exception as e:
            self.notify(f"An error occurred: {str(e)}")
            self.reset_application_state()

    async def prompt_for_configuration_v2(self,  # type: HummingbotApplication
                                          script_to_config: str):
        try:
            module = sys.modules.get(f"{settings.SCRIPT_STRATEGIES_MODULE}.{script_to_config}")
            script_module = importlib.reload(module)
            config_class = next((member for member_name, member in inspect.getmembers(script_module)
                                 if
                                 inspect.isclass(member) and member not in [BaseClientModel, StrategyV2ConfigBase] and
                                 (issubclass(member, BaseClientModel) or issubclass(member, StrategyV2ConfigBase))))
            config_map = ClientConfigAdapter(config_class.construct())

            await self.prompt_for_model_config(config_map)
            if not self.app.to_stop_config:
                file_name = await self.save_config(script_to_config, config_map, SCRIPT_STRATEGY_CONF_DIR_PATH)
                self.notify(f"A new config file has been created: {file_name}")
            self.app.change_prompt(prompt=">>> ")
            self.app.input_field.completer = load_completer(self)
            self.placeholder_mode = False
            self.app.hide_input = False

        except StopIteration:
            raise InvalidScriptModule(f"The module {script_to_config} does not contain any subclass of BaseModel")
        except Exception as e:
            self.notify(f"An error occurred: {str(e)}")
            self.reset_application_state()

    async def save_config(self, name: str, config_instance: BaseClientModel, config_dir_path: Path):
        file_name = await self.prompt_new_file_name(name, True)
        if self.app.to_stop_config:
            self.app.set_text("")
            return
        config_path = config_dir_path / file_name

        # Check if the file already exists
        if config_path.exists():
            self.notify(f"File {file_name} already exists. Please enter a different file name.")
            return await self.save_config(name, config_instance, config_dir_path)  # Recursive call

        config_path = config_dir_path / file_name
        field_order = list(config_instance.__fields__.keys())
        config_json_str = config_instance.json()
        config_data = json.loads(config_json_str)
        ordered_config_data = OrderedDict((field, config_data.get(field)) for field in field_order)

        def _dict_representer(dumper, data):
            return dumper.represent_dict(data.items())

        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        with open(config_path, 'w') as file:
            yaml.dump(ordered_config_data, file, Dumper=OrderedDumper, default_flow_style=False)

        return file_name

    async def prompt_for_configuration(
        self,  # type: HummingbotApplication
    ):
        strategy = await self.get_strategy_name()

        if self.app.to_stop_config:
            return

        config_map = get_strategy_config_map(strategy)
        self.notify(f"Please see https://docs.hummingbot.org/strategies/{strategy.replace('_', '-')}/ "
                    f"while setting up these below configuration.")

        if isinstance(config_map, ClientConfigAdapter):
            await self.prompt_for_model_config(config_map)
            if not self.app.to_stop_config:
                file_name = await self.save_config_to_file(config_map)
        elif config_map is not None:
            file_name = await self.prompt_for_configuration_legacy(strategy, config_map)
        else:
            self.app.to_stop_config = True

        if self.app.to_stop_config:
            return

        save_previous_strategy_value(file_name, self.client_config_map)
        self.strategy_file_name = file_name
        self.strategy_name = strategy
        self.strategy_config_map = config_map
        # Reload completer here otherwise the new file will not appear
        self.app.input_field.completer = load_completer(self)
        self.notify(f"A new config file has been created: {self.strategy_file_name}")
        self.placeholder_mode = False
        self.app.hide_input = False

        await self.verify_status()

    async def get_strategy_name(
        self,  # type: HummingbotApplication
    ) -> Optional[str]:
        strategy = None
        strategy_config = ClientConfigAdapter(BaseStrategyConfigMap.construct())
        await self.prompt_for_model_config(strategy_config)
        if not self.app.to_stop_config:
            strategy = strategy_config.strategy
        return strategy

    async def prompt_for_model_config(
        self,  # type: HummingbotApplication
        config_map: ClientConfigAdapter,
    ):
        for key in config_map.keys():
            client_data = config_map.get_client_data(key)
            if (
                client_data is not None
                and (client_data.prompt_on_new or config_map.is_required(key))
            ):
                await self.prompt_a_config(config_map, key)
                if self.app.to_stop_config:
                    break

    async def prompt_for_configuration_legacy(
        self,  # type: HummingbotApplication
        strategy: str,
        config_map: Dict,
    ):
        config_map_backup = copy.deepcopy(config_map)
        # assign default values and reset those not required
        for config in config_map.values():
            if config.required:
                config.value = config.default
            else:
                config.value = None
        for config in config_map.values():
            if config.prompt_on_new and config.required:
                if not self.app.to_stop_config:
                    await self.prompt_a_config_legacy(config)
                else:
                    break
            else:
                config.value = config.default

        if self.app.to_stop_config:
            self.restore_config_legacy(config_map, config_map_backup)
            self.app.set_text("")
            return

        file_name = await self.prompt_new_file_name(strategy)
        if self.app.to_stop_config:
            self.restore_config_legacy(config_map, config_map_backup)
            self.app.set_text("")
            return
        self.app.change_prompt(prompt=">>> ")
        strategy_path = STRATEGIES_CONF_DIR_PATH / file_name
        template = get_strategy_template_path(strategy)
        shutil.copy(template, strategy_path)
        save_to_yml_legacy(str(strategy_path), config_map)
        return file_name

    async def prompt_a_config(
        self,  # type: HummingbotApplication
        model: ClientConfigAdapter,
        config: str,
        input_value=None,
        assign_default=True,
    ):
        config_path = config.split(".")
        while len(config_path) != 1:
            sub_model_attr = config_path.pop(0)
            model = getattr(model, sub_model_attr)
        config = config_path[0]
        if input_value is None:
            prompt = await model.get_client_prompt(config)
            if prompt is not None:
                if assign_default:
                    default = model.get_default_str_repr(attr_name=config)
                    self.app.set_text(default)
                prompt = f"{prompt} >>> "
                client_data = model.get_client_data(config)
                input_value = await self.app.prompt(prompt=prompt, is_password=client_data.is_secure)

        new_config_value = None
        if not self.app.to_stop_config and input_value is not None:
            try:
                setattr(model, config, input_value)
                new_config_value = getattr(model, config)
            except ConfigValidationError as e:
                self.notify(str(e))
                new_config_value = await self.prompt_a_config(model, config)

        if not self.app.to_stop_config and isinstance(new_config_value, ClientConfigAdapter):
            await self.prompt_for_model_config(new_config_value)

    async def prompt_a_config_legacy(
        self,  # type: HummingbotApplication
        config: ConfigVar,
        input_value=None,
        assign_default=True,
    ):
        if config.key == "inventory_price":
            await self.inventory_price_prompt_legacy(self.strategy_config_map, input_value)
            return
        if input_value is None:
            if assign_default:
                self.app.set_text(parse_config_default_to_text(config))
            prompt = await config.get_prompt()
            input_value = await self.app.prompt(prompt=prompt, is_password=config.is_secure)

        if self.app.to_stop_config:
            return
        value = parse_cvar_value(config, input_value)
        err_msg = await config.validate(input_value)
        if err_msg is not None:
            self.notify(err_msg)
            config.value = None
            await self.prompt_a_config_legacy(config)
        else:
            config.value = value

    async def save_config_to_file(
        self,  # type: HummingbotApplication
        config_map: ClientConfigAdapter,
    ) -> str:
        file_name = await self.prompt_new_file_name(config_map.strategy)
        if self.app.to_stop_config:
            self.app.set_text("")
            return
        self.app.change_prompt(prompt=">>> ")
        strategy_path = Path(STRATEGIES_CONF_DIR_PATH) / file_name
        save_to_yml(strategy_path, config_map)
        return file_name

    async def prompt_new_file_name(self,  # type: HummingbotApplication
                                   strategy: str,
                                   is_script: bool = False):
        file_name = default_strategy_file_path(strategy)
        self.app.set_text(file_name)
        input = await self.app.prompt(prompt="Enter a new file name for your configuration >>> ")
        input = format_config_file_name(input)
        conf_dir_path = STRATEGIES_CONF_DIR_PATH if not is_script else SCRIPT_STRATEGY_CONF_DIR_PATH
        file_path = os.path.join(conf_dir_path, input)
        if input is None or input == "":
            self.notify("Value is required.")
            return await self.prompt_new_file_name(strategy, is_script)
        elif os.path.exists(file_path):
            self.notify(f"{input} file already exists, please enter a new name.")
            return await self.prompt_new_file_name(strategy, is_script)
        else:
            return input

    async def verify_status(
        self  # type: HummingbotApplication
    ):
        try:
            timeout = float(self.client_config_map.commands_timeout.create_command_timeout)
            all_status_go = await asyncio.wait_for(self.status_check_all(), timeout)
        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the connection check to complete. See logs for more details.")
            self.strategy_file_name = None
            self.strategy_name = None
            self.strategy_config = None
            raise
        if all_status_go:
            self.notify("\nEnter \"start\" to start market making.")

    @staticmethod
    def restore_config_legacy(config_map: Dict[str, ConfigVar], config_map_backup: Dict[str, ConfigVar]):
        for key in config_map:
            config_map[key] = config_map_backup[key]

    def reset_application_state(self):
        self.app.change_prompt(prompt=">>> ")
        self.app.input_field.completer = load_completer(self)
        self.placeholder_mode = False
        self.app.hide_input = False
