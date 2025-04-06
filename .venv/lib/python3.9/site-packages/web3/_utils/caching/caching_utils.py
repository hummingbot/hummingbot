from asyncio import (
    iscoroutinefunction,
)
import collections
import hashlib
import threading
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Sequence,
    Tuple,
    Union,
)

from eth_typing import (
    ChainId,
)
from eth_utils import (
    is_boolean,
    is_bytes,
    is_dict,
    is_list_like,
    is_null,
    is_number,
    is_text,
    to_bytes,
)

from web3._utils.caching import (
    ASYNC_PROVIDER_TYPE,
    SYNC_PROVIDER_TYPE,
)
from web3._utils.caching.request_caching_validation import (
    UNCACHEABLE_BLOCK_IDS,
    always_cache_request,
    async_validate_from_block_id_in_params,
    async_validate_from_blockhash_in_params,
    async_validate_from_blocknum_in_result,
    validate_from_block_id_in_params,
    validate_from_blockhash_in_params,
    validate_from_blocknum_in_result,
)
from web3._utils.empty import (
    empty,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3.exceptions import (
    Web3TypeError,
)
from web3.types import (
    RPCEndpoint,
)
from web3.utils import (
    RequestCacheValidationThreshold,
)

if TYPE_CHECKING:
    from web3.providers import (  # noqa: F401
        AsyncBaseProvider,
        BaseProvider,
        PersistentConnectionProvider,
    )
    from web3.types import (  # noqa: F401
        AsyncMakeRequestFn,
        MakeRequestFn,
        RPCRequest,
        RPCResponse,
    )


def generate_cache_key(value: Any) -> str:
    """
    Generates a cache key for the *args and **kwargs
    """
    if is_bytes(value):
        return hashlib.md5(value).hexdigest()
    elif is_text(value):
        return generate_cache_key(to_bytes(text=value))
    elif is_boolean(value) or is_null(value) or is_number(value):
        return generate_cache_key(repr(value))
    elif is_dict(value):
        return generate_cache_key((key, value[key]) for key in sorted(value.keys()))
    elif is_list_like(value) or isinstance(value, collections.abc.Generator):
        return generate_cache_key("".join(generate_cache_key(item) for item in value))
    else:
        raise Web3TypeError(
            f"Cannot generate cache key for value {value} of type {type(value)}"
        )


class RequestInformation:
    def __init__(
        self,
        method: RPCEndpoint,
        params: Any,
        response_formatters: Tuple[
            Union[Dict[str, Callable[..., Any]], Callable[..., Any]],
            Callable[..., Any],
            Callable[..., Any],
        ],
        subscription_id: str = None,
    ):
        self.method = method
        self.params = params
        self.response_formatters = response_formatters
        self.subscription_id = subscription_id
        self.middleware_response_processors: List[Callable[..., Any]] = []


DEFAULT_VALIDATION_THRESHOLD = 60 * 60  # 1 hour

CHAIN_VALIDATION_THRESHOLD_DEFAULTS: Dict[
    int, Union[RequestCacheValidationThreshold, int]
] = {
    # Suggested safe values as defaults for each chain. Users can configure a different
    # value if desired.
    ChainId.ETH.value: RequestCacheValidationThreshold.FINALIZED,
    ChainId.ARB1.value: 7 * 24 * 60 * 60,  # 7 days
    ChainId.ZKSYNC.value: 60 * 60,  # 1 hour
    ChainId.OETH.value: 3 * 60,  # 3 minutes
    ChainId.MATIC.value: 30 * 60,  # 30 minutes
    ChainId.ZKEVM.value: 60 * 60,  # 1 hour
    ChainId.BASE.value: 7 * 24 * 60 * 60,  # 7 days
    ChainId.SCR.value: 60 * 60,  # 1 hour
    ChainId.GNO.value: 5 * 60,  # 5 minutes
    ChainId.AVAX.value: 2 * 60,  # 2 minutes
    ChainId.BNB.value: 2 * 60,  # 2 minutes
    ChainId.FTM.value: 60,  # 1 minute
}


def is_cacheable_request(
    provider: Union[ASYNC_PROVIDER_TYPE, SYNC_PROVIDER_TYPE],
    method: RPCEndpoint,
    params: Any,
) -> bool:
    if not (provider.cache_allowed_requests and method in provider.cacheable_requests):
        return False
    elif method in BLOCKNUM_IN_PARAMS:
        block_id = params[0]
        if block_id in UNCACHEABLE_BLOCK_IDS:
            return False
    return True


# -- request caching -- #

ALWAYS_CACHE = {
    RPC.eth_chainId,
    RPC.web3_clientVersion,
    RPC.net_version,
}
BLOCKNUM_IN_PARAMS = {
    RPC.eth_getBlockByNumber,
    RPC.eth_getRawTransactionByBlockNumberAndIndex,
    RPC.eth_getBlockTransactionCountByNumber,
    RPC.eth_getUncleByBlockNumberAndIndex,
    RPC.eth_getUncleCountByBlockNumber,
}
BLOCK_IN_RESULT = {
    RPC.eth_getBlockByHash,
    RPC.eth_getTransactionByHash,
    RPC.eth_getTransactionByBlockNumberAndIndex,
    RPC.eth_getTransactionByBlockHashAndIndex,
    RPC.eth_getBlockTransactionCountByHash,
}
BLOCKHASH_IN_PARAMS = {
    RPC.eth_getRawTransactionByBlockHashAndIndex,
    RPC.eth_getUncleByBlockHashAndIndex,
    RPC.eth_getUncleCountByBlockHash,
}

INTERNAL_VALIDATION_MAP: Dict[
    RPCEndpoint,
    Callable[
        [SYNC_PROVIDER_TYPE, Sequence[Any], Dict[str, Any]],
        bool,
    ],
] = {
    **{endpoint: always_cache_request for endpoint in ALWAYS_CACHE},
    **{endpoint: validate_from_block_id_in_params for endpoint in BLOCKNUM_IN_PARAMS},
    **{endpoint: validate_from_blocknum_in_result for endpoint in BLOCK_IN_RESULT},
    **{endpoint: validate_from_blockhash_in_params for endpoint in BLOCKHASH_IN_PARAMS},
}
CACHEABLE_REQUESTS = tuple(INTERNAL_VALIDATION_MAP.keys())


def set_threshold_if_empty(provider: SYNC_PROVIDER_TYPE) -> None:
    current_threshold = provider.request_cache_validation_threshold

    if current_threshold is empty or isinstance(
        current_threshold, RequestCacheValidationThreshold
    ):
        cache_allowed_requests = provider.cache_allowed_requests
        try:
            # turn off momentarily to avoid recursion
            provider.cache_allowed_requests = False
            chain_id_result = provider.make_request(RPCEndpoint("eth_chainId"), [])[
                "result"
            ]
            chain_id = int(chain_id_result, 16)

            if current_threshold is empty:
                provider.request_cache_validation_threshold = (
                    CHAIN_VALIDATION_THRESHOLD_DEFAULTS.get(
                        chain_id, DEFAULT_VALIDATION_THRESHOLD
                    )
                )
        except Exception:
            provider.request_cache_validation_threshold = DEFAULT_VALIDATION_THRESHOLD
        finally:
            provider.cache_allowed_requests = cache_allowed_requests


def _should_cache_response(
    provider: SYNC_PROVIDER_TYPE,
    method: RPCEndpoint,
    params: Sequence[Any],
    response: "RPCResponse",
) -> bool:
    result = response.get("result", None)
    if "error" in response or is_null(result):
        return False

    set_threshold_if_empty(provider)
    if (
        method in INTERNAL_VALIDATION_MAP
        and provider.request_cache_validation_threshold is not None
    ):
        return INTERNAL_VALIDATION_MAP[method](provider, params, result)
    return True


def handle_request_caching(
    func: Callable[[SYNC_PROVIDER_TYPE, RPCEndpoint, Any], "RPCResponse"]
) -> Callable[..., "RPCResponse"]:
    def wrapper(
        provider: SYNC_PROVIDER_TYPE, method: RPCEndpoint, params: Any
    ) -> "RPCResponse":
        if is_cacheable_request(provider, method, params):
            request_cache = provider._request_cache
            cache_key = generate_cache_key(
                f"{threading.get_ident()}:{(method, params)}"
            )
            cache_result = request_cache.get_cache_entry(cache_key)
            if cache_result is not None:
                return cache_result
            else:
                response = func(provider, method, params)
                if _should_cache_response(provider, method, params, response):
                    with provider._request_cache_lock:
                        request_cache.cache(cache_key, response)
                return response
        else:
            return func(provider, method, params)

    # save a reference to the decorator on the wrapped function
    wrapper._decorator = handle_request_caching  # type: ignore
    return wrapper


# -- async -- #

ASYNC_VALIDATOR_TYPE = Callable[
    ["AsyncBaseProvider", Sequence[Any], Dict[str, Any]],
    Union[bool, Coroutine[Any, Any, bool]],
]

ASYNC_INTERNAL_VALIDATION_MAP: Dict[RPCEndpoint, ASYNC_VALIDATOR_TYPE] = {
    **{endpoint: always_cache_request for endpoint in ALWAYS_CACHE},
    **{
        endpoint: async_validate_from_block_id_in_params
        for endpoint in BLOCKNUM_IN_PARAMS
    },
    **{
        endpoint: async_validate_from_blocknum_in_result for endpoint in BLOCK_IN_RESULT
    },
    **{
        endpoint: async_validate_from_blockhash_in_params
        for endpoint in BLOCKHASH_IN_PARAMS
    },
}


async def async_set_threshold_if_empty(provider: ASYNC_PROVIDER_TYPE) -> None:
    current_threshold = provider.request_cache_validation_threshold

    if current_threshold is empty or isinstance(
        current_threshold, RequestCacheValidationThreshold
    ):
        cache_allowed_requests = provider.cache_allowed_requests
        try:
            # turn off momentarily to avoid recursion
            provider.cache_allowed_requests = False
            chain_id_result = await provider.make_request(
                RPCEndpoint("eth_chainId"), []
            )
            chain_id = int(chain_id_result["result"], 16)

            if current_threshold is empty:
                provider.request_cache_validation_threshold = (
                    CHAIN_VALIDATION_THRESHOLD_DEFAULTS.get(
                        chain_id, DEFAULT_VALIDATION_THRESHOLD
                    )
                )
        except Exception:
            provider.request_cache_validation_threshold = DEFAULT_VALIDATION_THRESHOLD
        finally:
            provider.cache_allowed_requests = cache_allowed_requests


async def _async_should_cache_response(
    provider: ASYNC_PROVIDER_TYPE,
    method: RPCEndpoint,
    params: Sequence[Any],
    response: "RPCResponse",
) -> bool:
    result = response.get("result", None)
    if "error" in response or is_null(result):
        return False

    await async_set_threshold_if_empty(provider)
    if (
        method in ASYNC_INTERNAL_VALIDATION_MAP
        and provider.request_cache_validation_threshold is not None
    ):
        cache_validator = ASYNC_INTERNAL_VALIDATION_MAP[method]
        return (
            await cache_validator(provider, params, result)
            if iscoroutinefunction(cache_validator)
            else cache_validator(provider, params, result)
        )
    return True


def async_handle_request_caching(
    func: Callable[
        [ASYNC_PROVIDER_TYPE, RPCEndpoint, Any], Coroutine[Any, Any, "RPCResponse"]
    ],
) -> Callable[..., Coroutine[Any, Any, "RPCResponse"]]:
    async def wrapper(
        provider: ASYNC_PROVIDER_TYPE, method: RPCEndpoint, params: Any
    ) -> "RPCResponse":
        if is_cacheable_request(provider, method, params):
            request_cache = provider._request_cache
            cache_key = generate_cache_key(
                f"{threading.get_ident()}:{(method, params)}"
            )
            cache_result = request_cache.get_cache_entry(cache_key)
            if cache_result is not None:
                return cache_result
            else:
                response = await func(provider, method, params)
                if await _async_should_cache_response(
                    provider, method, params, response
                ):
                    async with provider._request_cache_lock:
                        request_cache.cache(cache_key, response)
                return response
        else:
            return await func(provider, method, params)

    # save a reference to the decorator on the wrapped function
    wrapper._decorator = async_handle_request_caching  # type: ignore
    return wrapper


def async_handle_send_caching(
    func: Callable[
        [ASYNC_PROVIDER_TYPE, RPCEndpoint, Any],
        Coroutine[Any, Any, "RPCRequest"],
    ],
) -> Callable[..., Coroutine[Any, Any, "RPCRequest"]]:
    async def wrapper(
        provider: ASYNC_PROVIDER_TYPE, method: RPCEndpoint, params: Any
    ) -> "RPCRequest":
        if is_cacheable_request(provider, method, params):
            request_cache = provider._request_cache
            cache_key = generate_cache_key(
                f"{threading.get_ident()}:{(method, params)}"
            )
            cached_response = request_cache.get_cache_entry(cache_key)
            if cached_response is not None:
                # The request data isn't used, this just prevents a cached request from
                # being sent - return an empty request object
                return {"id": -1, "method": RPCEndpoint(""), "params": []}
        return await func(provider, method, params)

    # save a reference to the decorator on the wrapped function
    wrapper._decorator = async_handle_send_caching  # type: ignore
    return wrapper


def async_handle_recv_caching(
    func: Callable[
        ["PersistentConnectionProvider", "RPCRequest"],
        Coroutine[Any, Any, "RPCResponse"],
    ]
) -> Callable[..., Coroutine[Any, Any, "RPCResponse"]]:
    async def wrapper(
        provider: "PersistentConnectionProvider",
        rpc_request: "RPCRequest",
    ) -> "RPCResponse":
        method = rpc_request["method"]
        params = rpc_request["params"]
        if is_cacheable_request(provider, method, params):
            request_cache = provider._request_cache
            cache_key = generate_cache_key(
                f"{threading.get_ident()}:{(method, params)}"
            )
            cache_result = request_cache.get_cache_entry(cache_key)
            if cache_result is not None:
                return cache_result
            else:
                response = await func(provider, rpc_request)
                if await _async_should_cache_response(
                    provider, method, params, response
                ):
                    async with provider._request_cache_lock:
                        request_cache.cache(cache_key, response)
                return response
        else:
            return await func(provider, rpc_request)

    # save a reference to the decorator on the wrapped function
    wrapper._decorator = async_handle_recv_caching  # type: ignore
    return wrapper
