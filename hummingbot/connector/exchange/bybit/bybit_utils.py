from typing import Optional

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.exchange.bybit import bybit_constants as CONSTANTS

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-CAD"

# Bybit fees: https://help.bybit.com/hc/en-us/articles/360039261154
# Fees have to be expressed as percent value
DEFAULT_FEES = [0, 0.1]


# USE_ETHEREUM_WALLET not required because default value is false
# FEE_TYPE not required because default value is Percentage
# FEE_TOKEN not required because the fee is not flat


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def rest_api_url_for_endpoint(endpoint: str, domain: Optional[str]) -> str:
    variant = domain if domain else "bybit_main"
    return CONSTANTS.REST_URLS.get(variant) + CONSTANTS.REST_API_VERSION + endpoint


def wss_url(connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "bybit_main"
    return CONSTANTS.WSS_URLS.get(variant)


KEYS = {
    "bybit_api_key":
        ConfigVar(key="bybit_api_key",
                  prompt="Enter your Bybit API key >>> ",
                  required_if=using_exchange("bybit"),
                  is_secure=True,
                  is_connect_key=True),
    "bybit_secret_key":
        ConfigVar(key="bybit_secret_key",
                  prompt="Enter your Bybit secret key >>> ",
                  required_if=using_exchange("bybit"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["bybit_testnet"]
OTHER_DOMAINS_PARAMETER = {"bybit_testnet": "bybit_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bybit_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bybit_testnet": [0, 0.1]}
OTHER_DOMAINS_KEYS = {
    "bybit_testnet": {
        "bybit_testnet_api_key":
            ConfigVar(key="bybit_testnet_api_key",
                      prompt="Enter your Bybit API key >>> ",
                      required_if=using_exchange("bybit_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "bybit_testnet_secret_key":
            ConfigVar(key="bybit_testnet_secret_key",
                      prompt="Enter your Bybit secret key >>> ",
                      required_if=using_exchange("bybit_testnet"),
                      is_secure=True,
                      is_connect_key=True),
    }
}
