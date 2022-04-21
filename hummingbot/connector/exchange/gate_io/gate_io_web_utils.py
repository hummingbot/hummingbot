import time
import logging
import random
import asyncio
from typing import Any, Callable, Dict, Optional, Tuple, AsyncIterable, List

import hummingbot.connector.exchange.gate_io.gate_io_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


def public_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint

    :param endpoint: a public REST endpoint
    :param domain: unused

    :return: the full URL to the endpoint
    """
    if CONSTANTS.REST_URL[-1] != '/' and endpoint[0] != '/':
        endpoint = '/' + endpoint
    return CONSTANTS.REST_URL + endpoint


def private_rest_url(endpoint: str, domain: str = "") -> str:
    return public_rest_url(endpoint, domain)


def build_api_factory(
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(auth=auth)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def api_request(path: Optional[str] = None,
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
                      headers: Dict[str, Any] = {},
                      retry: bool = False,
                      retry_logger: Optional[logging.Logger] = None):
    close_session = False
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    if retry and return_err:
        raise ValueError("Both retry and return_err are True")

    # If api_factory is not provided a default one is created
    # The default instance has no authentication capabilities and all authenticated requests will fail
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

    async def close_session_if():
        if close_session:
            await api_factory._connections_factory._shared_client.close()

    retries = 0
    if not retry:
        retries = CONSTANTS.API_MAX_RETRIES - 1

    while retries < CONSTANTS.API_MAX_RETRIES:
        retries += 1

        async with throttler.execute_task(limit_id=limit_id if limit_id else path):
            response = await rest_assistant.call(request=request, timeout=timeout)
            if response.status in (200, 201):
                j = await response.json()
                await close_session_if()
                return j

            # handling of retries
            if retry and not return_err:
                # if retries is == max, we continue and raise exception
                if retries < CONSTANTS.API_MAX_RETRIES:
                    time_sleep = retry_sleep_time(retries)
                    retry_logger.info(
                        f"Error fetching data from {request.url}. HTTP status is {response.status}."
                        f" Retrying {retries}/{CONSTANTS.API_MAX_RETRIES} in {time_sleep:.0f}s."
                    )
                    await _sleep(time_sleep)
                    continue

            if return_err:
                error_response = await response.json()
                await close_session_if()
                return error_response

            error_response = await response.text()
            await close_session_if()
            if error_response is not None and "code" in error_response and "msg" in error_response:
                raise IOError(
                    f"The request to {CONSTANTS.EXCHANGE_NAME} failed. Error: {error_response}. Request: {request}")
            else:
                raise IOError(
                    f"Error executing request {method.name} {path}. HTTP status is {response.status}. "
                    f"Error: {error_response}")


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    return time.time()


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


async def _sleep(delay):
    """
    To facilitate patching the sleep in unit tests without affecting the asyncio module
    """
    await asyncio.sleep(delay)


class APIError(IOError):
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


class GateIoWebsocket:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[GateIoAuth] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        self._auth: Optional[GateIoAuth] = auth
        self._is_private = True if self._auth is not None else False
        self._api_factory = api_factory or build_api_factory()
        self._ws_assistant: Optional[WSAssistant] = None
        self._closed = True

    @property
    def last_recv_time(self) -> float:
        last_recv_time = 0
        if self._ws_assistant is not None:
            last_recv_time = self._ws_assistant.last_recv_time
        return last_recv_time

    async def connect(self):
        self._ws_assistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(
            ws_url=CONSTANTS.WS_URL,
            ping_timeout=CONSTANTS.PING_TIMEOUT,
            message_timeout=CONSTANTS.MESSAGE_TIMEOUT,
        )
        self._closed = False

    async def disconnect(self):
        self._closed = True
        if self._ws_assistant is not None:
            await self._ws_assistant.disconnect()
            self._ws_assistant = None

    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    msg = await self._get_message()
                    data = msg.data

                    # Raise API error for login failures.
                    if data.get("error", None) is not None:
                        err_msg = data.get("error", {}).get("message", data["error"])
                        raise APIError({
                            "label": "WSS_ERROR",
                            "message": f"Error received via websocket - {err_msg}."
                        })

                    if data.get("channel") == "spot.pong":
                        continue

                    yield data

                except ValueError:
                    self.logger().debug("Unexpected error during _messages", exc_info=True)
                    continue
        except ConnectionError:
            if not self._closed:
                self.logger().warning("The websocket connection was unexpectedly closed.")
        finally:
            await self.disconnect()

    async def _get_message(self) -> WSResponse:
        try:
            response = await self._ws_assistant.receive()
        except asyncio.TimeoutError:
            self.logger().debug("Message receive timed out. Sending ping.")
            await self.request(channel="spot.ping")
            response = await self._ws_assistant.receive()
        return response

    async def _emit(self, channel: str, data: Optional[Dict[str, Any]] = None) -> int:
        data = data or {}
        payload = {
            "time": int(time.time()),
            "channel": channel,
            **data,
        }
        # if auth class was passed into websocket class
        # we need to emit authenticated requests
        if self._is_private:
            payload["auth"] = self._auth._get_auth_headers_ws(payload)
        request = WSRequest(payload)
        await self._ws_assistant.send(request)
        return payload["time"]

    async def request(self, channel: str, data: Optional[Dict[str, Any]] = None) -> int:
        data = data or {}
        return await self._emit(channel, data)

    async def subscribe(self,
                        channel: str,
                        trading_pairs: Optional[List[str]] = None) -> int:
        ws_params = {
            "event": "subscribe",
        }
        if trading_pairs is not None:
            ws_params["payload"] = trading_pairs
        return await self.request(channel, ws_params)

    async def unsubscribe(self,
                          channel: str,
                          trading_pairs: Optional[List[str]] = None) -> int:
        ws_params = {
            "event": "unsubscribe",
        }
        if trading_pairs is not None:
            ws_params["payload"] = trading_pairs
        return await self.request(channel, ws_params)

    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
