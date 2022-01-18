import hummingbot.connector.exchange.kraken.kraken_constants as CONSTANTS

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.connector.exchange.kraken.kraken_constants import KrakenAPITier
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.16, 0.26]


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    return tuple(convert_from_exchange_trading_pair(trading_pair).split("-"))


def convert_from_exchange_symbol(symbol: str) -> str:
    # Assuming if starts with Z or X and has 4 letters then Z/X is removable
    if (symbol[0] == "X" or symbol[0] == "Z") and len(symbol) == 4:
        symbol = symbol[1:]
    return CONSTANTS.KRAKEN_TO_HB_MAP.get(symbol, symbol)


def convert_to_exchange_symbol(symbol: str) -> str:
    inverted_kraken_to_hb_map = {v: k for k, v in CONSTANTS.KRAKEN_TO_HB_MAP.items()}
    return inverted_kraken_to_hb_map.get(symbol, symbol)


def split_to_base_quote(exchange_trading_pair: str) -> Tuple[Optional[str], Optional[str]]:
    base, quote = exchange_trading_pair.split("-")
    return base, quote


def convert_from_exchange_trading_pair(exchange_trading_pair: str, available_trading_pairs: Optional[Tuple] = None) -> Optional[str]:
    base, quote = "", ""
    if "-" in exchange_trading_pair:
        base, quote = split_to_base_quote(exchange_trading_pair)
    elif "/" in exchange_trading_pair:
        base, quote = exchange_trading_pair.split("/")
    elif len(available_trading_pairs) > 0:
        # If trading pair has no spaces (i.e. ETHUSDT). Then it will have to match with the existing pairs
        # Option 1: Using traditional naming convention
        connector_trading_pair = {''.join(convert_from_exchange_trading_pair(tp).split('-')): tp for tp in available_trading_pairs}.get(
            exchange_trading_pair)
        if not connector_trading_pair:
            # Option 2: Using kraken naming convention ( XXBT for Bitcoin, XXDG for Doge, ZUSD for USD, etc)
            connector_trading_pair = {''.join(tp.split('-')): tp for tp in available_trading_pairs}.get(
                exchange_trading_pair)
            if not connector_trading_pair:
                # Option 3: Kraken naming convention but without the initial X and Z
                connector_trading_pair = {''.join(convert_to_exchange_symbol(convert_from_exchange_symbol(s))
                                                  for s in tp.split('-')): tp
                                          for tp in available_trading_pairs}.get(exchange_trading_pair)
        return connector_trading_pair

    if not base or not quote:
        return None
    base = convert_from_exchange_symbol(base)
    quote = convert_from_exchange_symbol(quote)
    return f"{base}-{quote}"


def convert_to_exchange_trading_pair(hb_trading_pair: str, delimiter: str = "") -> str:
    """
    Note: The result of this method can safely be used to submit/make queries.
    Result shouldn't be used to parse responses as Kraken add special formating to most pairs.
    """
    if "-" in hb_trading_pair:
        base, quote = hb_trading_pair.split("-")
    elif "/" in hb_trading_pair:
        base, quote = hb_trading_pair.split("/")
    else:
        return hb_trading_pair
    base = convert_to_exchange_symbol(base)
    quote = convert_to_exchange_symbol(quote)

    exchange_trading_pair = f"{base}{delimiter}{quote}"
    return exchange_trading_pair


def is_dark_pool(trading_pair_details: Dict[str, Any]):
    '''
    Want to filter out dark pool trading pairs from the list of trading pairs
    For more info, please check
    https://support.kraken.com/hc/en-us/articles/360001391906-Introducing-the-Kraken-Dark-Pool
    '''
    if trading_pair_details.get('altname'):
        return trading_pair_details.get('altname').endswith('.d')
    return False


def _build_private_rate_limits(tier: KrakenAPITier = KrakenAPITier.STARTER) -> List[RateLimit]:
    private_rate_limits = []

    PRIVATE_ENDPOINT_LIMIT, MATCHING_ENGINE_LIMIT = CONSTANTS.KRAKEN_TIER_LIMITS[tier]

    # Private REST endpoints
    private_rate_limits.extend([
        # Private API Pool
        RateLimit(
            limit_id=CONSTANTS.PRIVATE_ENDPOINT_LIMIT_ID,
            limit=PRIVATE_ENDPOINT_LIMIT,
            time_interval=CONSTANTS.PRIVATE_ENDPOINT_LIMIT_INTERVAL,
        ),
        # Private endpoints
        RateLimit(
            limit_id=CONSTANTS.GET_TOKEN_PATH_URL,
            limit=PRIVATE_ENDPOINT_LIMIT,
            time_interval=CONSTANTS.PRIVATE_ENDPOINT_LIMIT_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.PRIVATE_ENDPOINT_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.BALANCE_PATH_URL,
            limit=PRIVATE_ENDPOINT_LIMIT,
            time_interval=CONSTANTS.PRIVATE_ENDPOINT_LIMIT_INTERVAL,
            weight=2,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.PRIVATE_ENDPOINT_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.OPEN_ORDERS_PATH_URL,
            limit=PRIVATE_ENDPOINT_LIMIT,
            time_interval=CONSTANTS.PRIVATE_ENDPOINT_LIMIT_INTERVAL,
            weight=2,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.PRIVATE_ENDPOINT_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.QUERY_ORDERS_PATH_URL,
            limit=PRIVATE_ENDPOINT_LIMIT,
            time_interval=CONSTANTS.PRIVATE_ENDPOINT_LIMIT_INTERVAL,
            weight=2,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.PRIVATE_ENDPOINT_LIMIT_ID)],
        ),
    ])

    # Matching Engine Limits
    private_rate_limits.extend([
        RateLimit(
            limit_id=CONSTANTS.ADD_ORDER_PATH_URL,
            limit=MATCHING_ENGINE_LIMIT,
            time_interval=CONSTANTS.MATCHING_ENGINE_LIMIT_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.MATCHING_ENGINE_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.CANCEL_ORDER_PATH_URL,
            limit=MATCHING_ENGINE_LIMIT,
            time_interval=CONSTANTS.MATCHING_ENGINE_LIMIT_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(CONSTANTS.MATCHING_ENGINE_LIMIT_ID)],
        ),
    ])

    return private_rate_limits


def build_rate_limits_by_tier(tier: KrakenAPITier = KrakenAPITier.STARTER) -> List[RateLimit]:
    rate_limits = []

    rate_limits.extend(CONSTANTS.PUBLIC_API_LIMITS)
    rate_limits.extend(_build_private_rate_limits(tier=tier))

    return rate_limits


def _api_tier_validator(value: str) -> Optional[str]:
    """
    Determines if input value is a valid API tier
    """
    try:
        KrakenAPITier(value.upper())
    except ValueError:
        return "No such Kraken API Tier."


KEYS = {
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
    "kraken_api_tier":
        ConfigVar(key="kraken_api_tier",
                  prompt="Enter your Kraken API Tier (Starter/Intermediate/Pro) >>> ",
                  required_if=using_exchange("kraken"),
                  default="Starter",
                  is_secure=False,
                  is_connect_key=True,
                  validator=lambda v: _api_tier_validator(v),
                  ),
}


def build_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    return api_factory
