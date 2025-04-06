import asyncio
import json
import logging
import os
from threading import (
    Thread,
)
from types import (
    TracebackType,
)
from typing import (
    Any,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

from eth_typing import (
    URI,
)
from websockets.legacy.client import (
    WebSocketClientProtocol,
    connect,
)

from web3._utils.batching import (
    sort_batch_response_by_response_ids,
)
from web3._utils.caching import (
    handle_request_caching,
)
from web3.exceptions import (
    Web3ValidationError,
)
from web3.providers.base import (
    JSONBaseProvider,
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)

RESTRICTED_WEBSOCKET_KWARGS = {"uri", "loop"}
DEFAULT_WEBSOCKET_TIMEOUT = 30


def _start_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()
    loop.close()


def _get_threaded_loop() -> asyncio.AbstractEventLoop:
    new_loop = asyncio.new_event_loop()
    thread_loop = Thread(target=_start_event_loop, args=(new_loop,), daemon=True)
    thread_loop.start()
    return new_loop


def get_default_endpoint() -> URI:
    return URI(os.environ.get("WEB3_WS_PROVIDER_URI", "ws://127.0.0.1:8546"))


class PersistentWebSocket:
    def __init__(self, endpoint_uri: URI, websocket_kwargs: Any) -> None:
        self.ws: Optional[WebSocketClientProtocol] = None
        self.endpoint_uri = endpoint_uri
        self.websocket_kwargs = websocket_kwargs

    async def __aenter__(self) -> WebSocketClientProtocol:
        if self.ws is None:
            self.ws = await connect(uri=self.endpoint_uri, **self.websocket_kwargs)
        return self.ws

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        if exc_val is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None


class LegacyWebSocketProvider(JSONBaseProvider):
    logger = logging.getLogger("web3.providers.WebSocketProvider")
    _loop = None

    def __init__(
        self,
        endpoint_uri: Optional[Union[URI, str]] = None,
        websocket_kwargs: Optional[Any] = None,
        websocket_timeout: int = DEFAULT_WEBSOCKET_TIMEOUT,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.endpoint_uri = URI(endpoint_uri)
        self.websocket_timeout = websocket_timeout
        if self.endpoint_uri is None:
            self.endpoint_uri = get_default_endpoint()
        if LegacyWebSocketProvider._loop is None:
            LegacyWebSocketProvider._loop = _get_threaded_loop()
        if websocket_kwargs is None:
            websocket_kwargs = {}
        else:
            found_restricted_keys = set(websocket_kwargs).intersection(
                RESTRICTED_WEBSOCKET_KWARGS
            )
            if found_restricted_keys:
                raise Web3ValidationError(
                    f"{RESTRICTED_WEBSOCKET_KWARGS} are not allowed "
                    f"in websocket_kwargs, found: {found_restricted_keys}"
                )
        self.conn = PersistentWebSocket(self.endpoint_uri, websocket_kwargs)

    def __str__(self) -> str:
        return f"WS connection {self.endpoint_uri}"

    async def coro_make_request(self, request_data: bytes) -> RPCResponse:
        async with self.conn as conn:
            await asyncio.wait_for(
                conn.send(request_data), timeout=self.websocket_timeout
            )
            return json.loads(
                await asyncio.wait_for(conn.recv(), timeout=self.websocket_timeout)
            )

    @handle_request_caching
    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug(
            f"Making request WebSocket. URI: {self.endpoint_uri}, " f"Method: {method}"
        )
        request_data = self.encode_rpc_request(method, params)
        future = asyncio.run_coroutine_threadsafe(
            self.coro_make_request(request_data), LegacyWebSocketProvider._loop
        )
        return future.result()

    def make_batch_request(
        self, requests: List[Tuple[RPCEndpoint, Any]]
    ) -> List[RPCResponse]:
        self.logger.debug(
            f"Making batch request WebSocket. URI: {self.endpoint_uri}, "
            f"Methods: {requests}"
        )
        request_data = self.encode_batch_rpc_request(requests)
        future = asyncio.run_coroutine_threadsafe(
            self.coro_make_request(request_data), LegacyWebSocketProvider._loop
        )
        response = cast(List[RPCResponse], future.result())
        return sort_batch_response_by_response_ids(response)
