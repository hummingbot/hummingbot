from typing import Any, Dict, Optional

import hummingbot.connector.derivative.bitmex_perpetual.constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitmexPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json" if request.method == RESTMethod.POST else "application/x-www-form-urlencoded"
        )
        return request


def rest_url(path_url: str, domain: str = "bitmex_perpetual"):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "bitmex_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(endpoint: str, domain: str = "bitmex_perpetual"):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "bitmex_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url + endpoint


def build_api_factory(
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:

    throttler = create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            BitmexPerpetualRESTPreProcessor(),
        ])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def api_request(path: str,
                      api_factory: Optional[WebAssistantsFactory] = None,
                      throttler: Optional[AsyncThrottler] = None,
                      domain: str = CONSTANTS.DOMAIN,
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
        url = rest_url(path, domain)

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
