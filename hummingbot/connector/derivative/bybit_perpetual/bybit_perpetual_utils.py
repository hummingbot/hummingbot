from typing import Optional, Dict

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

# Bybit fees: https://help.bybit.com/hc/en-us/articles/360039261154
# Fees have to be expressed as percent value
DEFAULT_FEES = [0, 0.075]


# USE_ETHEREUM_WALLET not required because default value is false
# FEE_TYPE not required because default value is Percentage
# FEE_TOKEN not required because the fee is not flat

def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def rest_api_url_for_endpoint(endpoint: Dict[str, str],
                              domain: Optional[str] = None,
                              trading_pair: Optional[str] = None) -> str:
    variant = domain if domain else "bybit_perpetual_main"
    if trading_pair:
        _, quote_asset = trading_pair.split("-")
        market = "linear" if quote_asset == "USDT" else "non_linear"
    else:
        market = "non_linear"
    return CONSTANTS.REST_URLS.get(variant) + endpoint[market]


def wss_url(connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "bybit_perpetual_main"
    return CONSTANTS.WSS_URLS.get(variant)


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
                  prompt="Enter your Bybit API key >>> ",
                  required_if=using_exchange("bybit_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "bybit_perpetual_secret_key":
        ConfigVar(key="bybit_perpetual_secret_key",
                  prompt="Enter your Bybit secret key >>> ",
                  required_if=using_exchange("bybit_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["bybit_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"bybit_perpetual_testnet": "bybit_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bybit_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bybit_perpetual_testnet": [0, 0.075]}
OTHER_DOMAINS_KEYS = {
    "bybit_perpetual_testnet": {
        "bybit_perpetual_testnet_api_key":
            ConfigVar(key="bybit_perpetual_testnet_api_key",
                      prompt="Enter your Bybit API key >>> ",
                      required_if=using_exchange("bybit_perpetual_testnet"),
                      is_secure=True,
                      is_connect_key=True),
        "bybit_perpetual_testnet_secret_key":
            ConfigVar(key="bybit_testnet_secret_key",
                      prompt="Enter your Bybit secret key >>> ",
                      required_if=using_exchange("bybit_perpetual_testnet"),
                      is_secure=True,
                      is_connect_key=True),
    }
}
