from decimal import Decimal
from typing import Any, Dict

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status", None) == "TRADING" and "SPOT" in exchange_info.get("permissions", list())


KEYS = {
    "bybit_api_key":
        ConfigVar(key="bybit_api_key",
                  prompt="Enter your bybit API key >>> ",
                  required_if=using_exchange("bybit"),
                  is_secure=True,
                  is_connect_key=True),
    "bybit_api_secret":
        ConfigVar(key="bybit_api_secret",
                  prompt="Enter your bybit API secret >>> ",
                  required_if=using_exchange("bybit"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["bybit_testnet"]
OTHER_DOMAINS_PARAMETER = {"bybit_testnet": None}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bybit_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bybit_testnet": [0.1, 0.1]}
OTHER_DOMAINS_KEYS = {"bybit_testnet": {
    "bybit_testnet_api_key":
        ConfigVar(key="bybit_testnet_api_key",
                  prompt="Enter your Bybit Testnet API key >>> ",
                  required_if=using_exchange("bybit_testnet"),
                  is_secure=True,
                  is_connect_key=True),
    "bybit_testnet_api_secret":
        ConfigVar(key="bybit_testnet_api_secret",
                  prompt="Enter your Bybit Testnet API secret >>> ",
                  required_if=using_exchange("bybit_testnet"),
                  is_secure=True,
                  is_connect_key=True),
}}
