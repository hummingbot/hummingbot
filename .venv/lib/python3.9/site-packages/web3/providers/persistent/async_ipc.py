import asyncio
import errno
import json
import logging
from pathlib import (
    Path,
)
import sys
from typing import (
    Any,
    Optional,
    Tuple,
    Union,
)

from web3.types import (
    RPCEndpoint,
    RPCResponse,
)

from . import (
    PersistentConnectionProvider,
)
from ...exceptions import (
    PersistentConnectionClosedOK,
    ProviderConnectionError,
    ReadBufferLimitReached,
    Web3TypeError,
)
from ..ipc import (
    get_default_ipc_path,
)


async def async_get_ipc_socket(
    ipc_path: str, read_buffer_limit: int
) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    if sys.platform == "win32":
        # On Windows named pipe is used. Simulate socket with it.
        from web3._utils.windows import (
            NamedPipe,
        )

        return NamedPipe(ipc_path)
    else:
        return await asyncio.open_unix_connection(ipc_path, limit=read_buffer_limit)


class AsyncIPCProvider(PersistentConnectionProvider):
    logger = logging.getLogger("web3.providers.AsyncIPCProvider")

    _reader: Optional[asyncio.StreamReader] = None
    _writer: Optional[asyncio.StreamWriter] = None
    _decoder: json.JSONDecoder = json.JSONDecoder()

    def __init__(
        self,
        ipc_path: Optional[Union[str, Path]] = None,
        read_buffer_limit: int = 20 * 1024 * 1024,  # 20 MB
        # `PersistentConnectionProvider` kwargs can be passed through
        **kwargs: Any,
    ) -> None:
        # initialize the ipc_path before calling the super constructor
        if ipc_path is None:
            self.ipc_path = get_default_ipc_path()
        elif isinstance(ipc_path, str) or isinstance(ipc_path, Path):
            self.ipc_path = str(Path(ipc_path).expanduser().resolve())
        else:
            raise Web3TypeError("ipc_path must be of type string or pathlib.Path")
        super().__init__(**kwargs)
        self.read_buffer_limit = read_buffer_limit

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {self.ipc_path}>"

    async def is_connected(self, show_traceback: bool = False) -> bool:
        if not self._writer or not self._reader:
            return False

        try:
            await self.make_request(RPCEndpoint("web3_clientVersion"), [])
            return True
        except (OSError, ProviderConnectionError) as e:
            if show_traceback:
                raise ProviderConnectionError(
                    f"Problem connecting to provider with error: {type(e)}: {e}"
                )
            return False

    async def socket_send(self, request_data: bytes) -> None:
        if self._writer is None:
            raise ProviderConnectionError(
                "Connection to ipc socket has not been initiated for the provider."
            )

        return await asyncio.wait_for(
            self._socket_send(request_data), timeout=self.request_timeout
        )

    async def socket_recv(self) -> RPCResponse:
        try:
            data = await self._reader.readline()
        except ValueError as e:
            if all(kw in str(e) for kw in ("limit", "chunk")):
                raise ReadBufferLimitReached(
                    f"Read buffer limit of `{self.read_buffer_limit}` bytes was "
                    "reached. Consider increasing the ``read_buffer_limit`` on the "
                    "AsyncIPCProvider."
                ) from e
            raise

        if not data:
            raise PersistentConnectionClosedOK("Socket reader received end of stream.")
        return self.decode_rpc_response(data)

    # -- private methods -- #

    async def _socket_send(self, request_data: bytes) -> None:
        try:
            self._writer.write(request_data + b"\n")
            await self._writer.drain()
        except OSError as e:
            # Broken pipe
            if e.errno == errno.EPIPE:
                # one extra attempt, then give up
                await self._reset_socket()
                self._writer.write(request_data)
                await self._writer.drain()

    async def _reset_socket(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()
        self._reader, self._writer = await async_get_ipc_socket(
            self.ipc_path, self.read_buffer_limit
        )

    async def _provider_specific_connect(self) -> None:
        self._reader, self._writer = await async_get_ipc_socket(
            self.ipc_path, self.read_buffer_limit
        )

    async def _provider_specific_disconnect(self) -> None:
        # this should remain idempotent
        if self._writer and not self._writer.is_closing():
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
        if self._reader:
            self._reader = None

    async def _provider_specific_socket_reader(self) -> RPCResponse:
        return await self.socket_recv()

    def _error_log_listener_task_exception(self, e: Exception) -> None:
        super()._error_log_listener_task_exception(e)
