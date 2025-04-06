from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from eth_abi.codec import (
    ABICodec,
)
from eth_utils.toolz import (
    curry,
    pipe,
)

from web3._utils.filters import (
    AsyncLogFilter,
    LogFilter,
    _UseExistingFilter,
)
from web3.method import (
    Method,
)
from web3.providers.persistent import (
    PersistentConnectionProvider,
)
from web3.types import (
    FormattedEthSubscriptionResponse,
    RPCEndpoint,
    RPCResponse,
)

if TYPE_CHECKING:
    from web3.main import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


@curry
def apply_result_formatters(
    result_formatters: Callable[..., Any], result: RPCResponse
) -> RPCResponse:
    if result_formatters:
        formatted_result = pipe(result, result_formatters)
        return formatted_result
    else:
        return result


TReturn = TypeVar("TReturn")


@curry
def retrieve_request_information_for_batching(
    w3: Union["AsyncWeb3", "Web3"],
    module: "Module",
    method: Method[Callable[..., Any]],
) -> Union[
    Callable[..., Tuple[Tuple[RPCEndpoint, Any], Sequence[Any]]],
    Callable[..., Coroutine[Any, Any, Tuple[Tuple[RPCEndpoint, Any], Sequence[Any]]]],
]:
    async def async_inner(
        *args: Any, **kwargs: Any
    ) -> Tuple[Tuple[RPCEndpoint, Any], Sequence[Any]]:
        (method_str, params), response_formatters = method.process_params(
            module, *args, **kwargs
        )
        if isinstance(w3.provider, PersistentConnectionProvider):
            w3.provider._request_processor.cache_request_information(
                None, cast(RPCEndpoint, method_str), params, response_formatters
            )
        return (cast(RPCEndpoint, method_str), params), response_formatters

    def inner(
        *args: Any, **kwargs: Any
    ) -> Tuple[Tuple[RPCEndpoint, Any], Sequence[Any]]:
        (method_str, params), response_formatters = method.process_params(
            module, *args, **kwargs
        )
        return (cast(RPCEndpoint, method_str), params), response_formatters

    return async_inner if module.is_async else inner


@curry
def retrieve_blocking_method_call_fn(
    w3: "Web3",
    module: "Module",
    method: Method[Callable[..., TReturn]],
) -> Callable[..., Union[TReturn, LogFilter]]:
    def caller(*args: Any, **kwargs: Any) -> Union[TReturn, LogFilter]:
        try:
            (method_str, params), response_formatters = method.process_params(
                module, *args, **kwargs
            )
        except _UseExistingFilter as err:
            return LogFilter(eth_module=module, filter_id=err.filter_id)

        (
            result_formatters,
            error_formatters,
            null_result_formatters,
        ) = response_formatters
        result = w3.manager.request_blocking(
            method_str, params, error_formatters, null_result_formatters
        )
        return apply_result_formatters(result_formatters, result)

    return caller


@curry
def retrieve_async_method_call_fn(
    async_w3: "AsyncWeb3",
    module: "Module",
    method: Method[Callable[..., Any]],
) -> Callable[
    ...,
    Coroutine[
        Any,
        Any,
        Optional[Union[RPCResponse, FormattedEthSubscriptionResponse, AsyncLogFilter]],
    ],
]:
    async def caller(
        *args: Any, **kwargs: Any
    ) -> Union[RPCResponse, FormattedEthSubscriptionResponse, AsyncLogFilter]:
        try:
            (method_str, params), response_formatters = method.process_params(
                module, *args, **kwargs
            )
        except _UseExistingFilter as err:
            return AsyncLogFilter(eth_module=module, filter_id=err.filter_id)

        if isinstance(async_w3.provider, PersistentConnectionProvider):
            return await async_w3.manager.socket_request(
                cast(RPCEndpoint, method_str),
                params,
                response_formatters=response_formatters,
            )
        else:
            (
                result_formatters,
                error_formatters,
                null_result_formatters,
            ) = response_formatters
            result = await async_w3.manager.coro_request(
                method_str, params, error_formatters, null_result_formatters
            )
            return apply_result_formatters(result_formatters, result)

    return caller


#  Module should no longer have access to the full web3 api.
#  Only the calling functions need access to the request methods.
#  Any "re-entrant" shenanigans can go in the middleware, which do
#  have web3 access.
class Module:
    is_async = False

    def __init__(self, w3: Union["AsyncWeb3", "Web3"]) -> None:
        if self.is_async:
            self.retrieve_caller_fn = retrieve_async_method_call_fn(w3, self)
        else:
            self.retrieve_caller_fn = retrieve_blocking_method_call_fn(w3, self)
        self.retrieve_request_information = retrieve_request_information_for_batching(
            w3, self
        )
        self.w3 = w3

    @property
    def codec(self) -> ABICodec:
        # use codec set on the Web3 instance
        return self.w3.codec

    def attach_methods(
        self,
        methods: Dict[str, Method[Callable[..., Any]]],
    ) -> None:
        for method_name, method_class in methods.items():
            klass = (
                method_class.__get__(module=self)()
                if method_class.is_property
                else method_class.__get__(module=self)
            )
            setattr(self, method_name, klass)
