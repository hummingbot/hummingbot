from typing import Dict, List, Optional

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
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
    return f"{CONSTANTS.HBOT_BROKER_ID}-{side}-{trading_pair}-{get_tracking_nonce()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def is_linear_perpetual(trading_pair: str) -> bool:
    """
    Returns True if trading_pair is in USDT(Linear) Perpetual
    """
    _, quote_asset = split_hb_trading_pair(trading_pair)
    return quote_asset == "USDT"


def get_rest_api_market_for_endpoint(trading_pair: Optional[str] = None) -> str:
    if trading_pair and is_linear_perpetual(trading_pair):
        market = CONSTANTS.LINEAR_MARKET
    else:
        market = CONSTANTS.NON_LINEAR_MARKET
    return market


def rest_api_path_for_endpoint(endpoint: Dict[str, str],
                               trading_pair: Optional[str] = None) -> str:
    market = get_rest_api_market_for_endpoint(trading_pair)
    return endpoint[market]


def rest_api_url_for_endpoint(endpoint: str, domain: Optional[str] = None) -> str:
    variant = domain if domain else "bybit_perpetual_main"
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def get_pair_specific_limit_id(base_limit_id: str, trading_pair: str) -> str:
    limit_id = f"{base_limit_id}-{trading_pair}"
    return limit_id


def get_rest_api_limit_id_for_endpoint(endpoint: Dict[str, str],
                                       trading_pair: Optional[str] = None) -> str:
    market = get_rest_api_market_for_endpoint(trading_pair)
    limit_id = endpoint[market]
    if trading_pair is not None:
        limit_id = get_pair_specific_limit_id(limit_id, trading_pair)
    return limit_id


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


def build_rate_limits(trading_pairs: Optional[List[str]] = None) -> List[RateLimit]:
    trading_pairs = trading_pairs or []
    rate_limits = []

    rate_limits.extend(_build_global_rate_limits())
    rate_limits.extend(_build_public_rate_limits())
    rate_limits.extend(_build_private_rate_limits(trading_pairs))

    return rate_limits


def _build_private_general_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(  # same for linear and non-linear
            limit_id=CONSTANTS.GET_WALLET_BALANCE_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID)],
        ),
    ]
    return rate_limits


def _build_global_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(limit_id=CONSTANTS.GET_LIMIT_ID, limit=CONSTANTS.GET_RATE, time_interval=1),
        RateLimit(limit_id=CONSTANTS.POST_LIMIT_ID, limit=CONSTANTS.POST_RATE, time_interval=1),
    ]
    return rate_limits


def _build_public_rate_limits():
    public_rate_limits = [
        RateLimit(  # same for linear and non-linear
            limit_id=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT[CONSTANTS.NON_LINEAR_MARKET],
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(  # same for linear and non-linear
            limit_id=CONSTANTS.QUERY_SYMBOL_ENDPOINT[CONSTANTS.NON_LINEAR_MARKET],
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(  # same for linear and non-linear
            limit_id=CONSTANTS.ORDER_BOOK_ENDPOINT[CONSTANTS.NON_LINEAR_MARKET],
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(  # same for linear and non-linear
            limit_id=CONSTANTS.SERVER_TIME_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
            limit=CONSTANTS.GET_RATE,
            time_interval=1,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        )
    ]
    return public_rate_limits


def _build_private_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    rate_limits.extend(_build_private_pair_specific_rate_limits(trading_pairs))
    rate_limits.extend(_build_private_general_rate_limits())

    return rate_limits


def _build_private_pair_specific_rate_limits(trading_pairs: List[str]) -> List[RateLimit]:
    rate_limits = []

    for trading_pair in trading_pairs:
        market = get_rest_api_market_for_endpoint(trading_pair)
        if market == CONSTANTS.NON_LINEAR_MARKET:
            rate_limits.extend(_build_private_pair_specific_non_linear_rate_limits(trading_pair))
        else:
            rate_limits.extend(_build_private_pair_specific_linear_rate_limits(trading_pair))

    return rate_limits


def _build_private_pair_specific_non_linear_rate_limits(trading_pair: str) -> List[RateLimit]:
    pair_specific_non_linear_private_bucket_100_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_600_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_75_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_120_b_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_non_linear_private_bucket_120_c_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_120_C_LIMIT_ID, trading_pair=trading_pair
    )

    rate_limits = [
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_100_limit_id, limit=100, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_600_limit_id, limit=600, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_75_limit_id, limit=75, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_120_b_limit_id, limit=120, time_interval=60),
        RateLimit(limit_id=pair_specific_non_linear_private_bucket_120_c_limit_id, limit=120, time_interval=60),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.SET_LEVERAGE_PATH_URL[CONSTANTS.NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=75,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_non_linear_private_bucket_75_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
                trading_pair=trading_pair,
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_non_linear_private_bucket_120_c_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_POSITIONS_PATH_URL[CONSTANTS.NON_LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_non_linear_private_bucket_120_b_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
                trading_pair=trading_pair,
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_non_linear_private_bucket_100_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
                trading_pair=trading_pair,
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_non_linear_private_bucket_100_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
                trading_pair=trading_pair,
            ),
            limit=600,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_non_linear_private_bucket_600_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.USER_TRADE_RECORDS_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
                trading_pair=trading_pair,
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
    ]

    return rate_limits


def _build_private_pair_specific_linear_rate_limits(trading_pair: str) -> List[RateLimit]:
    pair_specific_linear_private_bucket_100_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_linear_private_bucket_600_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.LINEAR_PRIVATE_BUCKET_600_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_linear_private_bucket_75_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.LINEAR_PRIVATE_BUCKET_75_LIMIT_ID, trading_pair=trading_pair
    )
    pair_specific_linear_private_bucket_120_a_limit_id = get_pair_specific_limit_id(
        base_limit_id=CONSTANTS.LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, trading_pair=trading_pair
    )

    rate_limits = [
        RateLimit(limit_id=pair_specific_linear_private_bucket_100_limit_id, limit=100, time_interval=60),
        RateLimit(limit_id=pair_specific_linear_private_bucket_600_limit_id, limit=600, time_interval=60),
        RateLimit(limit_id=pair_specific_linear_private_bucket_75_limit_id, limit=75, time_interval=60),
        RateLimit(limit_id=pair_specific_linear_private_bucket_120_a_limit_id, limit=120, time_interval=60),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.SET_LEVERAGE_PATH_URL[CONSTANTS.LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=75,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_75_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL[CONSTANTS.LINEAR_MARKET],
                trading_pair=trading_pair,
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_120_a_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.GET_POSITIONS_PATH_URL[CONSTANTS.LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_120_a_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL[CONSTANTS.LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_100_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL[CONSTANTS.LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=100,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_100_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL[CONSTANTS.LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=600,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_600_limit_id)],
        ),
        RateLimit(
            limit_id=get_pair_specific_limit_id(
                base_limit_id=CONSTANTS.USER_TRADE_RECORDS_PATH_URL[CONSTANTS.LINEAR_MARKET], trading_pair=trading_pair
            ),
            limit=120,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID),
                           LinkedLimitWeightPair(pair_specific_linear_private_bucket_120_a_limit_id)],
        ),
    ]

    return rate_limits
