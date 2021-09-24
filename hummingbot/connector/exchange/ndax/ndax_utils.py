from typing import Optional

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-CAD"
HUMMINGBOT_ID_PREFIX = 777

# NDAX fees: https://ndax.io/fees
# Fees have to be expressed as percent value
DEFAULT_FEES = [0.2, 0.2]


# USE_ETHEREUM_WALLET not required because default value is false
# FEE_TYPE not required because default value is Percentage
# FEE_TOKEN not required because the fee is not flat


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    ts_micro_sec: int = get_tracking_nonce()
    return f"{HUMMINGBOT_ID_PREFIX}{ts_micro_sec}"


def rest_api_url(connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "ndax_main"
    return CONSTANTS.REST_URLS.get(variant)


def wss_url(connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "ndax_main"
    return CONSTANTS.WSS_URLS.get(variant)


KEYS = {
    "ndax_uid":
        ConfigVar(key="ndax_uid",
                  prompt="Enter your NDAX user ID (uid) >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=True,
                  is_connect_key=True),
    "ndax_account_name":
        ConfigVar(key="ndax_account_name",
                  prompt="Enter the name of the account you want to use >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=True,
                  is_connect_key=True),
    "ndax_api_key":
        ConfigVar(key="ndax_api_key",
                  prompt="Enter your NDAX API key >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=True,
                  is_connect_key=True),
    "ndax_secret_key":
        ConfigVar(key="ndax_secret_key",
                  prompt="Enter your NDAX secret key >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["ndax_testnet"]
OTHER_DOMAINS_PARAMETER = {"ndax_testnet": "ndax_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"ndax_testnet": "BTC-CAD"}
OTHER_DOMAINS_DEFAULT_FEES = {"ndax_testnet": [0.2, 0.2]}
OTHER_DOMAINS_KEYS = {
    "ndax_testnet": {
        "ndax_testnet_uid":
            ConfigVar(key="ndax_testnet_uid",
                      prompt="Enter your NDAX user ID (uid) >>> ",
                      required_if=using_exchange("ndax_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "ndax_testnet_account_name":
            ConfigVar(key="ndax_testnet_account_name",
                      prompt="Enter the name of the account you want to use >>> ",
                      required_if=using_exchange("ndax_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "ndax_testnet_api_key":
            ConfigVar(key="ndax_testnet_api_key",
                      prompt="Enter your NDAX API key >>> ",
                      required_if=using_exchange("ndax_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "ndax_testnet_secret_key":
            ConfigVar(key="ndax_testnet_secret_key",
                      prompt="Enter your NDAX secret key >>> ",
                      required_if=using_exchange("ndax_testnet"),
                      is_secure=True,
                      is_connect_key=True),
    }
}
