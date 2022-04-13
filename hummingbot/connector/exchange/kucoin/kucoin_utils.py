from decimal import Decimal
from typing import Any, Dict

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its market information

    :param pair_info: the market information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return pair_info.get("enableTrading", False)


KEYS = {
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
}

OTHER_DOMAINS = ["kucoin_testnet"]
OTHER_DOMAINS_PARAMETER = {"kucoin_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"kucoin_testnet": "ETH-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"kucoin_testnet": [0.1, 0.1]}
OTHER_DOMAINS_KEYS = {
    "kucoin_testnet": {
        "kucoin_testnet_api_key":
            ConfigVar(key="kucoin_testnet_api_key",
                      prompt="Enter your KuCoin API key >>> ",
                      required_if=using_exchange("kucoin_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "kucoin_testnet_secret_key":
            ConfigVar(key="kucoin_testnet_secret_key",
                      prompt="Enter your KuCoin secret key >>> ",
                      required_if=using_exchange("kucoin_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "kucoin_testnet_passphrase":
            ConfigVar(key="kucoin_testnet_passphrase",
                      prompt="Enter your KuCoin passphrase >>> ",
                      required_if=using_exchange("kucoin_testnet"),
                      is_secure=True,
                      is_connect_key=True),
    }
}
