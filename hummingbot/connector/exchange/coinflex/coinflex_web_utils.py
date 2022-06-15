import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlencode

import ujson

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest, RESTMethod, RESTResponse
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str = "",
                    domain: str = CONSTANTS.DEFAULT_DOMAIN,
                    only_hostname: bool = False,
                    domain_api_version: str = None,
                    endpoint_api_version: str = None) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param host: the CoinFLEX host to connect to
    :return: the full URL to the endpoint
    """
    local_domain_api_version = domain_api_version or CONSTANTS.PUBLIC_API_VERSION
    local_endpoint_api_version = endpoint_api_version or CONSTANTS.PUBLIC_API_VERSION
    subdomain_prefix = f"{local_domain_api_version}stg" if domain == "coinflex_test" else local_domain_api_version
    endpoint = "" if not len(path_url) else f"/{path_url}"
    if only_hostname:
        return CONSTANTS.REST_URL.format(subdomain_prefix)
    return "https://" + CONSTANTS.REST_URL.format(subdomain_prefix) + f"/{local_endpoint_api_version}{endpoint}"


def private_rest_url(path_url: str = "",
                     domain: str = CONSTANTS.DEFAULT_DOMAIN,
                     only_hostname: bool = False,
                     domain_api_version: str = None,
                     endpoint_api_version: str = None) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param host: the CoinFLEX host to connect to
    :return: the full URL to the endpoint
    """
    local_domain_api_version = domain_api_version or CONSTANTS.PRIVATE_API_VERSION
    local_endpoint_api_version = endpoint_api_version or CONSTANTS.PRIVATE_API_VERSION
    subdomain_prefix = f"{local_domain_api_version}stg" if domain == "coinflex_test" else local_domain_api_version
    endpoint = "" if not len(path_url) else f"/{path_url}"
    if only_hostname:
        return CONSTANTS.REST_URL.format(subdomain_prefix)
    return "https://" + CONSTANTS.REST_URL.format(subdomain_prefix) + f"/{local_endpoint_api_version}{endpoint}"


def private_rest_auth_path(path_url: str,
                           domain: str = CONSTANTS.DEFAULT_DOMAIN,
                           endpoint_api_version: str = None) -> str:
    """
    Creates an auth URL path for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param host: the CoinFLEX host to connect to
    :return: the auth URL path for the endpoint
    """
    local_endpoint_api_version = endpoint_api_version or CONSTANTS.PRIVATE_API_VERSION
    return f"/{local_endpoint_api_version}/{path_url}"


def websocket_url(domain: str = CONSTANTS.DEFAULT_DOMAIN,
                  domain_api_version: str = None,
                  endpoint_api_version: str = None) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param host: the CoinFLEX host to connect to
    :return: the full URL to the endpoint
    """
    local_domain_api_version = domain_api_version or CONSTANTS.PUBLIC_API_VERSION
    local_endpoint_api_version = endpoint_api_version or CONSTANTS.PUBLIC_API_VERSION
    subdomain_prefix = f"{local_domain_api_version}stg" if domain == "coinflex_test" else local_domain_api_version
    return CONSTANTS.WSS_URL.format(subdomain_prefix, local_endpoint_api_version)


def build_api_factory(throttler: AsyncThrottler, auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth, rest_pre_processors=[CoinflexRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


@dataclass
class CoinflexRESTRequest(EndpointRESTRequest):
    """
    CoinFLEX version of the `RESTRequest` class.
    """
    data: Optional[Mapping[str, str]] = None
    domain: str = CONSTANTS.DEFAULT_DOMAIN
    domain_api_version: str = None
    endpoint_api_version: str = None
    disable_retries: bool = False

    def __post_init__(self):
        super().__post_init__()
        if not self.throttler_limit_id:
            self.throttler_limit_id = self.endpoint

    @property
    def should_use_data(self) -> bool:
        return self.method in [RESTMethod.POST, RESTMethod.DELETE]

    def _ensure_data(self):
        if self.should_use_data:
            if self.data is not None:
                self.data = ujson.dumps(self.data)
        elif self.data is not None:
            raise ValueError(
                "The `data` field should be used only for POST/DELETE requests. Use `params` instead."
            )

    @property
    def base_url(self) -> str:
        if self.is_auth_required:
            return private_rest_url(domain=self.domain,
                                    domain_api_version=self.domain_api_version,
                                    endpoint_api_version=self.endpoint_api_version)
        return public_rest_url(domain=self.domain,
                               domain_api_version=self.domain_api_version,
                               endpoint_api_version=self.endpoint_api_version)

    @property
    def auth_path(self) -> str:
        if self.endpoint is None:
            raise ValueError("No endpoint specified. Cannot build auth url.")
        uri = private_rest_auth_path(self.endpoint, self.domain, endpoint_api_version=self.endpoint_api_version)
        return uri

    @property
    def auth_url(self) -> str:
        return private_rest_url(domain=self.domain, only_hostname=True)

    @property
    def auth_body(self) -> str:
        if self.should_use_data and self.data:
            return f"{self.data}"
        elif self.params:
            return urlencode(self.params)
        return ""


class CoinflexAPIError(IOError):
    """
    CoinFLEX API Errors
    """
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


class CoinflexRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: CoinflexRESTRequest) -> CoinflexRESTRequest:
        base_headers = {
            "Content-Type": "application/json",
            "User-Agent": CONSTANTS.USER_AGENT
        }
        request.headers = {**base_headers, **request.headers} if request.headers else base_headers
        return request


# REST Request utils


def retry_sleep_time(try_count: int) -> float:
    random.seed()
    randSleep = 1 + float(random.randint(1, 10) / 100)
    return float(2 + float(randSleep * (1 + (try_count ** try_count))))


async def _parse_or_truncate_response(response: RESTResponse):
    parsed_response, request_errors = None, False
    http_status = response.status
    try:
        parsed_response = await response.json()
    except Exception:
        request_errors = True
        try:
            parsed_response = await response.text()
            try:
                parsed_response = ujson.loads(parsed_response)
            except Exception:
                if len(parsed_response) < 1:
                    parsed_response = None
                elif len(parsed_response) > 100:
                    parsed_response = f"{parsed_response[:100]} ... (truncated)"
        except Exception:
            pass
    TempFailure = (parsed_response is None or
                   (response.status not in [200, 201] and
                    "errors" not in parsed_response and
                    "error" not in parsed_response))
    if TempFailure:
        parsed_response = response._aiohttp_response.reason if parsed_response is None else parsed_response
        request_errors = True
    return http_status, parsed_response, request_errors


async def rest_response_with_errors(rest_assistant, request):
    try:
        response = await asyncio.wait_for(rest_assistant.call(request), CONSTANTS.API_CALL_TIMEOUT)
        return await _parse_or_truncate_response(response)
    except asyncio.CancelledError:
        raise
    except Exception:
        return None, None, True


def _extract_error_from_response(response_data: Dict[str, Any]):
    if "errors" in response_data:
        raise CoinflexAPIError(response_data)
    if "error" in response_data:
        response_data['errors'] = response_data.get('error')
        raise CoinflexAPIError(response_data)
    if str(response_data.get("success")).lower() == "false":
        response_data['errors'] = response_data.get('message')
        raise CoinflexAPIError(response_data)
    resp_data = response_data.get("data", [])
    if len(resp_data) and str(resp_data[0].get("success")).lower() == "false":
        response_data['errors'] = resp_data[0].get('message')
        raise CoinflexAPIError(response_data)


async def api_call_with_retries(request: CoinflexRESTRequest,
                                rest_assistant: RESTAssistant,
                                throttler: AsyncThrottler,
                                logger: logging.Logger = None,
                                try_count: int = 0) -> Dict[str, Any]:

    async with throttler.execute_task(limit_id=request.throttler_limit_id):
        http_status, resp, request_errors = await rest_response_with_errors(rest_assistant, request)

    if isinstance(resp, dict):
        _extract_error_from_response(resp)

    if request_errors or resp is None:
        if try_count < CONSTANTS.API_MAX_RETRIES and not request.disable_retries:
            try_count += 1
            time_sleep = retry_sleep_time(try_count)

            suppress_msgs = ['Forbidden']

            err_msg = (f"Error fetching data from {request.url}. HTTP status is {http_status}. "
                       f"Retrying in {time_sleep:.0f}s. {resp or ''}")

            if (resp is not None and resp not in suppress_msgs) or try_count > 1:
                if logger:
                    logger.network(err_msg)
                else:
                    print(err_msg)
            elif logger:
                logger.debug(err_msg, exc_info=True)
            await asyncio.sleep(time_sleep)
            return await api_call_with_retries(request=request, rest_assistant=rest_assistant, throttler=throttler,
                                               logger=logger, try_count=try_count)
        else:
            raise CoinflexAPIError({"errors": resp, "status": http_status})
    return resp


async def api_request(path: str,
                      api_factory: Optional[WebAssistantsFactory] = None,
                      throttler: Optional[AsyncThrottler] = None,
                      domain: str = CONSTANTS.DEFAULT_DOMAIN,
                      params: Optional[Dict[str, Any]] = None,
                      data: Optional[Dict[str, Any]] = None,
                      method: RESTMethod = RESTMethod.GET,
                      is_auth_required: bool = False,
                      domain_api_version: str = None,
                      endpoint_api_version: str = None,
                      disable_retries: bool = False,
                      limit_id: Optional[str] = None,
                      logger: logging.Logger = None):
    """
    CoinFLEX generic api request wrapper function.
    """
    throttler = throttler or create_throttler()

    # If api_factory is not provided a default one is created
    # The default instance has no authentication capabilities and all authenticated requests will fail
    api_factory = api_factory or build_api_factory(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()

    request = CoinflexRESTRequest(
        method=method,
        endpoint=path,
        domain=domain,
        domain_api_version=domain_api_version,
        endpoint_api_version=endpoint_api_version,
        data=data,
        params=params,
        is_auth_required=is_auth_required,
        throttler_limit_id=limit_id if limit_id else path,
        disable_retries=disable_retries
    )

    return await api_call_with_retries(
        request=request,
        rest_assistant=rest_assistant,
        throttler=throttler,
        logger=logger
    )
