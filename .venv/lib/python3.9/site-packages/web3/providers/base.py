import itertools
import logging
import threading
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from eth_utils import (
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
    combine_middleware,
)
from web3.middleware.base import (
    Middleware,
    MiddlewareOnion,
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)
from web3.utils import (
    RequestCacheValidationThreshold,
    SimpleCache,
)

if TYPE_CHECKING:
    from web3 import Web3  # noqa: F401


class BaseProvider:
    # Set generic logger for the provider. Override in subclasses for more specificity.
    logger: logging.Logger = logging.getLogger("web3.providers.base.BaseProvider")
    # a tuple of (middleware, request_func)
    _request_func_cache: Tuple[Tuple[Middleware, ...], Callable[..., RPCResponse]] = (
        None,
        None,
    )

    is_async = False
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
        self._request_cache_lock: threading.Lock = threading.Lock()

        self.cache_allowed_requests = cache_allowed_requests
        self.cacheable_requests = cacheable_requests or CACHEABLE_REQUESTS
        self.request_cache_validation_threshold = request_cache_validation_threshold

    def request_func(
        self, w3: "Web3", middleware_onion: MiddlewareOnion
    ) -> Callable[..., RPCResponse]:
        """
        @param w3 is the web3 instance
        @param middleware_onion is an iterable of middleware,
            ordered by first to execute
        @returns a function that calls all the middleware and
            eventually self.make_request()
        """
        middleware: Tuple[Middleware, ...] = middleware_onion.as_tuple_of_middleware()

        cache_key = self._request_func_cache[0]
        if cache_key != middleware:
            self._request_func_cache = (
                middleware,
                combine_middleware(
                    middleware=middleware,
                    w3=w3,
                    provider_request_fn=self.make_request,
                ),
            )

        return self._request_func_cache[-1]

    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        raise NotImplementedError("Providers must implement this method")

    def is_connected(self, show_traceback: bool = False) -> bool:
        raise NotImplementedError("Providers must implement this method")


class JSONBaseProvider(BaseProvider):
    logger = logging.getLogger("web3.providers.base.JSONBaseProvider")

    _is_batching: bool = False
    _batch_request_func_cache: Tuple[
        Tuple[Middleware, ...], Callable[..., Union[List[RPCResponse], RPCResponse]]
    ] = (None, None)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.request_counter = itertools.count()

    def encode_rpc_request(self, method: RPCEndpoint, params: Any) -> bytes:
        rpc_dict = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": next(self.request_counter),
        }
        encoded = FriendlyJsonSerde().json_encode(rpc_dict, Web3JsonEncoder)
        return to_bytes(text=encoded)

    @staticmethod
    def decode_rpc_response(raw_response: bytes) -> RPCResponse:
        text_response = to_text(raw_response)
        return cast(RPCResponse, FriendlyJsonSerde().json_decode(text_response))

    def is_connected(self, show_traceback: bool = False) -> bool:
        try:
            response = self.make_request(RPCEndpoint("web3_clientVersion"), [])
        except OSError as e:
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

        if response["jsonrpc"] == "2.0":
            return True
        else:
            if show_traceback:
                raise ProviderConnectionError(f"Bad jsonrpc version: {response}")
            return False

    #  -- batch requests -- #

    def batch_request_func(
        self, w3: "Web3", middleware_onion: MiddlewareOnion
    ) -> Callable[..., Union[List[RPCResponse], RPCResponse]]:
        middleware: Tuple[Middleware, ...] = middleware_onion.as_tuple_of_middleware()

        cache_key = self._batch_request_func_cache[0]
        if cache_key != middleware:
            accumulator_fn = self.make_batch_request
            for mw in reversed(middleware):
                initialized = mw(w3)
                # type ignore bc in order to wrap the method, we have to call
                # `wrap_make_batch_request` with the accumulator_fn as the argument
                # which breaks the type hinting for this particular case.
                accumulator_fn = initialized.wrap_make_batch_request(
                    accumulator_fn
                )  # type: ignore  # noqa: E501
            self._batch_request_func_cache = (middleware, accumulator_fn)

        return self._batch_request_func_cache[-1]

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

    def make_batch_request(
        self, requests: List[Tuple[RPCEndpoint, Any]]
    ) -> Union[List[RPCResponse], RPCResponse]:
        raise NotImplementedError("Providers must implement this method")
