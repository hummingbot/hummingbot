from typing import Any, Callable, Dict, List, Optional

from hummingbot.connector.derivative.kucoin_perpetual import kucoin_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
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
    throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
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
    server_time = response["data"]

    return server_time * 1e-3


def endpoint_from_message(message: Dict[str, Any]) -> Optional[str]:
    endpoint = None
    if "request" in message:
        message = message["request"]
    elif "type" in message:
        endpoint = message["type"]
    if isinstance(message, dict):
        if "subject" in message.keys():
            endpoint = message["subject"]
        elif endpoint is None and "topic" in message.keys():
            endpoint = message["topic"]
    return endpoint


def payload_from_message(message: Dict[str, Any]) -> Dict[str, Any]:
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


def get_rest_api_limit_id_for_endpoint(endpoint: Dict[str, str]) -> str:
    return endpoint


def _wss_url(endpoint: Dict[str, str], connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else CONSTANTS.DEFAULT_DOMAIN
    return endpoint.get(variant)


def wss_public_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PUBLIC_URLS, connector_variant_label)


def wss_private_url(connector_variant_label: Optional[str]) -> str:
    return _wss_url(CONSTANTS.WSS_PRIVATE_URLS, connector_variant_label)


def next_message_id() -> str:
    return str(get_tracking_nonce())


async def api_request(path: str,
                      api_factory: Optional[WebAssistantsFactory] = None,
                      throttler: Optional[AsyncThrottler] = None,
                      domain: str = CONSTANTS.DEFAULT_DOMAIN,
                      params: Optional[Dict[str, Any]] = None,
                      data: Optional[Dict[str, Any]] = None,
                      method: RESTMethod = RESTMethod.GET,
                      is_auth_required: bool = False,
                      return_err: bool = False,
                      api_version: str = "v1",
                      limit_id: Optional[str] = None,
                      timeout: Optional[float] = None):

    throttler = throttler or create_throttler()

    api_factory = api_factory or build_api_factory()
    rest_assistant = await api_factory.get_rest_assistant()

    async with throttler.execute_task(limit_id=limit_id if limit_id else path):
        url = get_rest_url_for_endpoint(endpoint=path, domain=domain)

        request = RESTRequest(
            method=method,
            url=url,
            params=params,
            data=data,
            is_auth_required=is_auth_required,
            throttler_limit_id=limit_id if limit_id else path
        )
        response = await rest_assistant.call(request=request, timeout=timeout)

        if response.status != 200:
            if return_err:
                error_response = await response.json()
                return error_response
            else:
                error_response = await response.text()
                raise IOError(f"Error executing request {method.name} {path}. "
                              f"HTTP status is {response.status}. "
                              f"Error: {error_response}")
        return await response.json()
