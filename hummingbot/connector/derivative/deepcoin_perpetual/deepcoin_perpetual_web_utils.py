from typing import Any, Callable, Dict, List, Optional

from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_constants as CONSTANTS
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
    url = get_rest_url_for_endpoint(endpoint=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain)
    limit_id = get_rest_api_limit_id_for_endpoint(CONSTANTS.SERVER_TIME_PATH_URL)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=limit_id,
        method=RESTMethod.GET,
    )
    time_data = response.get("data")
    if time_data is not None:
        server_time = float(time_data["timestamp"])
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
    endpoint: str, trading_pair: Optional[str] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
):
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def get_ws_url_for_endpoint(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.WSS_PUBLIC_URLS.get(variant) + endpoint


def get_ws_private_url_for_endpoint(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.WSS_USER_STREAM_URLS.get(variant) + endpoint


def get_rest_api_limit_id_for_endpoint(endpoint: str) -> str:
    return f"REST_{endpoint}"


def build_rate_limits(trading_pairs: List[str] = None) -> List[RateLimit]:
    """
    Creates rate limits for the connector
    """
    rate_limits = [
        # General rate limits
        RateLimit(limit_id="REST_GET", limit=1200, time_interval=60),
        RateLimit(limit_id="REST_POST", limit=600, time_interval=60),
        RateLimit(limit_id="REST_DELETE", limit=600, time_interval=60),
        # Specific endpoint limits
        RateLimit(limit_id="REST_api/v1/market/symbols", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/market/depth", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/market/ticker", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/account/balance", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/account/positions", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/trade/order", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/trade/leverage", limit=100, time_interval=60),
        RateLimit(limit_id="REST_api/v1/trade/positionMode", limit=100, time_interval=60),
    ]
    return rate_limits


def public_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Get public REST URL for endpoint
    """
    return get_rest_url_for_endpoint(endpoint, domain=domain)


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Get WebSocket URL for domain
    """
    return CONSTANTS.WSS_PUBLIC_URLS.get(domain, CONSTANTS.WSS_PUBLIC_URLS[CONSTANTS.DEFAULT_DOMAIN])
