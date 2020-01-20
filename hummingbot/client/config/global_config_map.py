import random
from typing import Callable
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import (
    required_exchanges,
    DEXES,
    DEFAULT_KEY_FILE_PATH,
    DEFAULT_LOG_FILE_PATH,
)
from hummingbot.client.config.config_validators import is_valid_bool


def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


# Required conditions
def paper_trade_disabled():
    return global_config_map.get("paper_trade_enabled").value is False


def using_strategy(strategy: str) -> Callable:
    return lambda: global_config_map.get("strategy").value == strategy


def using_exchange(exchange: str) -> Callable:
    return lambda: paper_trade_disabled() and exchange in required_exchanges


def using_wallet() -> bool:
    return paper_trade_disabled() and any([e in DEXES for e in required_exchanges])


def using_bamboo_coordinator_mode() -> bool:
    return global_config_map.get("bamboo_relay_use_coordinator").value


# Main global config store
global_config_map = {
    # The variables below are usually not prompted during setup process
    "client_id":
        ConfigVar(key="client_id",
                  prompt=None,
                  required_if=lambda: False,
                  default=generate_client_id()),
    "log_level":
        ConfigVar(key="log_level",
                  prompt=None,
                  required_if=lambda: False,
                  default="INFO"),
    "debug_console":
        ConfigVar(key="debug_console",
                  prompt=None,
                  type_str="bool",
                  required_if=lambda: False,
                  default=False),
    "strategy_report_interval":
        ConfigVar(key="strategy_report_interval",
                  prompt=None,
                  type_str="float",
                  required_if=lambda: False,
                  default=900),
    "logger_override_whitelist":
        ConfigVar(key="logger_override_whitelist",
                  prompt=None,
                  required_if=lambda: False,
                  default=["hummingbot.strategy",
                           "hummingbot.market",
                           "hummingbot.wallet",
                           "conf"
                           ],
                  type_str="list"),
    "key_file_path":
        ConfigVar(key="key_file_path",
                  prompt=f"Where would you like to save your private key file? "
                         f"(default '{DEFAULT_KEY_FILE_PATH}') >>> ",
                  required_if=lambda: False,
                  default=DEFAULT_KEY_FILE_PATH),
    "log_file_path":
        ConfigVar(key="log_file_path",
                  prompt=f"Where would you like to save your logs? (default '{DEFAULT_LOG_FILE_PATH}') >>> ",
                  required_if=lambda: False,
                  default=DEFAULT_LOG_FILE_PATH),

    # Required by chosen CEXes or DEXes
    "paper_trade_enabled":
        ConfigVar(key="paper_trade_enabled",
                  prompt="Enable paper trading mode (Yes/No) ? >>> ",
                  type_str="bool",
                  default=False,
                  required_if=lambda: True,
                  validator=is_valid_bool),
    "paper_trade_account_balance":
        ConfigVar(key="paper_trade_account_balance",
                  prompt="Enter paper trade balance settings (Input must be valid json: "
                         "e.g. [[\"ETH\", 10.0], [\"USDC\", 100]]) >>> ",
                  required_if=lambda: False,
                  type_str="json",
                  default=[["USDT", 3000],
                           ["ONE", 1000],
                           ["BTC", 1],
                           ["ETH", 10],
                           ["WETH", 10],
                           ["USDC", 3000],
                           ["TUSD", 3000],
                           ["PAX", 3000]]),
    "binance_api_key":
        ConfigVar(key="binance_api_key",
                  prompt="Enter your Binance API key >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True),
    "binance_api_secret":
        ConfigVar(key="binance_api_secret",
                  prompt="Enter your Binance API secret >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True),
    "coinbase_pro_api_key":
        ConfigVar(key="coinbase_pro_api_key",
                  prompt="Enter your Coinbase API key >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True),
    "coinbase_pro_secret_key":
        ConfigVar(key="coinbase_pro_secret_key",
                  prompt="Enter your Coinbase secret key >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True),
    "coinbase_pro_passphrase":
        ConfigVar(key="coinbase_pro_passphrase",
                  prompt="Enter your Coinbase passphrase >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True),
    "huobi_api_key":
        ConfigVar(key="huobi_api_key",
                  prompt="Enter your Huobi API key >>> ",
                  required_if=using_exchange("huobi"),
                  is_secure=True),
    "huobi_secret_key":
        ConfigVar(key="huobi_secret_key",
                  prompt="Enter your Huobi secret key >>> ",
                  required_if=using_exchange("huobi"),
                  is_secure=True),
    "liquid_api_key":
        ConfigVar(key="liquid_api_key",
                  prompt="Enter your Liquid API key >>> ",
                  required_if=using_exchange("liquid"),
                  is_secure=True),
    "liquid_secret_key":
        ConfigVar(key="liquid_secret_key",
                  prompt="Enter your Liquid secret key >>> ",
                  required_if=using_exchange("liquid"),
                  is_secure=True),
    "idex_api_key":
        ConfigVar(key="idex_api_key",
                  prompt="Enter your IDEX API key >>> ",
                  required_if=using_exchange("idex"),
                  is_secure=True),
    "bamboo_relay_use_coordinator":
        ConfigVar(key="bamboo_relay_use_coordinator",
                  prompt="Would you like to use the Bamboo Relay Coordinator? (Yes/No) >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "bamboo_relay_pre_emptive_soft_cancels":
        ConfigVar(key="bamboo_relay_pre_emptive_soft_cancels",
                  prompt="Would you like to pre-emptively soft cancel orders? (Yes/No) >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "bittrex_api_key":
        ConfigVar(key="bittrex_api_key",
                  prompt="Enter your Bittrex API key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True),
    "bittrex_secret_key":
        ConfigVar(key="bittrex_secret_key",
                  prompt="Enter your Bittrex secret key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True),
    "bitcoin_com_api_key":
        ConfigVar(key="bitcoin_com_api_key",
                  prompt="Enter your bitcoin_com API key >>> ",
                  required_if=using_exchange("bitcoin_com"),
                  is_secure=True),
    "bitcoin_com_secret_key":
        ConfigVar(key="bitcoin_com_secret_key",
                  prompt="Enter your bitcoin_com secret key >>> ",
                  required_if=using_exchange("bitcoin_com"),
                  is_secure=True),
    "wallet":
        ConfigVar(key="wallet",
                  prompt="Would you like to import an existing wallet or create a new wallet? (import/create) >>> ",
                  required_if=using_wallet,
                  is_secure=True),
    "ethereum_rpc_url":
        ConfigVar(key="ethereum_rpc_url",
                  prompt="Which Ethereum node would you like your client to connect to? >>> ",
                  required_if=using_wallet),
    "ethereum_chain_name":
        ConfigVar(key="ethereum_chain_name",
                  prompt="What is your preferred ethereum chain name? >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  default="MAIN_NET"),
    "ethereum_token_overrides":
        ConfigVar(key="ethereum_token_overrides",
                  prompt="What is your preferred ethereum token overrides? >>> ",
                  type_str="json",
                  required_if=lambda: False,
                  default={}),
    # Whether or not to invoke cancel_all on exit if marketing making on a open order book DEX (e.g. Radar Relay)
    "on_chain_cancel_on_exit":
        ConfigVar(key="on_chain_cancel_on_exit",
                  prompt="Would you like to cancel transactions on chain if using an open order books exchanges? >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False),
    "exchange_rate_conversion":
        ConfigVar(key="exchange_rate_conversion",
                  prompt="Enter your custom exchange rate conversion settings (Input must be valid json) >>> ",
                  required_if=lambda: False,
                  type_str="json",
                  default=[["USD", 1.0, "manual"],
                           ["DAI", 1.0, "coin_gecko_api"],
                           ["USDT", 1.0, "coin_gecko_api"],
                           ["USDC", 1.0, "coin_gecko_api"],
                           ["TUSD", 1.0, "coin_gecko_api"]]),
    "exchange_rate_fetcher":
        ConfigVar(key="exchange_rate_fetcher",
                  prompt="Enter your custom exchange rate fetcher settings >>> ",
                  required_if=lambda: False,
                  type_str="list",
                  default=[["ETH", "coin_gecko_api"],
                           ["DAI", "coin_gecko_api"]]),
    "kill_switch_enabled":
        ConfigVar(key="kill_switch_enabled",
                  prompt="Would you like to enable the kill switch? (Yes/No) >>> ",
                  required_if=paper_trade_disabled,
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "kill_switch_rate":
        ConfigVar(key="kill_switch_rate",
                  prompt="At what profit/loss rate would you like the bot to stop? "
                         "(e.g. -0.05 equals 5 percent loss) >>> ",
                  type_str="float",
                  default=-1,
                  required_if=lambda: global_config_map["kill_switch_enabled"].value),
    "telegram_enabled":
        ConfigVar(key="telegram_enabled",
                  prompt="Would you like to enable telegram? >>> ",
                  type_str="bool",
                  default=False,
                  required_if=lambda: False),
    "telegram_token":
        ConfigVar(key="telegram_token",
                  prompt="What is your telegram token? >>> ",
                  required_if=lambda: False),
    "telegram_chat_id":
        ConfigVar(key="telegram_chat_id",
                  prompt="What is your telegram chat id? >>> ",
                  required_if=lambda: False),
    "exchange_rate_default_data_feed":
        ConfigVar(key="exchange_rate_default_data_feed",
                  prompt="What is your default exchange rate data feed name? >>> ",
                  required_if=lambda: False,
                  default="coin_gecko_api"),
    "send_error_logs":
        ConfigVar(key="send_error_logs",
                  prompt="Would you like to send error logs to hummingbot? (Yes/No) >>> ",
                  type_str="bool",
                  default=True),
}
