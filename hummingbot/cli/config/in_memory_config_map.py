import logging
import ruamel.yaml
from os.path import (
    join,
    isfile,
)
from collections import OrderedDict
from typing import Dict
from os import listdir
import shutil

from hummingbot.cli.config.config_var import ConfigVar
from hummingbot.cli.config.validators import (
    is_strategy,
    is_path,
)
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


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_strategy_config_map(strategy: str) -> Dict[str, ConfigVar]:
    # Get the right config map from this file by its variable name
    return globals().get(f"{strategy}_config_map")


def load_required_configs(*args) -> OrderedDict:
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


def get_default_strategy_config_yml_path(strategy: str) -> str:
    return join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_0.yml")


# Prompt generators
def default_strategy_conf_path_prompt():
    strategy = in_memory_config_map.get("strategy").value
    return "Enter path to your strategy file (e.g. \"%s\") >>> " \
           % (get_default_strategy_config_yml_path(strategy),)


# These configs are never saved and prompted every time
in_memory_config_map = {
    # Always required
    "strategy":                         ConfigVar(key="strategy",
                                                  prompt="What is your market making strategy? >>> ",
                                                  validator=is_strategy,
                                                  on_validated=load_required_configs),
    "strategy_file_path":               ConfigVar(key="strategy_file_path",
                                                  prompt=default_strategy_conf_path_prompt,
                                                  validator=is_path,
                                                  on_validated=read_configs_from_yml)
}