from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Literal,
    Optional,
    Union,
    cast,
)

from eth_abi import (
    abi,
)
from eth_abi.exceptions import (
    DecodingError,
)
from eth_utils import (
    is_bytes,
)

from web3.providers import (
    BaseProvider,
)
from web3.providers.async_base import (
    AsyncBaseProvider,
)
from web3.types import (
    RPCEndpoint,
    RPCError,
    RPCResponse,
)

from ...exceptions import (
    Web3TypeError,
)
from ...middleware import (
    async_combine_middleware,
    combine_middleware,
)
from .middleware import (
    default_transaction_fields_middleware,
    ethereum_tester_middleware,
)

if TYPE_CHECKING:
    from eth_tester import EthereumTester  # noqa: F401
    from eth_tester.backends.base import BaseChainBackend  # noqa: F401

    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.middleware.base import (  # noqa: F401
        Middleware,
        MiddlewareOnion,
        Web3Middleware,
    )


class AsyncEthereumTesterProvider(AsyncBaseProvider):
    _current_request_id = 0
    _middleware = (
        default_transaction_fields_middleware,
        ethereum_tester_middleware,
    )

    def __init__(self) -> None:
        super().__init__()

        # do not import eth_tester until runtime, it is not a default dependency
        from eth_tester import (
            EthereumTester,
        )

        from web3.providers.eth_tester.defaults import (
            API_ENDPOINTS,
        )

        self.ethereum_tester = EthereumTester()
        self.api_endpoints = API_ENDPOINTS

    async def request_func(
        self, async_w3: "AsyncWeb3", middleware_onion: "MiddlewareOnion"
    ) -> Callable[..., Coroutine[Any, Any, RPCResponse]]:
        # override the request_func to add the ethereum_tester_middleware

        middleware = middleware_onion.as_tuple_of_middleware() + tuple(self._middleware)

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

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        response = _make_request(
            method,
            params,
            self.api_endpoints,
            self.ethereum_tester,
            repr(self._current_request_id),
        )
        self._current_request_id += 1
        return response

    async def is_connected(self, show_traceback: bool = False) -> Literal[True]:
        return True


class EthereumTesterProvider(BaseProvider):
    _current_request_id = 0
    _middleware = (
        default_transaction_fields_middleware,
        ethereum_tester_middleware,
    )
    ethereum_tester = None
    api_endpoints: Optional[Dict[str, Dict[str, Callable[..., RPCResponse]]]] = None

    def __init__(
        self,
        ethereum_tester: Optional[Union["EthereumTester", "BaseChainBackend"]] = None,
        api_endpoints: Optional[
            Dict[str, Dict[str, Callable[..., RPCResponse]]]
        ] = None,
    ) -> None:
        # do not import eth_tester until runtime, it is not a default dependency
        super().__init__()
        from eth_tester import EthereumTester  # noqa: F811
        from eth_tester.backends.base import (
            BaseChainBackend,
        )

        if ethereum_tester is None:
            self.ethereum_tester = EthereumTester()
        elif isinstance(ethereum_tester, EthereumTester):
            self.ethereum_tester = ethereum_tester
        elif isinstance(ethereum_tester, BaseChainBackend):
            self.ethereum_tester = EthereumTester(ethereum_tester)
        else:
            raise Web3TypeError(
                "Expected ethereum_tester to be of type `eth_tester.EthereumTester` or "
                "a subclass of `eth_tester.backends.base.BaseChainBackend`, "
                f"instead received {type(ethereum_tester)}. "
                "If you would like a custom eth-tester instance to test with, see the "
                "eth-tester documentation. https://github.com/ethereum/eth-tester."
            )

        if api_endpoints is None:
            # do not import eth_tester derivatives until runtime,
            # it is not a default dependency
            from .defaults import (
                API_ENDPOINTS,
            )

            self.api_endpoints = API_ENDPOINTS
        else:
            self.api_endpoints = api_endpoints

    def request_func(
        self, w3: "Web3", middleware_onion: "MiddlewareOnion"
    ) -> Callable[..., RPCResponse]:
        # override the request_func to add the ethereum_tester_middleware

        middleware = middleware_onion.as_tuple_of_middleware() + tuple(self._middleware)

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
        response = _make_request(
            method,
            params,
            self.api_endpoints,
            self.ethereum_tester,
            repr(self._current_request_id),
        )
        self._current_request_id += 1
        return response

    def is_connected(self, show_traceback: bool = False) -> Literal[True]:
        return True


def _make_response(result: Any, response_id: str, message: str = "") -> RPCResponse:
    if isinstance(result, Exception):
        return cast(
            RPCResponse,
            {
                "id": response_id,
                "jsonrpc": "2.0",
                "error": cast(RPCError, {"code": -32601, "message": message}),
            },
        )

    return cast(RPCResponse, {"id": response_id, "jsonrpc": "2.0", "result": result})


def _make_request(
    method: RPCEndpoint,
    params: Any,
    api_endpoints: Dict[str, Dict[str, Any]],
    ethereum_tester_instance: "EthereumTester",
    request_id: str,
) -> RPCResponse:
    # do not import eth_tester derivatives until runtime,
    # it is not a default dependency
    from eth_tester.exceptions import (
        TransactionFailed,
    )

    namespace, _, endpoint = method.partition("_")

    try:
        delegator = api_endpoints[namespace][endpoint]
    except KeyError as e:
        return _make_response(e, request_id, message=f"Unknown RPC Endpoint: {method}")
    try:
        response = delegator(ethereum_tester_instance, params)
    except NotImplementedError as e:
        return _make_response(
            e,
            request_id,
            message=f"RPC Endpoint has not been implemented: {method}",
        )
    except TransactionFailed as e:
        first_arg = e.args[0]
        try:
            # sometimes eth-tester wraps an exception in another exception
            raw_error_msg = (
                first_arg if not isinstance(first_arg, Exception) else first_arg.args[0]
            )
            reason = (
                abi.decode(["string"], raw_error_msg[4:])[0]
                if is_bytes(raw_error_msg)
                else raw_error_msg
            )
        except DecodingError:
            reason = first_arg
        raise TransactionFailed(f"execution reverted: {reason}")
    else:
        return _make_response(response, request_id)
