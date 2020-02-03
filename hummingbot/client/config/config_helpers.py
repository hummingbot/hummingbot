import logging
from decimal import Decimal

import ruamel.yaml
from os import unlink
from os.path import (
    join,
    isfile,
)
from collections import OrderedDict
import json
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)
from os import listdir
import shutil

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import (
    GLOBAL_CONFIG_PATH,
    TEMPLATE_PATH,
    CONF_FILE_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
    TOKEN_ADDRESSES_FILE_PATH,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.config_crypt import (
    encrypt_n_save_config_value,
    encrypted_config_file_exists
)

# Use ruamel.yaml to preserve order and comments in .yml file
yaml_parser = ruamel.yaml.YAML()


def parse_cvar_value(cvar: ConfigVar, value: Any) -> Any:
    """
    Based on the target type specified in `ConfigVar.type_str`, parses a string value into the target type.
    :param cvar: ConfigVar object
    :param value: User input from running session or from saved `yml` files. Type is usually string.
    :return: value in the correct type
    """
    if value is None:
        return None
    elif cvar.type == 'str':
        return str(value)
    elif cvar.type == 'list':
        if isinstance(value, str):
            if len(value) == 0:
                return []
            filtered: filter = filter(lambda x: x not in ['[', ']', '"', "'"], list(value))
            value = "".join(filtered).split(",")  # create csv and generate list
            return [s.strip() for s in value]  # remove leading and trailing whitespaces
        else:
            return value
    elif cvar.type == 'json':
        if isinstance(value, str):
            value_json = value.replace("'", '"')  # replace single quotes with double quotes for valid JSON
            return json.loads(value_json)
        else:
            return value
    elif cvar.type == 'float':
        try:
            return float(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.", exc_info=True)
            return 0.0
    elif cvar.type == 'decimal':
        try:
            return Decimal(str(value))
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid decimal.", exc_info=True)
            return Decimal(0)
    elif cvar.type == 'int':
        try:
            return int(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.", exc_info=True)
            return 0
    elif cvar.type == 'bool':
        if isinstance(value, str) and value.lower() in ["true", "yes", "y"]:
            return True
        elif isinstance(value, str) and value.lower() in ["false", "no", "n"]:
            return False
        else:
            return bool(value)
    else:
        raise TypeError


def parse_cvar_default_value_prompt(cvar: ConfigVar) -> str:
    """
    :param cvar: ConfigVar object
    :return: text for default value prompt
    """
    if cvar.default is None:
        return ""
    elif cvar.type == 'bool' and isinstance(cvar.prompt, str) and "Yes/No" in cvar.prompt:
        return "Yes" if cvar.default else "No"
    else:
        return str(cvar.default)


async def copy_strategy_template(strategy: str) -> str:
    """
    Look up template `.yml` file for a particular strategy in `hummingbot/templates` and copy it to the `conf` folder.
    The file name is `conf_{STRATEGY}_strategy_{INDEX}.yml`
    :return: The newly created file name
    """
    old_path = get_strategy_template_path(strategy)
    i = 0
    new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
    new_path = join(CONF_FILE_PATH, new_fname)
    while isfile(new_path):
        new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
        new_path = join(CONF_FILE_PATH, new_fname)
        i += 1
    shutil.copy(old_path, new_path)
    return new_fname


def get_strategy_template_path(strategy: str) -> str:
    """
    Given the strategy name, return its template config `yml` file name.
    """
    return join(TEMPLATE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_TEMPLATE.yml")


def get_erc20_token_addresses(trading_pairs: List[str]):

    with open(TOKEN_ADDRESSES_FILE_PATH) as f:
        try:
            data: Dict[str, str] = json.load(f)
            overrides: Dict[str, str] = global_config_map.get("ethereum_token_overrides").value
            if overrides is not None:
                data.update(overrides)
            addresses = [data[trading_pair] for trading_pair in trading_pairs if trading_pair in data]
            return addresses
        except Exception as e:
            logging.getLogger().error(e, exc_info=True)


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    """
    Helper function to merge a few dictionaries into an ordered dictionary.
    """
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_strategy_config_map(strategy: str) -> Optional[Dict[str, ConfigVar]]:
    """
    Given the name of a strategy, find and load strategy-specific config map.
    """
    if strategy is None:
        return None
    try:
        cm_key = f"{strategy}_config_map"
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.{cm_key}",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, cm_key)
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def get_strategy_starter_file(strategy: str) -> Callable:
    """
    Given the name of a strategy, find and load the `start` function in
    `hummingbot/strategy/{STRATEGY_NAME}/start.py` file.
    """
    if strategy is None:
        return lambda: None
    try:
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.start",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, "start")
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def load_required_configs(*args) -> OrderedDict:
    """
    Go through `in_memory_config_map`, `strategy_config_map`, and `global_config_map` in order to list all of the
    config settings required by the bot.
    """
    from hummingbot.client.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    current_strategy_file_path = in_memory_config_map.get("strategy_file_path").value
    if current_strategy is None or current_strategy_file_path is None:
        return _merge_dicts(in_memory_config_map)
    else:
        strategy_config_map = get_strategy_config_map(current_strategy)
        # create an ordered dict where `strategy` is inserted first
        # so that strategy-specific configs are prompted first and populate required_exchanges
        return _merge_dicts(in_memory_config_map, strategy_config_map, global_config_map)


def read_configs_from_yml(strategy_file_path: Optional[str] = None):
    """
    Read global config and selected strategy yml files and save the values to corresponding config map
    If a yml file is outdated, it gets reformatted with the new template
    """
    from hummingbot.client.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    strategy_config_map: Optional[Dict[str, ConfigVar]] = get_strategy_config_map(current_strategy)

    def load_yml_into_cm(yml_path: str, template_file_path: str, cm: Dict[str, ConfigVar]):
        try:
            with open(yml_path) as stream:
                data = yaml_parser.load(stream) or {}
                conf_version = data.get("template_version", 0)

            with open(template_file_path, "r") as template_fd:
                template_data = yaml_parser.load(template_fd)
                template_version = template_data.get("template_version", 0)

            for key in template_data:
                if key in {"wallet", "template_version"}:
                    continue

                cvar = cm.get(key)
                if cvar is None:
                    logging.getLogger().error(f"Cannot find corresponding config to key {key} in template.")
                    continue

                # Skip this step since the values are not saved in the yml file
                if cvar.is_secure:
                    continue

                val_in_file = data.get(key)
                if key not in data and cvar.migration_default is not None:
                    cvar.value = cvar.migration_default
                else:
                    cvar.value = parse_cvar_value(cvar, val_in_file)
                if val_in_file is not None and not cvar.validate(str(cvar.value)):
                    # Instead of raising an exception, simply skip over this variable and wait till the user is prompted
                    logging.getLogger().error("Invalid value %s for config variable %s" % (val_in_file, cvar.key))
                    cvar.value = None

            if conf_version < template_version:
                # delete old config file
                if isfile(yml_path):
                    unlink(yml_path)
                # copy the new file template
                shutil.copy(template_file_path, yml_path)
                # save the old variables into the new config file
                safe_ensure_future(save_to_yml(yml_path, cm))
        except Exception as e:
            logging.getLogger().error("Error loading configs. Your config file may be corrupt. %s" % (e,),
                                      exc_info=True)

    load_yml_into_cm(GLOBAL_CONFIG_PATH, join(TEMPLATE_PATH, "conf_global_TEMPLATE.yml"), global_config_map)

    if strategy_file_path:
        strategy_template_path = get_strategy_template_path(current_strategy)
        load_yml_into_cm(join(CONF_FILE_PATH, strategy_file_path), strategy_template_path, strategy_config_map)


async def save_to_yml(yml_path: str, cm: Dict[str, ConfigVar]):
    """
    Write current config saved a single config map into each a single yml file
    """
    try:
        with open(yml_path) as stream:
            data = yaml_parser.load(stream) or {}
            for key in cm:
                cvar = cm.get(key)
                if cvar.is_secure:
                    if cvar.value is not None and not encrypted_config_file_exists(cvar):
                        from hummingbot.client.config.in_memory_config_map import in_memory_config_map
                        password = in_memory_config_map.get("password").value
                        encrypt_n_save_config_value(cvar, password)
                    if key in data:
                        data.pop(key)
                elif type(cvar.value) == Decimal:
                    data[key] = float(cvar.value)
                else:
                    data[key] = cvar.value
            with open(yml_path, "w+") as outfile:
                yaml_parser.dump(data, outfile)
    except Exception as e:
        logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)


async def write_config_to_yml():
    """
    Write current config saved in all config maps into each corresponding yml file
    """
    from hummingbot.client.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    strategy_file_path = in_memory_config_map.get("strategy_file_path").value

    if current_strategy is not None and strategy_file_path is not None:
        strategy_config_map = get_strategy_config_map(current_strategy)
        strategy_file_path = join(CONF_FILE_PATH, strategy_file_path)
        await save_to_yml(strategy_file_path, strategy_config_map)

    await save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)


async def create_yml_files():
    """
    Copy `hummingbot_logs.yml` and `conf_global.yml` templates to the `conf` directory on start up
    """
    for fname in listdir(TEMPLATE_PATH):
        if "_TEMPLATE" in fname and CONF_POSTFIX not in fname:
            stripped_fname = fname.replace("_TEMPLATE", "")
            template_path = join(TEMPLATE_PATH, fname)
            conf_path = join(CONF_FILE_PATH, stripped_fname)
            if not isfile(conf_path):
                shutil.copy(template_path, conf_path)

            # Only overwrite log config. Updating `conf_global.yml` is handled by `read_configs_from_yml`
            if conf_path.endswith("hummingbot_logs.yml"):
                with open(template_path, "r") as template_fd:
                    template_data = yaml_parser.load(template_fd)
                    template_version = template_data.get("template_version", 0)
                with open(conf_path, "r") as conf_fd:
                    conf_version = 0
                    try:
                        conf_data = yaml_parser.load(conf_fd)
                        conf_version = conf_data.get("template_version", 0)
                    except Exception:
                        pass
                if conf_version < template_version:
                    shutil.copy(template_path, conf_path)
