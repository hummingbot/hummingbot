from json import (
    JSONDecodeError,
)
import logging
import os
from pathlib import (
    Path,
)
import socket
import sys
import threading
from types import (
    TracebackType,
)
from typing import (
    Any,
    List,
    Tuple,
    Type,
    Union,
    cast,
)

from web3._utils.threads import (
    Timeout,
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)

from .._utils.batching import (
    sort_batch_response_by_response_ids,
)
from .._utils.caching import (
    handle_request_caching,
)
from ..exceptions import (
    Web3TypeError,
    Web3ValueError,
)
from .base import (
    JSONBaseProvider,
)


def get_ipc_socket(ipc_path: str, timeout: float = 2.0) -> socket.socket:
    if sys.platform == "win32":
        # On Windows named pipe is used. Simulate socket with it.
        from web3._utils.windows import (
            NamedPipe,
        )

        return NamedPipe(ipc_path)
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(ipc_path)
        sock.settimeout(timeout)
        return sock


class PersistantSocket:
    sock = None

    def __init__(self, ipc_path: str) -> None:
        self.ipc_path = ipc_path

    def __enter__(self) -> socket.socket:
        if not self.ipc_path:
            raise FileNotFoundError(
                f"cannot connect to IPC socket at path: {self.ipc_path!r}"
            )

        if not self.sock:
            self.sock = self._open()
        return self.sock

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        # only close the socket if there was an error
        if exc_value is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _open(self) -> socket.socket:
        return get_ipc_socket(self.ipc_path)

    def reset(self) -> socket.socket:
        self.sock.close()
        self.sock = self._open()
        return self.sock


def get_default_ipc_path() -> str:
    if sys.platform == "darwin":
        return os.path.expanduser(os.path.join("~", "Library", "Ethereum", "geth.ipc"))

    elif sys.platform.startswith("linux") or sys.platform.startswith("freebsd"):
        return os.path.expanduser(os.path.join("~", ".ethereum", "geth.ipc"))

    elif sys.platform == "win32":
        return r"\\.\pipe\geth.ipc"

    else:
        raise Web3ValueError(
            f"Unsupported platform '{sys.platform}'. Only darwin/linux/win32/"
            "freebsd are supported.  You must specify the ipc_path"
        )


def get_dev_ipc_path() -> str:
    web3_provider_uri = os.environ.get("WEB3_PROVIDER_URI", "")
    if web3_provider_uri and "geth.ipc" in web3_provider_uri:
        return web3_provider_uri

    elif sys.platform == "darwin" or sys.platform.startswith("linux"):
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        return os.path.expanduser(os.path.join(tmpdir, "geth.ipc"))

    elif sys.platform.endswith("freebsd"):
        return os.path.expanduser(os.path.join("/tmp", "geth.ipc"))

    elif sys.platform == "win32":
        return r"\\.\pipe\geth.ipc"

    else:
        raise Web3ValueError(
            f"Unsupported platform '{sys.platform}'. Only darwin/linux/win32/"
            "freebsd are supported.  You must specify the ipc_path"
        )


class IPCProvider(JSONBaseProvider):
    logger = logging.getLogger("web3.providers.IPCProvider")
    _socket = None

    def __init__(
        self,
        ipc_path: Union[str, Path] = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if ipc_path is None:
            self.ipc_path = get_default_ipc_path()
        elif isinstance(ipc_path, str) or isinstance(ipc_path, Path):
            self.ipc_path = str(Path(ipc_path).expanduser().resolve())
        else:
            raise Web3TypeError("ipc_path must be of type string or pathlib.Path")

        self.timeout = timeout
        self._lock = threading.Lock()
        self._socket = PersistantSocket(self.ipc_path)

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {self.ipc_path}>"

    def _make_request(self, request: bytes) -> RPCResponse:
        with self._lock, self._socket as sock:
            try:
                sock.sendall(request + b"\n")
            except BrokenPipeError:
                # one extra attempt, then give up
                sock = self._socket.reset()
                sock.sendall(request)

            raw_response = b""
            with Timeout(self.timeout) as timeout:
                while True:
                    try:
                        raw_response += sock.recv(4096)
                    except socket.timeout:
                        timeout.sleep(0)
                        continue
                    if raw_response == b"":
                        timeout.sleep(0)
                    elif has_valid_json_rpc_ending(raw_response):
                        try:
                            response = self.decode_rpc_response(raw_response)
                        except JSONDecodeError:
                            timeout.sleep(0)
                            continue
                        else:
                            return response
                    else:
                        timeout.sleep(0)
                        continue

    @handle_request_caching
    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug(
            f"Making request IPC. Path: {self.ipc_path}, Method: {method}"
        )
        request = self.encode_rpc_request(method, params)
        return self._make_request(request)

    def make_batch_request(
        self, requests: List[Tuple[RPCEndpoint, Any]]
    ) -> List[RPCResponse]:
        self.logger.debug(f"Making batch request IPC. Path: {self.ipc_path}")
        request_data = self.encode_batch_rpc_request(requests)
        response = cast(List[RPCResponse], self._make_request(request_data))
        return sort_batch_response_by_response_ids(response)


# A valid JSON RPC response can only end in } or ] http://www.jsonrpc.org/specification
def has_valid_json_rpc_ending(raw_response: bytes) -> bool:
    stripped_raw_response = raw_response.rstrip()
    for valid_ending in [b"}", b"]"]:
        if stripped_raw_response.endswith(valid_ending):
            return True
    else:
        return False
