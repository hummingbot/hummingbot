import json
import asyncio
from typing import Callable
from copy import deepcopy
from typing import (
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Any,
    Union
)
from asyncio import wait_for
import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from threading import Lock
lock = Lock()


class RESTAssistant_SX:
    """A helper class to contain all REST-related logic.

    The class can be injected with additional functionality by passing a list of objects inheriting from
    the `RESTPreProcessorBase` and `RESTPostProcessorBase` classes. The pre-processors are applied to a request
    before it is sent out, while the post-processors are applied to a response before it is returned to the caller.
    """
    def __init__(
        self,
        connection: RESTConnection,
        throttler: AsyncThrottlerBase,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connection = connection
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._auth = auth
        self._throttler = throttler
        self._lock = asyncio.Lock()

    async def execute_request(
            self,
            url: str,
            throttler_limit_id: str,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            method: RESTMethod = RESTMethod.GET,
            is_auth_required: bool = False,
            return_err: bool = False,
            timeout: Optional[float] = None,
            headers: Optional[Dict[str, Any]] = None) -> Union[str, Dict[str, Any]]:
        with await self._lock:
            data = json.dumps(data)
            auth_ = None
            if is_auth_required:
                auth_ = self._auth.get_auth_headers(url, params)
                data = json.dumps(auth_['data'])
            else:
                auth_ = self._auth.get_headers()
            headers = auth_['header'] or {}
            local_headers = {
                "Content-Type": ("application/json" if method in [RESTMethod.POST, RESTMethod.PUT]
                                 else "application/x-www-form-urlencoded")}
            local_headers.update(headers)

            request = RESTRequest(
                method=method,
                url=url,
                params=None,
                data=data or {},
                headers=local_headers,
                is_auth_required=False,
                throttler_limit_id=throttler_limit_id
            )

            async with self._throttler.execute_task(limit_id=throttler_limit_id):
                response = await self.call(request=request, timeout=timeout)

                if 400 <= response.status:
                    if return_err:
                        error_response = await response.json()
                        return error_response
                    else:
                        error_response = await response.text()
                        raise IOError(f"Error executing request {method.name} {url}. HTTP status is {response.status}. "
                                      f"Error: {error_response}.")
                elif response.status == 204:
                    return "ok"
                else:
                    result = await response.json()
                    return result

    async def call(self, request: RESTRequest, timeout: Optional[float] = None) -> RESTResponse:
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        request = await self._authenticate(request)
        resp = await wait_for(self._connection.call(request), timeout)
        resp = await self._post_process_response(resp)
        return resp

    async def _pre_process_request(self, request: RESTRequest) -> RESTRequest:
        for pre_processor in self._rest_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _authenticate(self, request: RESTRequest):
        if self._auth is not None and request.is_auth_required:
            request = await self._auth.rest_authenticate(request)
        return request

    async def _post_process_response(self, response: RESTResponse) -> RESTResponse:
        for post_processor in self._rest_post_processors:
            response = await post_processor.post_process(response)
        return response


class WSAssistant_SX:
    """A helper class to contain all WebSocket-related logic.

    The class can be injected with additional functionality by passing a list of objects inheriting from
    the `WSPreProcessorBase` and `WSPostProcessorBase` classes. The pre-processors are applied to a request
    before it is sent out, while the post-processors are applied to a response before it is returned to the caller.
    """

    def __init__(
        self,
        connection: WSConnection,
        ws_pre_processors: Optional[List[WSPreProcessorBase]] = None,
        ws_post_processors: Optional[List[WSPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connection = connection
        self._ws_pre_processors = ws_pre_processors or []
        self._ws_post_processors = ws_post_processors or []
        self._auth = auth

    @property
    def last_recv_time(self) -> float:
        return self._connection.last_recv_time

    async def connect(
        self,
        ws_url: str,
        *,
        ping_timeout: float = 10,
        message_timeout: Optional[float] = None,
        ws_headers: Optional[Dict] = {},
    ):
        await self._connection.connect(ws_url=ws_url, ws_headers=ws_headers, ping_timeout=ping_timeout, message_timeout=message_timeout)

    async def disconnect(self):
        await self._connection.disconnect()

    async def subscribe(self, request: WSRequest):
        """Will eventually be used to handle automatic re-connection."""
        await self.send(request)

    async def send(self, request: WSRequest):
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        request = await self._authenticate(request)
        await self._connection.send(request)

    async def ping(self):
        await self._connection.ping()

    async def iter_messages(self) -> AsyncGenerator[Optional[WSResponse], None]:
        """Will yield None and stop if `WSDelegate.disconnect()` is called while waiting for a response."""
        while self._connection.connected:
            response = await self._connection.receive()
            if response is not None:
                response = await self._post_process_response(response)
                yield response

    async def receive(self) -> Optional[WSResponse]:
        """This method will return `None` if `WSDelegate.disconnect()` is called while waiting for a response."""
        response = await self._connection.receive()
        if response is not None:
            response = await self._post_process_response(response)
        return response

    async def _pre_process_request(self, request: WSRequest) -> WSRequest:
        for pre_processor in self._ws_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _authenticate(self, request: WSRequest) -> WSRequest:
        if self._auth is not None and request.is_auth_required:
            request = await self._auth.ws_authenticate(request)
        return request

    async def _post_process_response(self, response: WSResponse) -> WSResponse:
        for post_processor in self._ws_post_processors:
            response = await post_processor.post_process(response)
        return response


class WebAssistantsFactory_SX:
    """Creates `RESTAssistant` and `WSAssistant` objects.

    The purpose of the `web_assistant` layer is to abstract away all WebSocket and REST operations from the exchange
    logic. The assistant objects are designed to be injectable with additional logic via the pre- and post-processor
    lists. Consult the documentation of the relevant assistant and/or pre-/post-processor class for
    additional information.

    todo: integrate AsyncThrottler
    """
    def __init__(
        self,
        throttler: AsyncThrottlerBase,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        ws_pre_processors: Optional[List[WSPreProcessorBase]] = None,
        ws_post_processors: Optional[List[WSPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connections_factory = ConnectionsFactory()
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._ws_pre_processors = ws_pre_processors or []
        self._ws_post_processors = ws_post_processors or []
        self._auth = auth
        self._throttler = throttler

    @property
    def throttler(self) -> AsyncThrottlerBase:
        return self._throttler

    async def get_rest_assistant(self) -> RESTAssistant_SX:
        connection = await self._connections_factory.get_rest_connection()
        assistant = RESTAssistant_SX(
            connection=connection,
            throttler=self._throttler,
            rest_pre_processors=self._rest_pre_processors,
            rest_post_processors=self._rest_post_processors,
            auth=self._auth
        )
        return assistant

    async def get_ws_assistant(self) -> WSAssistant_SX:
        connection = await self._connections_factory.get_ws_connection()
        assistant = WSAssistant_SX(
            connection, self._ws_pre_processors, self._ws_post_processors, self._auth
        )
        return assistant


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory_SX:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory_SX(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory_SX:
    api_factory = WebAssistantsFactory_SX(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
    )
    server_time = response["serverTime"]
    return server_time
