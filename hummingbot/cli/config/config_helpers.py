import json
from typing import List

from hummingbot.cli.settings import TOKEN_ADDRESSES_FILE_PATH

import logging
import ruamel.yaml
from os.path import (
    join,
    isfile,
)
from collections import OrderedDict
from typing import (
    Dict,
    Optional,
)
from os import listdir
import shutil

from hummingbot.cli.config.config_var import ConfigVar
from hummingbot.cli.config.global_config_map import global_config_map
from hummingbot.cli.settings import (
    GLOBAL_CONFIG_PATH,
    TEMPLATE_PATH,
    CONF_FILE_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
)

# Use ruamel.yaml to preserve order and comments in .yml file
yaml = ruamel.yaml.YAML()


def parse_cvar_value(cvar: ConfigVar, value: any):
    if cvar.type == 'str':
        return str(value)
    elif cvar.type in {"list", "dict"}:
        if isinstance(value, str):
            return eval(value)
        else:
            return value
    elif cvar.type == 'float':
        return float(value)
    elif cvar.type == 'int':
        return int(value)
    elif cvar.type == 'bool':
        if type(value) == str and value.lower() in ["true", "yes"]:
            return True
        elif type(value) == str and value.lower() in ["false", "no"]:
            return False
        else:
            return bool(value)
    else:
        raise TypeError


async def copy_strategy_template(strategy: str) -> str:
    old_path = get_strategy_template_path(strategy)
    i = 0
    new_path = join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml")
    while isfile(new_path):
        new_path = join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml")
        i += 1
    shutil.copy(old_path, new_path)
    return new_path


def get_strategy_template_path(strategy: str) -> str:
    return join(TEMPLATE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_TEMPLATE.yml")


def get_erc20_token_addresses(symbols: List[str]):
    with open(TOKEN_ADDRESSES_FILE_PATH) as f:
        try:
            data = json.load(f)
            addresses = [data[symbol] for symbol in symbols if symbol in data]
            return addresses
        except Exception as e:
            logging.getLogger().error(e, exc_info=True)


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_strategy_config_map(strategy: str) -> Optional[Dict[str, ConfigVar]]:
    # Get the right config map from this file by its variable name
    if strategy is None:
        return None
    try:
        cm_key = f"{strategy}_config_map"
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.{cm_key}",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, cm_key)
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def load_required_configs(*args) -> OrderedDict:
    from hummingbot.cli.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    current_strategy_file_path = in_memory_config_map.get("strategy_file_path").value
    if current_strategy is None or current_strategy_file_path is None:
        return _merge_dicts(in_memory_config_map)
    else:
        strategy_config_map = get_strategy_config_map(current_strategy)
        # create an ordered dict where `strategy` is inserted first
        # so that strategy-specific configs are prompted first and populate required exchanges
        return _merge_dicts(in_memory_config_map, strategy_config_map, global_config_map)


def read_configs_from_yml(strategy_file_path: str = None):
    """
    Read global config and selected strategy yml files and save the values to corresponding config map
    """
    from hummingbot.cli.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    strategy_config_map = get_strategy_config_map(current_strategy)

    def load_yml_into_cm(yml_path: str, cm: Dict[str, ConfigVar]):
        try:
            with open(yml_path) as stream:
                data = yaml.load(stream) or {}
                for key in data:
                    if key == "wallet":
                        continue
                    cvar = cm.get(key)
                    val_in_file = data.get(key)
                    if cvar is None:
                        raise ValueError(f"Cannot find corresponding config to key {key}.")
                    cvar.value = val_in_file
                    if val_in_file is not None and not cvar.validate(val_in_file):
                        logging.getLogger().error("Invalid value %s for config variable %s" %
                                                  (val_in_file, cvar.key), exc_info=True)
        except Exception as e:
            logging.getLogger().error("Error loading configs. Your config file may be corrupt. %s" % (e,),
                                      exc_info=True)

    load_yml_into_cm(GLOBAL_CONFIG_PATH, global_config_map)
    if strategy_file_path:
        load_yml_into_cm(strategy_file_path, strategy_config_map)


async def write_config_to_yml():
    """
    Write current config saved in config maps into each corresponding yml file
    """
    from hummingbot.cli.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    strategy_config_map = get_strategy_config_map(current_strategy)
    strategy_file_path = in_memory_config_map.get("strategy_file_path").value

    def save_to_yml(yml_path: str, cm: Dict[str, ConfigVar]):
        try:
            with open(yml_path) as stream:
                data = yaml.load(stream) or {}
                for key in cm:
                    cvar = cm.get(key)
                    data[key] = cvar.value
                with open(yml_path, "w+") as outfile:
                    yaml.dump(data, outfile)
        except Exception as e:
            logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)

    save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)
    save_to_yml(strategy_file_path, strategy_config_map)


async def create_yml_files():
    for fname in listdir(TEMPLATE_PATH):
        # Only copy `hummingbot_logs.yml` and `conf_global.yml` on start up
        if "_TEMPLATE" in fname and CONF_POSTFIX not in fname:
            stripped_fname = fname.replace("_TEMPLATE", "")
            template_path = join(TEMPLATE_PATH, fname)
            conf_path = join(CONF_FILE_PATH, stripped_fname)
            if not isfile(conf_path):
                shutil.copy(template_path, conf_path)
            with open(template_path, "r") as template_fd:
                template_data = yaml.load(template_fd)
                template_version = template_data.get("template_version", 0)
            with open(conf_path, "r") as conf_fd:
                conf_version = 0
                try:
                    conf_data = yaml.load(conf_fd)
                    conf_version = conf_data.get("template_version", 0)
                except Exception:
                    pass
            if conf_version < template_version:
                shutil.copy(template_path, conf_path)
