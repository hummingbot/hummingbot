from decimal import Decimal
from typing import Any, Dict

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0008"),
    taker_percent_fee_decimal=Decimal("0.0001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

KEYS = {
    "okx_api_key":
        ConfigVar(key="okx_api_key",
                  prompt="Enter your OKX API key >>> ",
                  required_if=using_exchange("okx"),
                  is_secure=True,
                  is_connect_key=True),
    "okx_secret_key":
        ConfigVar(key="okx_secret_key",
                  prompt="Enter your OKX secret key >>> ",
                  required_if=using_exchange("okx"),
                  is_secure=True,
                  is_connect_key=True),
    "okx_passphrase":
        ConfigVar(key="okx_passphrase",
                  prompt="Enter your OKX passphrase key >>> ",
                  required_if=using_exchange("okx"),
                  is_secure=True,
                  is_connect_key=True),
}


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("instType", None) == "SPOT"
