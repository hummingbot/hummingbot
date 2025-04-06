import asyncio
import json
import logging
import os
from typing import (
    Any,
    Dict,
    Optional,
    Union,
)

from eth_typing import (
    URI,
)
from toolz import (
    merge,
)
from websockets.exceptions import (
    ConnectionClosedOK,
    WebSocketException,
)
from websockets.legacy.client import (
    WebSocketClientProtocol,
    connect,
)

from web3.exceptions import (
    PersistentConnectionClosedOK,
    ProviderConnectionError,
    Web3ValidationError,
)
from web3.providers.persistent import (
    PersistentConnectionProvider,
)
from web3.types import (
    RPCResponse,
)

DEFAULT_PING_INTERVAL = 30  # 30 seconds
DEFAULT_PING_TIMEOUT = 300  # 5 minutes

VALID_WEBSOCKET_URI_PREFIXES = {"ws://", "wss://"}
RESTRICTED_WEBSOCKET_KWARGS = {"uri", "loop"}
DEFAULT_WEBSOCKET_KWARGS = {
    # set how long to wait between pings from the server
    "ping_interval": DEFAULT_PING_INTERVAL,
    # set how long to wait without a pong response before closing the connection
    "ping_timeout": DEFAULT_PING_TIMEOUT,
}


def get_default_endpoint() -> URI:
    return URI(os.environ.get("WEB3_WS_PROVIDER_URI", "ws://127.0.0.1:8546"))


class WebSocketProvider(PersistentConnectionProvider):
    logger = logging.getLogger("web3.providers.WebSocketProvider")
    is_async: bool = True

    def __init__(
        self,
        endpoint_uri: Optional[Union[URI, str]] = None,
        websocket_kwargs: Optional[Dict[str, Any]] = None,
        # uses binary frames by default
        use_text_frames: Optional[bool] = False,
        # `PersistentConnectionProvider` kwargs can be passed through
        **kwargs: Any,
    ) -> None:
        # initialize the endpoint_uri before calling the super constructor
        self.endpoint_uri = (
            URI(endpoint_uri) if endpoint_uri is not None else get_default_endpoint()
        )
        super().__init__(**kwargs)
        self.use_text_frames = use_text_frames
        self._ws: Optional[WebSocketClientProtocol] = None

        if not any(
            self.endpoint_uri.startswith(prefix)
            for prefix in VALID_WEBSOCKET_URI_PREFIXES
        ):
            raise Web3ValidationError(
                "WebSocket endpoint uri must begin with 'ws://' or 'wss://': "
                f"{self.endpoint_uri}"
            )

        if websocket_kwargs is not None:
            found_restricted_keys = set(websocket_kwargs).intersection(
                RESTRICTED_WEBSOCKET_KWARGS
            )
            if found_restricted_keys:
                raise Web3ValidationError(
                    "Found restricted keys for websocket_kwargs: "
                    f"{found_restricted_keys}."
                )

        self.websocket_kwargs = merge(DEFAULT_WEBSOCKET_KWARGS, websocket_kwargs or {})

    def __str__(self) -> str:
        return f"WebSocket connection: {self.endpoint_uri}"

    async def is_connected(self, show_traceback: bool = False) -> bool:
        if not self._ws:
            return False

        try:
            await self._ws.pong()
            return True

        except WebSocketException as e:
            if show_traceback:
                raise ProviderConnectionError(
                    f"Error connecting to endpoint: '{self.endpoint_uri}'"
                ) from e
            return False

    async def socket_send(self, request_data: bytes) -> None:
        if self._ws is None:
            raise ProviderConnectionError(
                "Connection to websocket has not been initiated for the provider."
            )

        payload: Union[bytes, str] = request_data
        if self.use_text_frames:
            payload = request_data.decode("utf-8")

        await asyncio.wait_for(self._ws.send(payload), timeout=self.request_timeout)

    async def socket_recv(self) -> RPCResponse:
        raw_response = await self._ws.recv()
        return json.loads(raw_response)

    # -- private methods -- #

    async def _provider_specific_connect(self) -> None:
        self._ws = await connect(self.endpoint_uri, **self.websocket_kwargs)

    async def _provider_specific_disconnect(self) -> None:
        # this should remain idempotent
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
            self._ws = None

    async def _provider_specific_socket_reader(self) -> RPCResponse:
        try:
            return await self.socket_recv()
        except ConnectionClosedOK:
            raise PersistentConnectionClosedOK(
                user_message="WebSocket connection received `ConnectionClosedOK`."
            )
