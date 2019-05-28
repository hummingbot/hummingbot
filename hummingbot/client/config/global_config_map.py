import random
from typing import Callable
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import (
    required_exchanges,
    DEXES,
    DEFAULT_KEY_FILE_PATH,
    DEFAULT_LOG_FILE_PATH,
)


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
                                                           "hummingbot.market",
                                                           "hummingbot.wallet",
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
                                                         " wallet? (import/create) >>> ",
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
                                                  default=[["DAI", 1.0, "coincap_api"],
                                                           ["USDT", 1.0, "coincap_api"],
                                                           ["USDC", 1.0, "coincap_api"],
                                                           ["TUSD", 1.0, "coincap_api"]]),
    "exchange_rate_fetcher":            ConfigVar(key="exchange_rate_fetcher",
                                                  prompt="Enter your custom exchange rate fetcher settings >>> ",
                                                  required_if=lambda: False,
                                                  type_str="list",
                                                  default=[["ETH", "coincap_api"],
                                                           ["DAI", "coincap_api"]]),
    "stop_loss_pct":                    ConfigVar(key="stop_loss_pct",
                                                  prompt="At what percentage of loss would you like the bot to stop "
                                                         "trading? (Enter 0.03 to indicate 3%. "
                                                         "Enter -1.0 to disable) >>> ",
                                                  default=-1.0,
                                                  type_str="float"),
    "stop_loss_price_type":             ConfigVar(key="stop_loss_price_type",
                                                  prompt="What type of price data would you like to use for stop "
                                                         "loss (fixed/dynamic) ? >>> ",
                                                  required_if=lambda:
                                                      type(global_config_map.get("stop_loss_pct").value) is float and
                                                      global_config_map.get("stop_loss_pct").value >= 0,
                                                  validator=lambda v: v in {"fixed", "dynamic"}),
    "stop_loss_base_token":             ConfigVar(key="stop_loss_base_token",
                                                  prompt="Would base token would you like to use to calculate your "
                                                         "inventory value? (Default \"USD\") >>> ",
                                                  default="USD",
                                                  required_if=lambda:
                                                      global_config_map.get("stop_loss_price_type").value == "dynamic")
}

