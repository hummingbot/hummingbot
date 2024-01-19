from typing import Any, Callable, Dict, List, Optional

from hummingbot.connector.derivative.okx_perpetual import okx_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
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


async def get_current_server_time(throttler: Optional[AsyncThrottler] = None,
                                  domain: str = CONSTANTS.DEFAULT_DOMAIN) -> float:
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
    server_time = float(response["data"]["ts"])

    return server_time


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
        endpoint: str,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
):
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def get_pair_specific_limit_id(base_limit_id: str, trading_pair: str) -> str:
    limit_id = f"{base_limit_id}-{trading_pair}"
    return limit_id


def get_rest_api_limit_id_for_endpoint(endpoint: str, trading_pair: Optional[str] = None) -> str:
    limit_id = endpoint
    if trading_pair is not None:
        limit_id = get_pair_specific_limit_id(limit_id, trading_pair)
    return limit_id


# TODO: Check that connector_variant_label is called with DEFAULT_DOMAIN
def _wss_url(endpoint: Dict[str, str], connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else CONSTANTS.DEFAULT_DOMAIN
    return endpoint.get(variant)


def wss_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PUBLIC_URLS, connector_variant_label)


def wss_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PRIVATE_URLS, connector_variant_label)


def build_rate_limits(trading_pairs: Optional[List[str]] = None) -> List[RateLimit]:
    trading_pairs = trading_pairs or []
    rate_limits = []

    rate_limits.extend(_build_websocket_rate_limits())
    rate_limits.extend(_build_public_rate_limits())
    rate_limits.extend(_build_private_rate_limits(trading_pairs))

    return rate_limits


def _build_websocket_rate_limits() -> List[RateLimit]:
    # TODO: Check with dman how to handle global nested rate limits
    rate_limits = [
        # For connections
        RateLimit(limit_id=CONSTANTS.WSS_PUBLIC_URLS, limit=3, time_interval=1),
        RateLimit(limit_id=CONSTANTS.WSS_PRIVATE_URLS, limit=3, time_interval=1),
        # For subscriptions/unsubscriptions/logins
        RateLimit(limit_id=CONSTANTS.WSS_PUBLIC_URLS, limit=480, time_interval=60),
        RateLimit(limit_id=CONSTANTS.WSS_PRIVATE_URLS, limit=480, time_interval=60),
    ]
    # TODO: Include ping-pong feature, merge with rate limits?
    # If there’s a network problem, the system will automatically disable the connection.
    # The connection will break automatically if the subscription is not established or data has not been pushed for more than 30 seconds.
    # To keep the connection stable:
    # 1. Set a timer of N seconds whenever a response message is received, where N is less than 30.
    # 2. If the timer is triggered, which means that no new message is received within N seconds, send the String 'ping'.
    # 3. Expect a 'pong' as a response. If the response message is not received within N seconds, please raise an error or reconnect.
    return rate_limits


def _build_public_rate_limits():
    public_rate_limits = [
        RateLimit(
            # TODO: Define whether to use tickers here
            limit_id=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT,
            limit=20,
            time_interval=2,
            # TODO: Define latest symbol information linked limits
            # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        # TODO: Check what is QUERY_SYMBOL_ENDPOINT for, symbol seems deprecated
        # RateLimit(
        #     limit_id=CONSTANTS.QUERY_SYMBOL_ENDPOINT,
        #     limit=1,
        #     time_interval=1,
        #     linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        # ),
        RateLimit(
            limit_id=CONSTANTS.ORDER_BOOK_ENDPOINT,
            limit=40,
            time_interval=2,
            # TODO: Define order book linked limits
            # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
            limit=10,
            time_interval=2,
            # TODO: Define server time linked limits
            # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
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
        # TODO: Determine whether to use linear or non-linear rate limits
        # TODO: Determine whether to use private_bucket_N_limit_id
        trading_pair_rate_limits = [
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.SET_LEVERAGE_PATH_URL,
                    trading_pair=trading_pair
                ),
                limit=20,
                time_interval=2,
                # TODO: Define set leverage linked limits
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID)],
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.GET_FUNDING_RATE,
                    trading_pair=trading_pair,
                ),
                limit=20,
                time_interval=2,
                # TODO: Define get predicted funding rate linked limits
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.GET_POSITIONS_PATH_URL,
                    trading_pair=trading_pair
                ),
                limit=10,
                time_interval=2,
                # TODO: Define get positions linked limits
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL,
                    trading_pair=trading_pair
                ),
                limit=60,
                time_interval=2,
                # TODO: Define place active order linked limits
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID)],
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL,
                    trading_pair=trading_pair
                ),
                limit=60,
                time_interval=2,
                # TODO: Define cancel active order linked limits
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.POST_LIMIT_ID)],
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL,
                    trading_pair=trading_pair
                ),
                limit=60,
                time_interval=2,
                # TODO: Define query active order linked limits
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(
                    base_limit_id=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
                    trading_pair=trading_pair
                ),
                limit=120,
                time_interval=60,
                # TODO: Define user trade records
                # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
            ),
        ]
        rate_limits.extend(trading_pair_rate_limits)
    return rate_limits


def _build_private_general_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(
            limit_id=CONSTANTS.GET_WALLET_BALANCE_PATH_URL,
            limit=10,
            time_interval=2,
            # TODO: Define balance linked limits
            # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
        RateLimit(
            limit_id=CONSTANTS.SET_POSITION_MODE_URL,
            limit=5,
            time_interval=2,
            # TODO: Define set position mode linked limits
            # linked_limits=[LinkedLimitWeightPair(CONSTANTS.GET_LIMIT_ID)],
        ),
    ]
    return rate_limits
