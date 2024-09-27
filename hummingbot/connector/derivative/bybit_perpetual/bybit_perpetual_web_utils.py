from typing import Any, Callable, Dict, List, Optional

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils import is_linear_perpetual
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HeadersContentRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        request.headers["Content-Type"] = "application/json"
        return request


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
            HeadersContentRESTPreProcessor(),
        ],
    )
    return api_factory


def create_throttler(trading_pairs: List[str] = None) -> AsyncThrottler:
    throttler = AsyncThrottler(build_rate_limits(trading_pairs))
    return throttler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    endpoint = CONSTANTS.SERVER_TIME_PATH_URL
    url = get_rest_url_for_endpoint(endpoint=endpoint, domain=domain)
    limit_id = get_rest_api_limit_id_for_endpoint(endpoint)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=limit_id,
        method=RESTMethod.GET,
    )
    time = response.get("result")
    if time is not None:
        server_time = float(time["timeNano"])
        return server_time
    else:
        raise ValueError("Failed to get server time")


def endpoint_from_message(message: Dict[str, Any]) -> Optional[str]:
    endpoint = None
    if "request" in message:
        message = message["request"]
    if isinstance(message, dict):
        if "op" in message.keys():
            endpoint = message["op"]
        elif endpoint is None and "topic" in message.keys():
            endpoint = message["topic"]
    return endpoint


def payload_from_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = message
    if "data" in message:
        payload = message["data"]
    return payload


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def get_rest_url_for_endpoint(
    endpoint: Dict[str, str], trading_pair: Optional[str] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
):
    market = _get_rest_api_market_for_endpoint(trading_pair)
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint[market]


def get_pair_specific_limit_id(base_limit_id: str, trading_pair: str) -> str:
    limit_id = f"{base_limit_id}-{trading_pair}"
    return limit_id


def get_rest_api_limit_id_for_endpoint(endpoint: Dict[str, str], trading_pair: Optional[str] = None) -> str:
    market = _get_rest_api_market_for_endpoint(trading_pair)
    limit_id = endpoint[market]
    if trading_pair is not None:
        limit_id = get_pair_specific_limit_id(limit_id, trading_pair)
    return limit_id


def _wss_url(endpoint: Dict[str, str], connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else CONSTANTS.DEFAULT_DOMAIN
    return endpoint.get(variant)


def wss_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_LINEAR_PUBLIC_URLS, connector_variant_label)


def wss_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_LINEAR_PRIVATE_URLS, connector_variant_label)


def wss_non_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_NON_LINEAR_PUBLIC_URLS, connector_variant_label)


def wss_non_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_NON_LINEAR_PRIVATE_URLS, connector_variant_label)


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
        RateLimit(  # same for linear and non-linear
            limit_id=CONSTANTS.SET_POSITION_MODE_URL[CONSTANTS.LINEAR_MARKET],
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
        market = _get_rest_api_market_for_endpoint(trading_pair)
        if market == CONSTANTS.NON_LINEAR_MARKET:
            rate_limits.extend(_build_private_pair_specific_non_linear_rate_limits(trading_pair))
        else:
            rate_limits.extend(_build_private_pair_specific_linear_rate_limits(trading_pair))

    return rate_limits


def _get_rest_api_market_for_endpoint(trading_pair: Optional[str] = None) -> str:
    # The default selection should be linear because general requests such as setting position mode
    # exists only for linear market and is without a trading pair
    if trading_pair is None or is_linear_perpetual(trading_pair):
        market = CONSTANTS.LINEAR_MARKET
    else:
        market = CONSTANTS.NON_LINEAR_MARKET
    return market


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
