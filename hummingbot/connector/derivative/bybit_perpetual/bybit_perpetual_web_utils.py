from typing import Any, Callable, Dict, List, Optional

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils import is_linear_perpetual
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HeadersContentRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        if request.method == RESTMethod.POST:
            request.headers["Content-Type"] = "application/json"
        return request


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Bybit domain to connect to ("mainnet" or "testnet"). The default value is "mainnet"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URLS[domain] + path_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
            HeadersContentRESTPreProcessor()
        ])
    return api_factory


async def api_request(path: str,
                      api_factory: Optional[WebAssistantsFactory] = None,
                      throttler: Optional[AsyncThrottler] = None,
                      time_synchronizer: Optional[TimeSynchronizer] = None,
                      domain: str = CONSTANTS.DEFAULT_DOMAIN,
                      params: Optional[Dict[str, Any]] = None,
                      data: Optional[Dict[str, Any]] = None,
                      method: RESTMethod = RESTMethod.GET,
                      is_auth_required: bool = False,
                      return_err: bool = False,
                      limit_id: Optional[str] = None,
                      timeout: Optional[float] = None,
                      headers: Dict[str, Any] = {}):
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()

    # If api_factory is not provided a default one is created
    # The default instance has no authentication capabilities and all authenticated requests will fail
    api_factory = api_factory or build_api_factory(
        throttler=throttler,
        time_synchronizer=time_synchronizer,
        domain=domain,
    )
    rest_assistant = await api_factory.get_rest_assistant()

    url = rest_url(path, domain=domain)

    request = RESTRequest(
        method=method,
        url=url,
        params=params,
        data=data,
        headers=headers,
        is_auth_required=is_auth_required,
        throttler_limit_id=limit_id if limit_id else path
    )

    async with throttler.execute_task(limit_id=limit_id if limit_id else path):
        response = await rest_assistant.call(request=request, timeout=timeout)
        if response.status != 200:
            if return_err:
                error_response = await response.json()
                return error_response
            else:
                error_response = await response.text()
                if error_response is not None and "ret_code" in error_response and "ret_msg" in error_response:
                    raise IOError(f"The request to Bybit failed. Error: {error_response}. Request: {request}")
                else:
                    raise IOError(f"Error executing request {method.name} {path}. "
                                  f"HTTP status is {response.status}. "
                                  f"Error: {error_response}")

        return await response.json()


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    response = await api_request(
        path=CONSTANTS.SERVER_TIME_PATH_URL,
        api_factory=api_factory,
        throttler=throttler,
        domain=domain,
        method=RESTMethod.GET
    )
    # Use nanoseconds for higher resolution
    server_time = float(response["result"]["timeNano"]) * 1e-6
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
    endpoint: Dict[str, str],
    trading_pair: Optional[str] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN
):
    market = _get_rest_api_market_for_endpoint(trading_pair)
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint[market]


def _get_rest_api_market_for_endpoint(trading_pair: Optional[str] = None) -> str:
    # The default selection should be linear because general requests such as setting position mode
    # exists only for linear market and is without a trading pair
    if trading_pair is None or is_linear_perpetual(trading_pair):
        market = CONSTANTS.LINEAR_MARKET
    else:
        market = CONSTANTS.NON_LINEAR_MARKET
    return market


def _wss_url(endpoint: Dict[str, str], connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else CONSTANTS.DEFAULT_DOMAIN
    return endpoint.get(variant)


def wss_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PUBLIC_URL_LINEAR, connector_variant_label)


def wss_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PRIVATE_URL_LINEAR, connector_variant_label)


def wss_non_linear_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PUBLIC_URL_NON_LINEAR, connector_variant_label)


def wss_non_linear_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PRIVATE_URL_NON_LINEAR, connector_variant_label)
