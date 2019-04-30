import json
import logging
from os.path import (
    isfile,
    join,
)
import shutil
from typing import List

from hummingbot.cli.config.config_var import ConfigVar
from hummingbot.cli.settings import (
    TEMPLATE_PATH,
    TOKEN_ADDRESSES_FILE_PATH,
    CONF_PREFIX,
    CONF_POSTFIX,
    CONF_FILE_PATH,
)


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
