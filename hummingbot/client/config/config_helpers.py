import logging
from decimal import Decimal
import ruamel.yaml
from os import (
    unlink
)
from os.path import (
    join,
    isfile
)
from collections import OrderedDict
import json
import requests
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
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.settings import (
    GLOBAL_CONFIG_PATH,
    TRADE_FEES_CONFIG_PATH,
    TEMPLATE_PATH,
    CONF_FILE_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
    TOKEN_ADDRESSES_FILE_PATH,
    CONNECTOR_SETTINGS
)
from hummingbot.client.config.security import Security
from hummingbot.core.utils.market_price import get_mid_price
from hummingbot import get_strategy_list
from eth_account import Account

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
            cvar_value = json.loads(value_json)
        else:
            cvar_value = value
        return cvar_json_migration(cvar, cvar_value)
    elif cvar.type == 'float':
        try:
            return float(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid float.", exc_info=True)
            return value
    elif cvar.type == 'decimal':
        try:
            return Decimal(str(value))
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid decimal.", exc_info=True)
            return value
    elif cvar.type == 'int':
        try:
            return int(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.", exc_info=True)
            return value
    elif cvar.type == 'bool':
        if isinstance(value, str) and value.lower() in ["true", "yes", "y"]:
            return True
        elif isinstance(value, str) and value.lower() in ["false", "no", "n"]:
            return False
        else:
            return value
    else:
        raise TypeError


def cvar_json_migration(cvar: ConfigVar, cvar_value: Any) -> Any:
    """
    A special function to migrate json config variable when its json type changes, for paper_trade_account_balance
    and min_quote_order_amount, they were List but change to Dict.
    """
    if cvar.key in ("paper_trade_account_balance", "min_quote_order_amount") and isinstance(cvar_value, List):
        results = {}
        for item in cvar_value:
            results[item[0]] = item[1]
        return results
    return cvar_value


def parse_cvar_default_value_prompt(cvar: ConfigVar) -> str:
    """
    :param cvar: ConfigVar object
    :return: text for default value prompt
    """
    if cvar.default is None:
        default = ""
    elif callable(cvar.default):
        default = cvar.default()
    elif cvar.type == 'bool' and isinstance(cvar.prompt, str) and "Yes/No" in cvar.prompt:
        default = "Yes" if cvar.default else "No"
    else:
        default = str(cvar.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


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


def get_eth_wallet_private_key() -> Optional[str]:
    ethereum_wallet = global_config_map.get("ethereum_wallet").value
    if ethereum_wallet is None or ethereum_wallet == "":
        return None
    private_key = Security._private_keys[ethereum_wallet]
    account = Account.privateKeyToAccount(private_key)
    return account.privateKey.hex()


def get_erc20_token_addresses() -> Dict[str, List]:
    token_list_url = global_config_map.get("ethereum_token_list_url").value
    address_file_path = TOKEN_ADDRESSES_FILE_PATH
    token_list = {}

    resp = requests.get(token_list_url, timeout=1)
    decoded_resp = resp.json()

    for token in decoded_resp["tokens"]:
        token_list[token["symbol"]] = [token["address"], token["decimals"]]

    try:
        with open(address_file_path) as f:
            overrides: Dict[str, str] = json.load(f)
            for token, address in overrides.items():
                override_token = token_list.get(token, [address, 18])
                token_list[token] = [address, override_token[1]]
    except FileNotFoundError:
        # create override file for first run w docker
        with open(address_file_path, "w+") as f:
            f.write(json.dumps({}))
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)

    return token_list


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    """
    Helper function to merge a few dictionaries into an ordered dictionary.
    """
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_connector_class(connector_name: str) -> Callable:
    conn_setting = CONNECTOR_SETTINGS[connector_name]
    mod = __import__(conn_setting.module_path(),
                     fromlist=[conn_setting.class_name()])
    return getattr(mod, conn_setting.class_name())


def get_strategy_config_map(strategy: str) -> Optional[Dict[str, ConfigVar]]:
    """
    Given the name of a strategy, find and load strategy-specific config map.
    """
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
        return strategy_module.start
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def load_required_configs(strategy_name) -> OrderedDict:
    strategy_config_map = get_strategy_config_map(strategy_name)
    # create an ordered dict where `strategy` is inserted first
    # so that strategy-specific configs are prompted first and populate required_exchanges
    return _merge_dicts(strategy_config_map, global_config_map)


def strategy_name_from_file(file_path: str) -> str:
    with open(file_path) as stream:
        data = yaml_parser.load(stream) or {}
        strategy = data.get("strategy")
    return strategy


def validate_strategy_file(file_path: str) -> Optional[str]:
    if not isfile(file_path):
        return f"{file_path} file does not exist."
    strategy = strategy_name_from_file(file_path)
    if strategy is None:
        return "Invalid configuration file or 'strategy' field is missing."
    if strategy not in get_strategy_list():
        return "Invalid strategy specified in the file."
    return None


def update_strategy_config_map_from_file(yml_path: str) -> str:
    strategy = strategy_name_from_file(yml_path)
    config_map = get_strategy_config_map(strategy)
    template_path = get_strategy_template_path(strategy)
    load_yml_into_cm(yml_path, template_path, config_map)
    return strategy


def load_yml_into_cm(yml_path: str, template_file_path: str, cm: Dict[str, ConfigVar]):
    try:
        with open(yml_path) as stream:
            data = yaml_parser.load(stream) or {}
            conf_version = data.get("template_version", 0)

        with open(template_file_path, "r") as template_fd:
            template_data = yaml_parser.load(template_fd)
            template_version = template_data.get("template_version", 0)

        for key in template_data:
            if key in {"template_version"}:
                continue

            cvar = cm.get(key)
            if cvar is None:
                logging.getLogger().error(f"Cannot find corresponding config to key {key} in template.")
                continue

            # Skip this step since the values are not saved in the yml file
            if cvar.is_secure:
                cvar.value = Security.decrypted_value(key)
                continue

            val_in_file = data.get(key)
            if (val_in_file is None or val_in_file == "") and cvar.default is not None:
                cvar.value = cvar.default
                continue

            # Todo: the proper process should be first validate the value then assign it
            cvar.value = parse_cvar_value(cvar, val_in_file)
            if cvar.value is not None:
                err_msg = cvar.validate(str(cvar.value))
                if err_msg is not None:
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
            save_to_yml(yml_path, cm)
    except Exception as e:
        logging.getLogger().error("Error loading configs. Your config file may be corrupt. %s" % (e,),
                                  exc_info=True)


def read_system_configs_from_yml():
    """
    Read global config and selected strategy yml files and save the values to corresponding config map
    If a yml file is outdated, it gets reformatted with the new template
    """
    load_yml_into_cm(GLOBAL_CONFIG_PATH, join(TEMPLATE_PATH, "conf_global_TEMPLATE.yml"), global_config_map)
    load_yml_into_cm(TRADE_FEES_CONFIG_PATH, join(TEMPLATE_PATH, "conf_fee_overrides_TEMPLATE.yml"),
                     fee_overrides_config_map)
    # In case config maps get updated (due to default values)
    save_system_configs_to_yml()


def save_system_configs_to_yml():
    save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)
    save_to_yml(TRADE_FEES_CONFIG_PATH, fee_overrides_config_map)


def save_to_yml(yml_path: str, cm: Dict[str, ConfigVar]):
    """
    Write current config saved a single config map into each a single yml file
    """
    try:
        with open(yml_path) as stream:
            data = yaml_parser.load(stream) or {}
            for key in cm:
                cvar = cm.get(key)
                if cvar.is_secure:
                    Security.update_secure_config(key, cvar.value)
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


async def write_config_to_yml(strategy_name, strategy_file_name):
    strategy_config_map = get_strategy_config_map(strategy_name)
    strategy_file_path = join(CONF_FILE_PATH, strategy_file_name)
    save_to_yml(strategy_file_path, strategy_config_map)
    save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)


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


def default_min_quote(quote_asset: str) -> (str, Decimal):
    result_quote, result_amount = "USD", Decimal("11")
    min_quote_config = global_config_map["min_quote_order_amount"].value
    if min_quote_config is not None and quote_asset in min_quote_config:
        result_quote, result_amount = quote_asset, Decimal(str(min_quote_config[quote_asset]))
    return result_quote, result_amount


def minimum_order_amount(exchange: str, trading_pair: str) -> Decimal:
    base_asset, quote_asset = trading_pair.split("-")
    default_quote_asset, default_amount = default_min_quote(quote_asset)
    quote_amount = Decimal("0")
    if default_quote_asset == quote_asset:
        mid_price = get_mid_price(exchange, trading_pair)
        if mid_price is not None:
            quote_amount = default_amount / mid_price
    return round(quote_amount, 4)


def default_strategy_file_path(strategy: str) -> str:
    """
    Find the next available file name.
    :return: a default file name - `conf_{short_strategy}_{INDEX}.yml` e.g. 'conf_pure_mm_1.yml'
    """
    i = 1
    new_fname = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{i}.yml"
    new_path = join(CONF_FILE_PATH, new_fname)
    while isfile(new_path):
        new_fname = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{i}.yml"
        new_path = join(CONF_FILE_PATH, new_fname)
        i += 1
    return new_fname


def short_strategy_name(strategy: str) -> str:
    if strategy == "pure_market_making":
        return "pure_mm"
    elif strategy == "cross_exchange_market_making":
        return "xemm"
    elif strategy == "arbitrage":
        return "arb"
    else:
        return strategy


def all_configs_complete(strategy):
    strategy_map = get_strategy_config_map(strategy)
    return config_map_complete(global_config_map) and config_map_complete(strategy_map)


def config_map_complete(config_map):
    return not any(c.required and c.value is None for c in config_map.values())


def missing_required_configs(config_map):
    return [c for c in config_map.values() if c.required and c.value is None and not c.is_connect_key]


def load_all_secure_values(strategy):
    strategy_map = get_strategy_config_map(strategy)
    load_secure_values(global_config_map)
    load_secure_values(strategy_map)


def load_secure_values(config_map):
    for key, config in config_map.items():
        if config.is_secure:
            config.value = Security.decrypted_value(key)


def format_config_file_name(file_name):
    if "." not in file_name:
        return file_name + ".yml"
    return file_name


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


def secondary_market_conversion_rate(strategy) -> Decimal:
    config_map = get_strategy_config_map(strategy)
    if "secondary_to_primary_quote_conversion_rate" in config_map:
        base_rate = config_map["secondary_to_primary_base_conversion_rate"].value
        quote_rate = config_map["secondary_to_primary_quote_conversion_rate"].value
    elif "taker_to_maker_quote_conversion_rate" in config_map:
        base_rate = config_map["taker_to_maker_base_conversion_rate"].value
        quote_rate = config_map["taker_to_maker_quote_conversion_rate"].value
    else:
        return Decimal("1")
    return quote_rate / base_rate
