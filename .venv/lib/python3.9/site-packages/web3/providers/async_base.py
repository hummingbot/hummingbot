import asyncio
import itertools
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from eth_utils import (
    is_text,
    to_bytes,
    to_text,
)

from web3._utils.caching import (
    CACHEABLE_REQUESTS,
)
from web3._utils.empty import (
    Empty,
    empty,
)
from web3._utils.encoding import (
    FriendlyJsonSerde,
    Web3JsonEncoder,
)
from web3.exceptions import (
    ProviderConnectionError,
)
from web3.middleware import (
    async_combine_middleware,
)
from web3.middleware.base import (
    Middleware,
    MiddlewareOnion,
)
from web3.types import (
    RPCEndpoint,
    RPCRequest,
    RPCResponse,
)
from web3.utils import (
    RequestCacheValidationThreshold,
    SimpleCache,
)

if TYPE_CHECKING:
    from websockets.legacy.client import (
        WebSocketClientProtocol,
    )

    from web3 import (  # noqa: F401
        AsyncWeb3,
        WebSocketProvider,
    )
    from web3.providers.persistent import (  # noqa: F401
        RequestProcessor,
    )


class AsyncBaseProvider:
    # Set generic logger for the provider. Override in subclasses for more specificity.
    logger: logging.Logger = logging.getLogger(
        "web3.providers.async_base.AsyncBaseProvider"
    )
    _request_func_cache: Tuple[
        Tuple[Middleware, ...], Callable[..., Coroutine[Any, Any, RPCResponse]]
    ] = (None, None)

    _is_batching: bool = False
    _batch_request_func_cache: Tuple[
        Tuple[Middleware, ...],
        Callable[..., Coroutine[Any, Any, Union[List[RPCResponse], RPCResponse]]],
    ] = (None, None)

    is_async = True
    has_persistent_connection = False
    global_ccip_read_enabled: bool = True
    ccip_read_max_redirects: int = 4

    def __init__(
        self,
        cache_allowed_requests: bool = False,
        cacheable_requests: Set[RPCEndpoint] = None,
        request_cache_validation_threshold: Optional[
            Union[RequestCacheValidationThreshold, int, Empty]
        ] = empty,
    ) -> None:
        self._request_cache = SimpleCache(1000)
        self._request_cache_lock: asyncio.Lock = asyncio.Lock()

        self.cache_allowed_requests = cache_allowed_requests
        self.cacheable_requests = cacheable_requests or CACHEABLE_REQUESTS
        self.request_cache_validation_threshold = request_cache_validation_threshold

    async def request_func(
        self, async_w3: "AsyncWeb3", middleware_onion: MiddlewareOnion
    ) -> Callable[..., Coroutine[Any, Any, RPCResponse]]:
        middleware: Tuple[Middleware, ...] = middleware_onion.as_tuple_of_middleware()

        cache_key = self._request_func_cache[0]
        if cache_key != middleware:
            self._request_func_cache = (
                middleware,
                await async_combine_middleware(
                    middleware=middleware,
                    async_w3=async_w3,
                    provider_request_fn=self.make_request,
                ),
            )
        return self._request_func_cache[-1]

    async def batch_request_func(
        self, async_w3: "AsyncWeb3", middleware_onion: MiddlewareOnion
    ) -> Callable[..., Coroutine[Any, Any, Union[List[RPCResponse], RPCResponse]]]:
        middleware: Tuple[Middleware, ...] = middleware_onion.as_tuple_of_middleware()

        cache_key = self._batch_request_func_cache[0]
        if cache_key != middleware:
            accumulator_fn = self.make_batch_request
            for mw in reversed(middleware):
                initialized = mw(async_w3)
                # type ignore bc in order to wrap the method, we have to call
                # `async_wrap_make_batch_request` with the accumulator_fn as the
                # argument which breaks the type hinting for this particular case.
                accumulator_fn = await initialized.async_wrap_make_batch_request(  # type: ignore # noqa: E501
                    accumulator_fn
                )
            self._batch_request_func_cache = (middleware, accumulator_fn)
        return self._batch_request_func_cache[-1]

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        raise NotImplementedError("Providers must implement this method")

    async def make_batch_request(
        self, requests: List[Tuple[RPCEndpoint, Any]]
    ) -> Union[List[RPCResponse], RPCResponse]:
        raise NotImplementedError("Providers must implement this method")

    async def is_connected(self, show_traceback: bool = False) -> bool:
        raise NotImplementedError("Providers must implement this method")

    # -- persistent connection providers -- #

    _request_processor: "RequestProcessor"
    _message_listener_task: "asyncio.Task[None]"
    _listen_event: "asyncio.Event"

    async def connect(self) -> None:
        raise NotImplementedError(
            "Persistent connection providers must implement this method"
        )

    async def disconnect(self) -> None:
        raise NotImplementedError(
            "Persistent connection providers must implement this method"
        )

    # WebSocket typing
    _ws: "WebSocketClientProtocol"

    # IPC typing
    _reader: Optional[asyncio.StreamReader]
    _writer: Optional[asyncio.StreamWriter]


class AsyncJSONBaseProvider(AsyncBaseProvider):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.request_counter = itertools.count()

    def form_request(self, method: RPCEndpoint, params: Any = None) -> RPCRequest:
        request_id = next(self.request_counter)
        rpc_dict = {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
        }
        return cast(RPCRequest, rpc_dict)

    @staticmethod
    def encode_rpc_dict(rpc_dict: RPCRequest) -> bytes:
        encoded = FriendlyJsonSerde().json_encode(
            cast(Dict[str, Any], rpc_dict), cls=Web3JsonEncoder
        )
        return to_bytes(text=encoded)

    def encode_rpc_request(self, method: RPCEndpoint, params: Any) -> bytes:
        rpc_dict = self.form_request(method, params)
        return self.encode_rpc_dict(rpc_dict)

    @staticmethod
    def decode_rpc_response(raw_response: bytes) -> RPCResponse:
        text_response = str(
            to_text(raw_response) if not is_text(raw_response) else raw_response
        )
        return cast(RPCResponse, FriendlyJsonSerde().json_decode(text_response))

    async def is_connected(self, show_traceback: bool = False) -> bool:
        try:
            response = await self.make_request(RPCEndpoint("web3_clientVersion"), [])
        except (OSError, ProviderConnectionError) as e:
            if show_traceback:
                raise ProviderConnectionError(
                    f"Problem connecting to provider with error: {type(e)}: {e}"
                )
            return False

        if "error" in response:
            if show_traceback:
                raise ProviderConnectionError(
                    f"Error received from provider: {response}"
                )
            return False

        if response.get("jsonrpc") == "2.0":
            return True
        else:
            if show_traceback:
                raise ProviderConnectionError(f"Bad jsonrpc version: {response}")
            return False

    # -- batch requests -- #

    def encode_batch_rpc_request(
        self, requests: List[Tuple[RPCEndpoint, Any]]
    ) -> bytes:
        return (
            b"["
            + b", ".join(
                self.encode_rpc_request(method, params) for method, params in requests
            )
            + b"]"
        )
