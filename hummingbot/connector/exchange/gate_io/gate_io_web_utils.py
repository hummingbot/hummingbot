import time
import logging
import random
import asyncio
from typing import Any, Callable, Dict, Optional, Tuple
from dataclasses import dataclass

import hummingbot.connector.exchange.gate_io.gate_io_constants as CONSTANTS
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTResponse,
    RESTRequest,
    EndpointRESTRequest
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant

EXCHANGE = "GateIo"
CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = [0.2, 0.2]


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint

    :param path_url: a public REST endpoint
    :param domain: unused

    :return: the full URL to the endpoint
    """
    if CONSTANTS.REST_URL[-1] != '/' and path_url[0] != '/':
        path_url = '/' + path_url
    return CONSTANTS.REST_URL + path_url


def private_rest_url(path_url: str, domain: str = "") -> str:
    return public_rest_url(path_url, domain)


def build_api_factory(
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


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
    close_session = False
    if not api_factory:
        api_factory = build_api_factory(
            throttler=throttler,
            time_synchronizer=time_synchronizer,
            domain=domain,
        )
        close_session = True

    rest_assistant = await api_factory.get_rest_assistant()
    local_headers = {
        "Content-Type": "application/json" if method == RESTMethod.POST else "application/x-www-form-urlencoded"}
    local_headers.update(headers)
    if is_auth_required:
        url = private_rest_url(path, domain=domain)
    else:
        url = public_rest_url(path, domain=domain)

    request = RESTRequest(
        method=method,
        url=url,
        params=params,
        data=data,
        headers=local_headers,
        is_auth_required=is_auth_required,
        throttler_limit_id=limit_id if limit_id else path
    )

    def close_session_if():
        if close_session:
            await api_factory._connections_factory._shared_client.close()

    async with throttler.execute_task(limit_id=limit_id if limit_id else path):
        response = await rest_assistant.call(request=request, timeout=timeout)
        if response.status not in (200, 201):
            if return_err:
                error_response = await response.json()
                close_session_if()
                return error_response
            else:
                error_response = await response.text()
                close_session_if()
                if error_response is not None and "code" in error_response and "msg" in error_response:
                    raise IOError(f"The request to {EXCHANGE} failed. Error: {error_response}. Request: {request}")
                else:
                    raise IOError(f"Error executing request {method.name} {path}. "
                                  f"HTTP status is {response.status}. "
                                  f"Error: {error_response}")
        j = await response.json()
        close_session_if()
        return j


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    # TODO
    return time.time()


@dataclass
class GateIORESTRequest(EndpointRESTRequest):
    @property
    def base_url(self) -> str:
        return CONSTANTS.REST_URL

    @property
    def auth_url(self) -> str:
        if self.endpoint is None:
            raise ValueError("No endpoint specified. Cannot build auth url.")
        auth_url = f"{CONSTANTS.REST_URL_AUTH}/{self.endpoint}"
        return auth_url


class GateIoAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload
        self.http_status = error_payload.get('status')
        if isinstance(error_payload, dict):
            self.error_message = error_payload.get('error', error_payload).get('message', error_payload)
            self.error_label = error_payload.get('error', error_payload).get('label', error_payload)
        else:
            self.error_message = error_payload
            self.error_label = error_payload


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = trading_pair.split('_')
        return m[0], m[1]
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(ex_trading_pair: str) -> Optional[str]:
    regex_match = split_trading_pair(ex_trading_pair)
    if regex_match is None:
        return None
    # Gate.io uses uppercase with underscore split (BTC_USDT)
    base_asset, quote_asset = split_trading_pair(ex_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Gate.io uses uppercase with underscore split (BTC_USDT)
    return hb_trading_pair.replace("-", "_").upper()


def retry_sleep_time(try_count: int) -> float:
    random.seed()
    randSleep = 1 + float(random.randint(1, 10) / 100)
    return float(2 + float(randSleep * (1 + (try_count ** try_count))))


async def rest_response_with_errors(request_coroutine):
    http_status, parsed_response, request_errors = None, None, False
    try:
        response: RESTResponse = await request_coroutine
        http_status = response.status
        try:
            parsed_response = await response.json()
        except Exception:
            request_errors = True
            try:
                parsed_response = await response.text()
                if len(parsed_response) > 100:
                    parsed_response = f"{parsed_response[:100]} ... (truncated)"
            except Exception:
                pass
        TempFailure = (parsed_response is None or
                       (response.status not in [200, 201, 204] and "message" not in parsed_response))
        if TempFailure:
            parsed_response = (
                f"Failed with status code {response.status}" if parsed_response is None else parsed_response
            )
            request_errors = True
    except Exception:
        request_errors = True
    return http_status, parsed_response, request_errors


async def _sleep(delay):
    """
    Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
    """
    await asyncio.sleep(delay)


async def api_call_with_retries(request: GateIORESTRequest,
                                rest_assistant: RESTAssistant,
                                throttler: AsyncThrottler,
                                logger: logging.Logger,
                                gate_io_auth: Optional[AuthBase] = None,
                                try_count: int = 0) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}

    async with throttler.execute_task(limit_id=request.throttler_limit_id):
        if request.is_auth_required:
            if gate_io_auth is None:
                raise RuntimeError(
                    f"Authentication required for request, but no GateIoAuth object supplied."
                    f" Request: {request}."
                )
            auth_params = request.data if request.method == RESTMethod.POST else request.params
            request.data = auth_params
            headers: dict = gate_io_auth.get_headers(str(request.method), request.auth_url, auth_params)
        request.headers = headers
        response_coro = asyncio.wait_for(rest_assistant.call(request), CONSTANTS.API_CALL_TIMEOUT)
        http_status, parsed_response, request_errors = await rest_response_with_errors(response_coro)

    if request_errors or parsed_response is None:
        if try_count < CONSTANTS.API_MAX_RETRIES:
            try_count += 1
            time_sleep = retry_sleep_time(try_count)
            logger.info(
                f"Error fetching data from {request.url}. HTTP status is {http_status}."
                f" Retrying in {time_sleep:.0f}s."
            )
            await _sleep(time_sleep)
            return await api_call_with_retries(
                request, rest_assistant, throttler, logger, gate_io_auth, try_count
            )
        else:
            raise GateIoAPIError({"label": "HTTP_ERROR", "message": parsed_response, "status": http_status})

    if "message" in parsed_response:
        raise GateIoAPIError(parsed_response)

    return parsed_response


KEYS = {
    "gate_io_api_key":
        ConfigVar(key="gate_io_api_key",
                  prompt=f"Enter your {CONSTANTS.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("gate_io"),
                  is_secure=True,
                  is_connect_key=True),
    "gate_io_secret_key":
        ConfigVar(key="gate_io_secret_key",
                  prompt=f"Enter your {CONSTANTS.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("gate_io"),
                  is_secure=True,
                  is_connect_key=True),
}
