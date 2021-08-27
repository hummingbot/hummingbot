from typing import Optional, Dict

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

# Bybit fees: https://help.bybit.com/hc/en-us/articles/360039261154
# Fees have to be expressed as percent value
DEFAULT_FEES = [-0.025, 0.075]


# USE_ETHEREUM_WALLET not required because default value is false
# FEE_TYPE not required because default value is Percentage
# FEE_TOKEN not required because the fee is not flat

def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def is_linear_perpetual(trading_pair: str) -> bool:
    """
    Returns True if trading_pair is in USDT(Linear) Perpetual
    """
    _, quote_asset = trading_pair.split("-")
    return quote_asset == "USDT"


def rest_api_path_for_endpoint(endpoint: Dict[str, str],
                               trading_pair: Optional[str] = None) -> str:
    if trading_pair and is_linear_perpetual(trading_pair):
        market = "linear"
    else:
        market = "non_linear"

    return endpoint[market]


def rest_api_url_for_endpoint(endpoint: str, domain: Optional[str] = None) -> str:
    variant = domain if domain else "bybit_perpetual_main"
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def _wss_url(endpoint: Dict[str, str], connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "bybit_perpetual_main"
    return endpoint.get(variant)


def wss_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_LINEAR_PUBLIC_URLS, connector_variant_label)


def wss_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_LINEAR_PRIVATE_URLS, connector_variant_label)


def wss_non_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_NON_LINEAR_PUBLIC_URLS, connector_variant_label)


def wss_non_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_NON_LINEAR_PRIVATE_URLS, connector_variant_label)


def get_next_funding_timestamp(current_timestamp: float) -> float:
    # On ByBit Perpetuals, funding occurs every 8 hours at 00:00UTC, 08:00UTC and 16:00UTC.
    # Reference: https://help.bybit.com/hc/en-us/articles/360039261134-Funding-fee-calculation
    int_ts = int(current_timestamp)
    eight_hours = 8 * 60 * 60
    mod = int_ts % eight_hours
    return float(int_ts - mod + eight_hours)


KEYS = {
    "bybit_perpetual_api_key":
        ConfigVar(key="bybit_perpetual_api_key",
                  prompt="Enter your Bybit Perpetual API key >>> ",
                  required_if=using_exchange("bybit_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "bybit_perpetual_secret_key":
        ConfigVar(key="bybit_perpetual_secret_key",
                  prompt="Enter your Bybit Perpetual secret key >>> ",
                  required_if=using_exchange("bybit_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["bybit_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"bybit_perpetual_testnet": "bybit_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bybit_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bybit_perpetual_testnet": [-0.025, 0.075]}
OTHER_DOMAINS_KEYS = {
    "bybit_perpetual_testnet": {
        "bybit_perpetual_testnet_api_key":
            ConfigVar(key="bybit_perpetual_testnet_api_key",
                      prompt="Enter your Bybit Perpetual Testnet API key >>> ",
                      required_if=using_exchange("bybit_perpetual_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "bybit_perpetual_testnet_secret_key":
            ConfigVar(key="bybit_perpetual_testnet_secret_key",
                      prompt="Enter your Bybit Perpetual Testnet secret key >>> ",
                      required_if=using_exchange("bybit_perpetual_testnet"),
                      is_secure=True,
                      is_connect_key=True),
    }
}
