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
        request.headers.update({"Content-Type": "application/json"})
        return request


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler, domain=CONSTANTS.DEFAULT_DOMAIN))
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
    """
    Transaction Timeouts (https://www.okx.com/docs-v5/en/?shell#overview-general-info)
    Orders may not be processed in time due to network delay or busy OKX servers.

    You can configure the expiry time of the request using expTime if you want the order request to be
    discarded after a specific time.

    If expTime is specified in the requests for Place (multiple) orders or Amend (multiple) orders,
    the request will not be processed if the current system time of the server is after the expTime.

    You should synchronize with our system time. Use Get system time to obtain the current system time.
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    endpoint = CONSTANTS.REST_SERVER_TIME
    url = get_rest_url_for_endpoint(endpoint=endpoint, domain=domain)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=endpoint,
        method=RESTMethod.GET,
    )
    server_time = int(response["data"][0]["ts"])

    return server_time


def endpoint_from_message(message: Dict[str, Any]) -> Optional[str]:
    endpoint = None
    if isinstance(message, dict):
        event = message.get("event")
        op = message.get("op")
        if event is not None:
            endpoint = event
        elif op is not None:
            endpoint = op
        else:
            endpoint = message["arg"].get("channel")
    return endpoint


def payload_from_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    return message.get("data", [])


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def get_rest_url_for_endpoint(
        endpoint: str,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
):
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def get_pair_specific_limit_id(endpoint: str, trading_pair: str) -> str:
    return f"{endpoint}-{trading_pair}"


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
    domain = CONSTANTS.DEFAULT_DOMAIN
    rate_limits.extend(_build_websocket_rate_limits(domain))
    rate_limits.extend(_build_public_rate_limits())
    rate_limits.extend(_build_private_rate_limits(trading_pairs))

    return rate_limits


def _build_websocket_rate_limits(domain: str) -> List[RateLimit]:
    rate_limits = [
        # For connections
        RateLimit(limit_id=CONSTANTS.WSS_PUBLIC_URLS[domain], limit=3, time_interval=1),
        RateLimit(limit_id=CONSTANTS.WSS_PRIVATE_URLS[domain], limit=3, time_interval=1),
        # For subscriptions/unsubscriptions/logins
        RateLimit(limit_id=CONSTANTS.WSS_PUBLIC_URLS[domain], limit=480, time_interval=60),
        RateLimit(limit_id=CONSTANTS.WSS_PRIVATE_URLS[domain], limit=480, time_interval=60),
    ]
    return rate_limits


def _build_public_rate_limits():
    public_rate_limits = [
        RateLimit(limit_id=CONSTANTS.REST_LATEST_SYMBOL_INFORMATION, limit=20, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_ORDER_BOOK, limit=40, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_SERVER_TIME, limit=10, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_GET_INSTRUMENTS, limit=20, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_INDEX_TICKERS, limit=20, time_interval=2),

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
        trading_pair_rate_limits = [
            RateLimit(
                limit_id=get_pair_specific_limit_id(endpoint=CONSTANTS.REST_FUNDING_RATE_INFO,
                                                    trading_pair=trading_pair),
                limit=20,
                time_interval=2,
            ),
            RateLimit(
                limit_id=get_pair_specific_limit_id(endpoint=CONSTANTS.REST_MARK_PRICE,
                                                    trading_pair=trading_pair),
                limit=10,
                time_interval=2
            ),
        ]
        rate_limits.extend(trading_pair_rate_limits)
    return rate_limits


def _build_private_general_rate_limits() -> List[RateLimit]:
    rate_limits = [
        RateLimit(limit_id=CONSTANTS.REST_QUERY_ACTIVE_ORDER, limit=60, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_PLACE_ACTIVE_ORDER, limit=60, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_CANCEL_ACTIVE_ORDER, limit=60, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_SET_LEVERAGE, limit=20, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_USER_TRADE_RECORDS, limit=120, time_interval=60),
        RateLimit(limit_id=CONSTANTS.REST_GET_POSITIONS, limit=10, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_GET_WALLET_BALANCE, limit=10, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_SET_POSITION_MODE, limit=5, time_interval=2),
        RateLimit(limit_id=CONSTANTS.REST_BILLS_DETAILS, limit=5, time_interval=1)
    ]
    return rate_limits
