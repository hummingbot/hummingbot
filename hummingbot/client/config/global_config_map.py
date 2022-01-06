import random
import re
from typing import Callable, Optional
from decimal import Decimal
import os.path
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange as using_exchange_pointer
from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_decimal
)
from hummingbot.client.settings import AllConnectorSettings, DEFAULT_KEY_FILE_PATH, DEFAULT_LOG_FILE_PATH
from hummingbot.core.rate_oracle.rate_oracle import RateOracleSource, RateOracle


def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


def using_exchange(exchange: str) -> Callable:
    return using_exchange_pointer(exchange)


def validate_script_file_path(file_path: str) -> Optional[bool]:
    import hummingbot.client.settings as settings
    path, name = os.path.split(file_path)
    if path == "":
        file_path = os.path.join(settings.SCRIPTS_PATH, file_path)
    if not os.path.isfile(file_path):
        return f"{file_path} file does not exist."


def connector_keys():
    from hummingbot.client.settings import AllConnectorSettings
    all_keys = {}
    for connector_setting in AllConnectorSettings.get_connector_settings().values():
        all_keys.update(connector_setting.config_keys)
    return all_keys


def validate_rate_oracle_source(value: str) -> Optional[str]:
    if value not in (r.name for r in RateOracleSource):
        return f"Invalid source, please choose value from {','.join(r.name for r in RateOracleSource)}"


def rate_oracle_source_on_validated(value: str):
    RateOracle.source = RateOracleSource[value]


def validate_color(value: str) -> Optional[str]:
    if not re.search(r'^#(?:[0-9a-fA-F]{2}){3}$', value):
        return "Invalid color code"


def global_token_on_validated(value: str):
    RateOracle.global_token = value.upper()


def global_token_symbol_on_validated(value: str):
    RateOracle.global_token_symbol = value


# Main global config store
main_config_map = {
    # The variables below are usually not prompted during setup process
    "instance_id":
        ConfigVar(key="instance_id",
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
                  prompt="What is your preferred ethereum chain name (MAIN_NET, KOVAN)? >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=lambda s: None if s in {"MAIN_NET", "KOVAN"} else "Invalid chain name.",
                  default="MAIN_NET"),
    "ethereum_token_list_url":
        ConfigVar(key="ethereum_token_list_url",
                  prompt="Specify token list url of a list available on https://tokenlists.org/ >>> ",
                  type_str="str",
                  required_if=lambda: global_config_map["ethereum_wallet"].value is not None,
                  default="https://defi.cmc.eth.link/"),
    "kill_switch_enabled":
        ConfigVar(key="kill_switch_enabled",
                  prompt="Would you like to enable the kill switch? (Yes/No) >>> ",
                  required_if=lambda: False,
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
    "autofill_import":
        ConfigVar(key="autofill_import",
                  prompt="What to auto-fill in the prompt after each import command? (start/config) >>> ",
                  type_str="str",
                  default=None,
                  validator=lambda s: None if s in {"start",
                                                    "config"} else "Invalid auto-fill prompt.",
                  required_if=lambda: False),
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
                  default={exchange: None for exchange in AllConnectorSettings.get_exchange_names()}),
    "manual_gas_price":
        ConfigVar(key="manual_gas_price",
                  prompt="Enter fixed gas price (in Gwei) you want to use for Ethereum transactions >>> ",
                  required_if=lambda: False,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, Decimal(0), inclusive=False),
                  default=50),
    "gateway_api_host":
        ConfigVar(key="gateway_api_host",
                  prompt=None,
                  required_if=lambda: False,
                  default='localhost'),
    "gateway_api_port":
        ConfigVar(key="gateway_api_port",
                  prompt="Please enter your Gateway API port >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  default="5000"),
    "heartbeat_enabled":
        ConfigVar(key="heartbeat_enabled",
                  prompt="Do you want to enable aggregated order and trade data collection? >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  validator=validate_bool,
                  default=True),
    "heartbeat_interval_min":
        ConfigVar(key="heartbeat_interval_min",
                  prompt="How often do you want Hummingbot to send aggregated order and trade data (in minutes, "
                         "e.g. enter 5 for once every 5 minutes)? >>> ",
                  required_if=lambda: False,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, Decimal(0), inclusive=False),
                  default=Decimal("15")),
    "command_shortcuts":
        ConfigVar(key="command_shortcuts",
                  prompt=None,
                  required_if=lambda: False,
                  type_str="list"),
    "rate_oracle_source":
        ConfigVar(key="rate_oracle_source",
                  prompt=f"What source do you want rate oracle to pull data from? "
                         f"({','.join(r.name for r in RateOracleSource)}) >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_rate_oracle_source,
                  on_validated=rate_oracle_source_on_validated,
                  default=RateOracleSource.binance.name),
    "global_token":
        ConfigVar(key="global_token",
                  prompt="What is your default display token? (e.g. USD,EUR,BTC)  >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  on_validated=global_token_on_validated,
                  default="USD"),
    "global_token_symbol":
        ConfigVar(key="global_token_symbol",
                  prompt="What is your default display token symbol? (e.g. $,€)  >>> ",
                  type_str="str",
                  required_if=lambda: False,
                  on_validated=global_token_symbol_on_validated,
                  default="$"),
    "rate_limits_share_pct":
        ConfigVar(key="rate_limits_share_pct",
                  prompt="What percentage of API rate limits do you want to allocate to this bot instance? "
                         "(Enter 50 to indicate 50%)  >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 1, 100, inclusive=True),
                  required_if=lambda: False,
                  default=Decimal("100")),
    "create_command_timeout":
        ConfigVar(key="create_command_timeout",
                  prompt="Network timeout when fetching the minimum order amount"
                         " in the create command (in seconds)  >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  required_if=lambda: False,
                  default=Decimal("10")),
    "other_commands_timeout":
        ConfigVar(key="other_commands_timeout",
                  prompt="Network timeout to apply to the other commands' API calls"
                         " (i.e. import, connect, balance, history; in seconds)  >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  required_if=lambda: False,
                  default=Decimal("30")),
}

key_config_map = connector_keys()

color_config_map = {
    # The variables below are usually not prompted during setup process
    "top-pane":
        ConfigVar(key="top-pane",
                  prompt="What is the background color of the top pane? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#000000"),
    "bottom-pane":
        ConfigVar(key="bottom-pane",
                  prompt="What is the background color of the bottom pane? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#000000"),
    "output-pane":
        ConfigVar(key="output-pane",
                  prompt="What is the background color of the output pane? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#282C2F"),
    "input-pane":
        ConfigVar(key="input-pane",
                  prompt="What is the background color of the input pane? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#151819"),
    "logs-pane":
        ConfigVar(key="logs-pane",
                  prompt="What is the background color of the logs pane? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#151819"),
    "terminal-primary":
        ConfigVar(key="terminal-primary",
                  prompt="What is the terminal primary color? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#00FFE5"),
    "primary-label":
        ConfigVar(key="primary-label",
                  prompt="What is the background color for primary label? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#5FFFD7"),
    "secondary-label":
        ConfigVar(key="secondary-label",
                  prompt="What is the background color for secondary label? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#FFFFFF"),
    "success-label":
        ConfigVar(key="success-label",
                  prompt="What is the background color for success label? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#5FFFD7"),
    "warning-label":
        ConfigVar(key="warning-label",
                  prompt="What is the background color for warning label? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#FFFF00"),
    "info-label":
        ConfigVar(key="info-label",
                  prompt="What is the background color for info label? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#5FD7FF"),
    "error-label":
        ConfigVar(key="error-label",
                  prompt="What is the background color for error label? ",
                  type_str="str",
                  required_if=lambda: False,
                  validator=validate_color,
                  default="#FF0000"),
}

paper_trade_config_map = {
    "paper_trade_exchanges":
        ConfigVar(key="paper_trade_exchanges",
                  prompt=None,
                  required_if=lambda: False,
                  default=["binance",
                           "kucoin",
                           "ascend_ex",
                           "gate_io",
                           ],
                  type_str="list"),
    "paper_trade_account_balance":
        ConfigVar(key="paper_trade_account_balance",
                  prompt="Enter paper trade balance settings (Input must be valid json: "
                         "e.g. [[\"ETH\", 10.0], [\"USDC\", 100]]) >>> ",
                  required_if=lambda: False,
                  type_str="json",
                  ),
}

global_config_map = {**key_config_map, **main_config_map, **color_config_map, **paper_trade_config_map}
