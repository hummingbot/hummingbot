import json
import logging
from os.path import (
    isfile,
    realpath,
    join,
)
import shutil
from os import listdir
import random
import ruamel.yaml
from collections import OrderedDict
from typing import (
    List,
    Dict,
    Optional,
    Callable,
)
# Use ruamel.yaml to preserve order and comments in .yml file
yaml = ruamel.yaml.YAML()


# Static values
KEYFILE_PREFIX = "key_file_"
KEYFILE_POSTFIX = ".json"
GLOBAL_CONFIG_PATH = "conf/conf_global.yml"
TOKEN_ADDRESSES_FILE_PATH = realpath(join(__file__, "../../erc20_tokens.json"))
DEFAULT_KEY_FILE_PATH = "conf/"
DEFAULT_LOG_FILE_PATH = "logs/"
DEFAULT_ETHEREUM_RPC_URL = "https://mainnet.coinalpha.com/hummingbot-test-node"
TEMPLATE_PATH = realpath(join(__file__, "../../templates/"))
CONF_FILE_PATH = "conf/"
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"

EXCHANGES = ["binance", "ddex", "radar_relay", "coinbase_pro"]
DEXES = ["ddex", "radar_relay"]
STRATEGIES = ["cross_exchange_market_making", "arbitrage"]
EXAMPLE_PAIRS = {
    "binance": "ZRXETH",
    "ddex": "ZRX-WETH",
    "radar_relay": "ZRX-WETH",
    "coinbase_pro": "ETH-USDC",
}

MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000


# Global variable
required_exchanges: List[str] = []


class ConfigVar:
    def __init__(self,
                 key: str,
                 prompt: Optional[any],
                 is_secure: bool = False,
                 default: any = None,
                 type_str: str = "str",
                 # Whether this config will be prompted during the setup process
                 required_if: Callable = lambda: True,
                 validator: Callable = lambda *args: True,
                 on_validated: Callable = lambda *args: None):
        self._prompt = prompt
        self.key = key
        self.value = None
        self.is_secure = is_secure
        self.default = default
        self.type = type_str
        self._required_if = required_if
        self._validator = validator
        self._on_validated = on_validated

    @property
    def prompt(self):
        if callable(self._prompt):
            return self._prompt()
        else:
            return self._prompt

    @property
    def required(self) -> bool:
        assert callable(self._required_if)
        return self._required_if()

    def validate(self, value: str) -> bool:
        assert callable(self._validator)
        assert callable(self._on_validated)
        valid = self._validator(value)
        if valid:
            self._on_validated(value)
        return valid


# Prompt generators
def default_strategy_conf_path_prompt():
    strategy = in_memory_config_map.get("strategy").value
    return "Enter path to your strategy file (e.g. \"%s\") >>> " \
           % (get_default_strategy_config_yml_path(strategy),)


def maker_symbol_prompt():
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    return "Enter the token symbol you would like to trade on %s (e.g. %s) >>> " \
           % (maker_market, EXAMPLE_PAIRS[maker_market])


def taker_symbol_prompt():
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    return "Enter the token symbol you would like to trade on %s (e.g. %s) >>> " \
           % (taker_market, EXAMPLE_PAIRS[taker_market])


def primary_symbol_prompt():
    primary_market = arbitrage_config_map.get("primary_market").value
    return "Enter the token symbol you would like to trade on %s (e.g. %s) >>> " \
           % (primary_market, EXAMPLE_PAIRS[primary_market])


def secondary_symbol_prompt():
    secondary_market = arbitrage_config_map.get("secondary_market").value
    return "Enter the token symbol you would like to trade on %s (e.g. %s) >>> " \
           % (secondary_market, EXAMPLE_PAIRS[secondary_market])


# Helpers
def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


# Required conditions
def using_strategy(strategy: str) -> Callable:
    return lambda: global_config_map.get("strategy").value == strategy


def using_exchange(exchange: str) -> Callable:
    return lambda: exchange in required_exchanges


def using_wallet() -> bool:
    return any([e in DEXES for e in required_exchanges])


# Validators
def is_exchange(value: str) -> bool:
    return value in EXCHANGES


def is_strategy(value: str) -> bool:
    return value in STRATEGIES


def is_path(value: str) -> bool:
    return isfile(value) and value.endswith('.yml')


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


# Strategy specific config maps TODO: put them in a separate file
cross_exchange_market_making_config_map = {
    "maker_market":                     ConfigVar(key="maker_market",
                                                  prompt="Enter your maker exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "taker_market":                     ConfigVar(key="taker_market",
                                                  prompt="Enter your taker exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "maker_market_symbol":              ConfigVar(key="maker_market_symbol",
                                                  prompt=maker_symbol_prompt),
    "taker_market_symbol":              ConfigVar(key="taker_market_symbol",
                                                  prompt=taker_symbol_prompt),
    "min_profitability":                ConfigVar(key="min_profitability",
                                                  prompt="What is the minimum profitability for you to make a trade? "\
                                                         "(Enter 0.01 to indicate 1%) >>> ",
                                                  default=0.003,
                                                  type_str="float"),
    "trade_size_override":              ConfigVar(key="trade_size_override",
                                                  prompt="What is your preferred trade size? (denominated in "
                                                         "the quote asset) >>> ",
                                                  required_if=lambda: False,
                                                  default=0.0,
                                                  type_str="float"),
    "top_depth_tolerance":              ConfigVar(key="top_depth_tolerance",
                                                  prompt="What is the maximum depth you would go into th"
                                                         "e order book to make a trade? >>> ",
                                                  type_str="list",
                                                  required_if=lambda: False,
                                                  default=[
                                                      ["^.+(USDT|USDC|USDS|DAI|PAX|TUSD)$", 1000],
                                                      ["^.+ETH$", 10],
                                                      ["^.+BTC$", 0.5],
                                                  ]),
    "active_order_canceling":           ConfigVar(key="active_order_canceling",
                                                  prompt="Do you want to actively adjust/cancel orders? (Default "\
                                                         "True, only set to False if maker market is Radar Relay) >>> ",
                                                  type_str="bool",
                                                  default=True),
    # Setting the default threshold to -1.0 when to active_order_canceling is disabled
    # prevent canceling orders after it has expired
    "cancel_order_threshold":           ConfigVar(key="cancel_order_threshold",
                                                  prompt="What is the minimum profitability to actively cancel orders? "
                                                         "(Default to -1.0, only specify when active_order_canceling "
                                                         "is disabled, value can be negative) >>> ",
                                                  default=-1.0,
                                                  type_str="float"),
    "limit_order_min_expiration":       ConfigVar(key="limit_order_min_expiration",
                                                  prompt="What is the minimum limit order expiration in seconds? "
                                                         "(Default to 130 seconds) >>> ",
                                                  default=130.0,
                                                  type_str="float")
}


arbitrage_config_map = {
    "primary_market":                   ConfigVar(key="primary_market",
                                                  prompt="Enter your primary exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "secondary_market":                 ConfigVar(key="secondary_market",
                                                  prompt="Enter your secondary exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "primary_market_symbol":            ConfigVar(key="primary_market_symbol",
                                                  prompt=primary_symbol_prompt),
    "secondary_market_symbol":          ConfigVar(key="secondary_market_symbol",
                                                  prompt=secondary_symbol_prompt),
    "min_profitability":                ConfigVar(key="min_profitability",
                                                  prompt="What is the minimum profitability for you to make a trade? "\
                                                         "(Enter 0.01 to indicate 1%) >>> ",
                                                  default=0.003,
                                                  type_str="float"),
    "trade_size_override":              ConfigVar(key="trade_size_override",
                                                  prompt="What is your preferred trade size? (denominated in "
                                                         "the quote asset) >>> ",
                                                  required_if=lambda: False,
                                                  default=0.0,
                                                  type_str="float"),
    "top_depth_tolerance":              ConfigVar(key="top_depth_tolerance",
                                                  prompt="What is the maximum depth you would go into th"
                                                         "e order book to make a trade? >>>",
                                                  type_str="list",
                                                  required_if=lambda: False,
                                                  default=[
                                                      ["^.+(USDT|USDC|USDS|DAI|PAX|TUSD)$", 1000],
                                                      ["^.+ETH$", 10],
                                                      ["^.+BTC$", 0.5],
                                                  ]),
}


# Main global config store
global_config_map = {
    # The variables below are usually not prompted during setup process
    "client_id":                        ConfigVar(key="client_id",
                                                  prompt=None,
                                                  required_if=lambda: False,
                                                  default=generate_client_id()),
    "log_level":                        ConfigVar(key="log_level",
                                                  prompt=None,
                                                  required_if=lambda: False,
                                                  default="INFO"),
    "debug_console":                    ConfigVar(key="debug_console",
                                                  prompt=None,
                                                  type_str="bool",
                                                  required_if=lambda: False,
                                                  default=False),
    "strategy_report_interval":         ConfigVar(key="strategy_report_interval",
                                                  prompt=None,
                                                  type_str="float",
                                                  required_if=lambda: False,
                                                  default=900),
    "reporting_aggregation_interval":   ConfigVar(key="reporting_aggregation_interval",
                                                  prompt=None,
                                                  default=60.0,
                                                  required_if=lambda: False,
                                                  type_str="float"),
    "reporting_log_interval":           ConfigVar(key="reporting_log_interval",
                                                  prompt=None,
                                                  default=60.0,
                                                  required_if=lambda: False,
                                                  type_str="float"),
    "logger_override_whitelist":        ConfigVar(key="logger_override_whitelist",
                                                  prompt=None,
                                                  required_if=lambda: False,
                                                  default=["hummingbot.strategy",
                                                           "wings.wallet",
                                                           "wings.market",
                                                           "conf"
                                                           ],
                                                  type_str="list"),
    "key_file_path":                    ConfigVar(key="key_file_path",
                                                  prompt="Where would you like to save your private key file? (default "
                                                         "'%s') >>> " % (DEFAULT_KEY_FILE_PATH,),
                                                  required_if=lambda: False,
                                                  default=DEFAULT_KEY_FILE_PATH),
    "log_file_path":                    ConfigVar(key="log_file_path",
                                                  prompt="Where would you like to save your logs? (default '%s') >>> "
                                                         % (DEFAULT_LOG_FILE_PATH,),
                                                  required_if=lambda: False,
                                                  default=DEFAULT_LOG_FILE_PATH),

    # Required by chosen CEXes or DEXes
    "binance_api_key":                  ConfigVar(key="binance_api_key",
                                                  prompt="Enter your Binance API key >>> ",
                                                  required_if=using_exchange("binance"),
                                                  is_secure=True),
    "binance_api_secret":               ConfigVar(key="binance_api_secret",
                                                  prompt="Enter your Binance API secret >>> ",
                                                  required_if=using_exchange("binance"),
                                                  is_secure=True),
    "coinbase_pro_api_key":             ConfigVar(key="coinbase_pro_api_key",
                                                  prompt="Enter your Coinbase API key >>> ",
                                                  required_if=using_exchange("coinbase_pro"),
                                                  is_secure=True),
    "coinbase_pro_secret_key":          ConfigVar(key="coinbase_pro_secret_key",
                                                  prompt="Enter your Coinbase secret key >>> ",
                                                  required_if=using_exchange("coinbase_pro"),
                                                  is_secure=True),
    "coinbase_pro_passphrase":          ConfigVar(key="coinbase_pro_passphrase",
                                                  prompt="Enter your Coinbase passphrase >>> ",
                                                  required_if=using_exchange("coinbase_pro"),
                                                  is_secure=True),
    "wallet":                           ConfigVar(key="wallet",
                                                  prompt="Would you like to import an existing wallet or create a new"
                                                         " wallet? (import / create) >>> ",
                                                  required_if=using_wallet,
                                                  is_secure=True),
    "ethereum_rpc_url":                 ConfigVar(key="ethereum_rpc_url",
                                                  prompt="Which Ethereum node would you like your client to connect "
                                                         "to? >>> ",
                                                  required_if=lambda: True),
    # Whether or not to invoke cancel_all on exit if marketing making on a open order book DEX (e.g. Radar Relay)
    "on_chain_cancel_on_exit":          ConfigVar(key="on_chain_cancel_on_exit",
                                                  prompt="Would you like to cancel transactions on chain if using an "
                                                         "open order books exchanges? >>> ",
                                                  required_if=lambda: False,
                                                  type_str="bool",
                                                  default=False),
    "exchange_rate_conversion":         ConfigVar(key="exchange_rate_conversion",
                                                  prompt="Enter your custom exchange rate conversion settings >>> ",
                                                  required_if=lambda: False,
                                                  type_str="list",
                                                  default=[["DAI", 1.0, "COINCAP_API"],
                                                           ["USDT", 1.0, "COINCAP_API"],
                                                           ["USDC", 1.0, "COINCAP_API"],
                                                           ["TUSD", 1.0, "COINCAP_API"]]),
    "exchange_rate_fetcher":            ConfigVar(key="exchange_rate_fetcher",
                                                  prompt="Enter your custom exchange rate fetcher settings >>> ",
                                                  required_if=lambda: False,
                                                  type_str="list",
                                                  default=[["ETH", "COINCAP_API"],
                                                           ["DAI", "COINCAP_API"]])
}


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


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


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


async def copy_strategy_template(strategy: str) -> str:
    old_path = get_strategy_template_path(strategy)
    i = 0
    new_path = join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml")
    while isfile(new_path):
        new_path = join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml")
        i += 1
    shutil.copy(old_path, new_path)
    return new_path


def get_log_file_path() -> str:
    path = global_config_map["log_file_path"].value
    return path if path is not None else DEFAULT_LOG_FILE_PATH


def get_key_file_path() -> str:
    path = global_config_map["key_file_path"].value
    return path if path is not None else DEFAULT_KEY_FILE_PATH


def get_strategy_template_path(strategy: str) -> str:
    return join(TEMPLATE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_TEMPLATE.yml")


def get_default_strategy_config_yml_path(strategy: str) -> str:
    return join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_0.yml")


def get_strategy_config_map(strategy: str) -> Dict[str, ConfigVar]:
    # Get the right config map from this file by its variable name
    return globals().get(f"{strategy}_config_map")


def get_erc20_token_addresses(symbols: List[str]):
    with open(TOKEN_ADDRESSES_FILE_PATH) as f:
        try:
            data = json.load(f)
            addresses = [data[symbol] for symbol in symbols if symbol in data]
            return addresses
        except Exception as e:
            logging.getLogger().error(e, exc_info=True)
