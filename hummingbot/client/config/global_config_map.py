import random
from typing import Callable, Optional
from decimal import Decimal
import os.path
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import (
    required_exchanges,
    DEXES,
    DEFAULT_KEY_FILE_PATH,
    DEFAULT_LOG_FILE_PATH,
    SCRIPTS_PATH, EXCHANGES
)
from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_decimal
)


def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


# Required conditions
def paper_trade_disabled():
    return global_config_map.get("paper_trade_enabled").value is False


def using_exchange(exchange: str) -> Callable:
    return lambda: paper_trade_disabled() and exchange in required_exchanges


def using_wallet() -> bool:
    return paper_trade_disabled() and any([e in DEXES for e in required_exchanges])


def using_bamboo_coordinator_mode() -> bool:
    return global_config_map.get("bamboo_relay_use_coordinator").value


def validate_script_file_path(file_path: str) -> Optional[bool]:
    path, name = os.path.split(file_path)
    if path == "":
        file_path = os.path.join(SCRIPTS_PATH, file_path)
    if not os.path.isfile(file_path):
        return f"{file_path} file does not exist."


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
                  validator=validate_bool),
    "paper_trade_account_balance":
        ConfigVar(key="paper_trade_account_balance",
                  prompt="Enter paper trade balance settings (Input must be valid json: "
                         "e.g. [[\"ETH\", 10.0], [\"USDC\", 100]]) >>> ",
                  required_if=lambda: False,
                  type_str="json",
                  ),
    "binance_api_key":
        ConfigVar(key="binance_api_key",
                  prompt="Enter your Binance API key >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_api_secret":
        ConfigVar(key="binance_api_secret",
                  prompt="Enter your Binance API secret >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True,
                  is_connect_key=True),
    "coinbase_pro_api_key":
        ConfigVar(key="coinbase_pro_api_key",
                  prompt="Enter your Coinbase API key >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "coinbase_pro_secret_key":
        ConfigVar(key="coinbase_pro_secret_key",
                  prompt="Enter your Coinbase secret key >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "coinbase_pro_passphrase":
        ConfigVar(key="coinbase_pro_passphrase",
                  prompt="Enter your Coinbase passphrase >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "huobi_api_key":
        ConfigVar(key="huobi_api_key",
                  prompt="Enter your Huobi API key >>> ",
                  required_if=using_exchange("huobi"),
                  is_secure=True,
                  is_connect_key=True),
    "huobi_secret_key":
        ConfigVar(key="huobi_secret_key",
                  prompt="Enter your Huobi secret key >>> ",
                  required_if=using_exchange("huobi"),
                  is_secure=True,
                  is_connect_key=True),
    "liquid_api_key":
        ConfigVar(key="liquid_api_key",
                  prompt="Enter your Liquid API key >>> ",
                  required_if=using_exchange("liquid"),
                  is_secure=True,
                  is_connect_key=True),
    "liquid_secret_key":
        ConfigVar(key="liquid_secret_key",
                  prompt="Enter your Liquid secret key >>> ",
                  required_if=using_exchange("liquid"),
                  is_secure=True,
                  is_connect_key=True),
    "bamboo_relay_use_coordinator":
        ConfigVar(key="bamboo_relay_use_coordinator",
                  prompt="Would you like to use the Bamboo Relay Coordinator? (Yes/No) >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "bamboo_relay_pre_emptive_soft_cancels":
        ConfigVar(key="bamboo_relay_pre_emptive_soft_cancels",
                  prompt="Would you like to pre-emptively soft cancel orders? (Yes/No) >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "bittrex_api_key":
        ConfigVar(key="bittrex_api_key",
                  prompt="Enter your Bittrex API key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True,
                  is_connect_key=True),
    "bittrex_secret_key":
        ConfigVar(key="bittrex_secret_key",
                  prompt="Enter your Bittrex secret key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True,
                  is_connect_key=True),
    "kucoin_api_key":
        ConfigVar(key="kucoin_api_key",
                  prompt="Enter your KuCoin API key >>> ",
                  required_if=using_exchange("kucoin"),
                  is_secure=True,
                  is_connect_key=True),
    "kucoin_secret_key":
        ConfigVar(key="kucoin_secret_key",
                  prompt="Enter your KuCoin secret key >>> ",
                  required_if=using_exchange("kucoin"),
                  is_secure=True,
                  is_connect_key=True),
    "kucoin_passphrase":
        ConfigVar(key="kucoin_passphrase",
                  prompt="Enter your KuCoin passphrase >>> ",
                  required_if=using_exchange("kucoin"),
                  is_secure=True,
                  is_connect_key=True),
    "eterbase_api_key":
        ConfigVar(key="eterbase_api_key",
                  prompt="Enter your Eterbase API key >>> ",
                  required_if=using_exchange("eterbase"),
                  is_secure=True,
                  is_connect_key=True),
    "eterbase_secret_key":
        ConfigVar(key="eterbase_secret_key",
                  prompt="Enter your Eterbase secret key >>> ",
                  required_if=using_exchange("eterbase"),
                  is_secure=True,
                  is_connect_key=True),
    "eterbase_account":
        ConfigVar(key="eterbase_account",
                  prompt="Enter your Eterbase account >>> ",
                  required_if=using_exchange("eterbase"),
                  is_secure=True,
                  is_connect_key=True),
    "kraken_api_key":
        ConfigVar(key="kraken_api_key",
                  prompt="Enter your Kraken API key >>> ",
                  required_if=using_exchange("kraken"),
                  is_secure=True,
                  is_connect_key=True),
    "kraken_secret_key":
        ConfigVar(key="kraken_secret_key",
                  prompt="Enter your Kraken secret key >>> ",
                  required_if=using_exchange("kraken"),
                  is_secure=True,
                  is_connect_key=True),
    "celo_address":
        ConfigVar(key="celo_address",
                  prompt="Enter your Celo account address >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  is_connect_key=True),
    "celo_password":
        ConfigVar(key="celo_password",
                  prompt="Enter your Celo account password >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map["celo_address"].value is not None,
                  is_secure=True,
                  is_connect_key=True),
    "ethereum_wallet":
        ConfigVar(key="ethereum_wallet",
                  prompt="Enter your wallet private key >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  is_connect_key=True),
    "ethereum_rpc_url":
        ConfigVar(key="ethereum_rpc_url",
                  prompt="Which Ethereum node would you like your client to connect to? >>> ",
                  required_if=lambda: global_config_map["ethereum_wallet"].value is not None),
    "ethereum_rpc_ws_url":
        ConfigVar(key="ethereum_rpc_ws_url",
                  prompt="Enter the Websocket Address of your Ethereum Node >>> ",
                  required_if=lambda: global_config_map["ethereum_rpc_url"].value is not None),
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
    "kill_switch_enabled":
        ConfigVar(key="kill_switch_enabled",
                  prompt="Would you like to enable the kill switch? (Yes/No) >>> ",
                  required_if=paper_trade_disabled,
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "kill_switch_rate":
        ConfigVar(key="kill_switch_rate",
                  prompt="At what profit/loss rate would you like the bot to stop? "
                         "(e.g. -5 equals 5 percent loss) >>> ",
                  type_str="decimal",
                  default=-100,
                  validator=lambda v: validate_decimal(v, Decimal(-100), Decimal(100)),
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
    "send_error_logs":
        ConfigVar(key="send_error_logs",
                  prompt="Would you like to send error logs to hummingbot? (Yes/No) >>> ",
                  type_str="bool",
                  default=True),
    "min_quote_order_amount":
        ConfigVar(key="min_quote_order_amount",
                  prompt=None,
                  required_if=lambda: False,
                  type_str="json",
                  ),
    # Database options
    "db_engine":
        ConfigVar(key="db_engine",
                  prompt="Please enter database engine you want to use (reference: https://docs.sqlalchemy.org/en/13/dialects/) >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  default="sqlite"),
    "db_host":
        ConfigVar(key="db_host",
                  prompt="Please enter your DB host address >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map.get("db_engine").value != "sqlite",
                  default="127.0.0.1"),
    "db_port":
        ConfigVar(key="db_port",
                  prompt="Please enter your DB port >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map.get("db_engine").value != "sqlite",
                  default="3306"),
    "db_username":
        ConfigVar(key="db_username",
                  prompt="Please enter your DB username >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map.get("db_engine").value != "sqlite",
                  default="username"),
    "db_password":
        ConfigVar(key="db_password",
                  prompt="Please enter your DB password >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map.get("db_engine").value != "sqlite",
                  default="password"),
    "db_name":
        ConfigVar(key="db_name",
                  prompt="Please enter your the name of your DB >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map.get("db_engine").value != "sqlite",
                  default="dbname"),
    "0x_active_cancels":
        ConfigVar(key="0x_active_cancels",
                  prompt="Enable active order cancellations for 0x exchanges (warning: this costs gas)?  >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "script_enabled":
        ConfigVar(key="script_enabled",
                  prompt="Would you like to enable script feature? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "script_file_path":
        ConfigVar(key="script_file_path",
                  prompt='Enter path to your script file >>> ',
                  type_str="str",
                  required_if=lambda: global_config_map["script_enabled"].value,
                  validator=validate_script_file_path),
    "balance_asset_limit":
        ConfigVar(key="balance_asset_limit",
                  prompt="Use the `balance limit` command"
                         "e.g. balance limit [EXCHANGE] [ASSET] [AMOUNT]",
                  required_if=lambda: False,
                  type_str="json",
                  default={exchange: None for exchange in EXCHANGES}),
}
