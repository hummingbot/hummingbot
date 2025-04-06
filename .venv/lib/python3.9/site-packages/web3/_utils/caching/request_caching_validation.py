import time
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Sequence,
    TypeVar,
    Union,
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

UNCACHEABLE_BLOCK_IDS = {"finalized", "safe", "latest", "pending"}

ASYNC_PROVIDER_TYPE = TypeVar("ASYNC_PROVIDER_TYPE", bound="AsyncBaseProvider")
SYNC_PROVIDER_TYPE = TypeVar("SYNC_PROVIDER_TYPE", bound="BaseProvider")


def _error_log(
    provider: Union[ASYNC_PROVIDER_TYPE, SYNC_PROVIDER_TYPE], e: Exception
) -> None:
    provider.logger.error(
        "There was an exception while caching the request.", exc_info=e
    )


def always_cache_request(*_args: Any, **_kwargs: Any) -> bool:
    return True


def is_beyond_validation_threshold(
    provider: SYNC_PROVIDER_TYPE,
    blocknum: int = None,
    block_timestamp: int = None,
) -> bool:
    cache_allowed_requests = provider.cache_allowed_requests
    try:
        threshold = provider.request_cache_validation_threshold

        # turn off caching to prevent recursion
        provider.cache_allowed_requests = False
        if isinstance(threshold, RequestCacheValidationThreshold):
            # if mainnet and threshold is "finalized" or "safe"
            threshold_block = provider.make_request(
                RPCEndpoint("eth_getBlockByNumber"), [threshold.value, False]
            )["result"]
            # we should have a `blocknum` to compare against
            return blocknum <= int(threshold_block["number"], 16)
        elif isinstance(threshold, int):
            if not block_timestamp:
                # if validating via `blocknum` from params, we need to get the timestamp
                # for the block with `blocknum`.
                block = provider.make_request(
                    RPCEndpoint("eth_getBlockByNumber"), [hex(blocknum), False]
                )["result"]
                block_timestamp = int(block["timestamp"], 16)

            # if validating via `block_timestamp` from result, we should have a
            # `block_timestamp` to compare against
            return block_timestamp <= time.time() - threshold
        else:
            provider.logger.error(
                "Invalid request_cache_validation_threshold value. This should not "
                f"have happened. Request not cached.\n    threshold: {threshold}"
            )
            return False
    except Exception as e:
        _error_log(provider, e)
        return False
    finally:
        provider.cache_allowed_requests = cache_allowed_requests


def validate_from_block_id_in_params(
    provider: SYNC_PROVIDER_TYPE,
    params: Sequence[Any],
    _result: Dict[str, Any],
) -> bool:
    block_id = params[0]
    if block_id == "earliest":
        # `earliest` should always be cacheable
        return True

    blocknum = int(block_id, 16)
    return is_beyond_validation_threshold(provider, blocknum=blocknum)


def validate_from_blocknum_in_result(
    provider: SYNC_PROVIDER_TYPE,
    _params: Sequence[Any],
    result: Dict[str, Any],
) -> bool:
    cache_allowed_requests = provider.cache_allowed_requests
    try:
        # turn off caching to prevent recursion
        provider.cache_allowed_requests = False

        # transaction results
        if "blockNumber" in result:
            blocknum = result.get("blockNumber")
            # make an extra call to get the block values
            block = provider.make_request(
                RPCEndpoint("eth_getBlockByNumber"), [blocknum, False]
            )["result"]
            return is_beyond_validation_threshold(
                provider,
                blocknum=int(blocknum, 16),
                block_timestamp=int(block["timestamp"], 16),
            )
        elif "number" in result:
            return is_beyond_validation_threshold(
                provider,
                blocknum=int(result["number"], 16),
                block_timestamp=int(result["timestamp"], 16),
            )
        else:
            provider.logger.error(
                "Could not find block number in result. This should not have happened. "
                f"Request not cached.\n    result: {result}",
            )
            return False
    except Exception as e:
        _error_log(provider, e)
        return False
    finally:
        provider.cache_allowed_requests = cache_allowed_requests


def validate_from_blockhash_in_params(
    provider: SYNC_PROVIDER_TYPE,
    params: Sequence[Any],
    _result: Dict[str, Any],
) -> bool:
    cache_allowed_requests = provider.cache_allowed_requests
    try:
        # turn off caching to prevent recursion
        provider.cache_allowed_requests = False

        # make an extra call to get the block number from the hash
        block = provider.make_request(
            RPCEndpoint("eth_getBlockByHash"), [params[0], False]
        )["result"]
        return is_beyond_validation_threshold(
            provider,
            blocknum=int(block["number"], 16),
            block_timestamp=int(block["timestamp"], 16),
        )
    except Exception as e:
        _error_log(provider, e)
        return False
    finally:
        provider.cache_allowed_requests = cache_allowed_requests


# -- async -- #


async def async_is_beyond_validation_threshold(
    provider: ASYNC_PROVIDER_TYPE,
    blocknum: int = None,
    block_timestamp: int = None,
) -> bool:
    cache_allowed_requests = provider.cache_allowed_requests
    try:
        threshold = provider.request_cache_validation_threshold

        # turn off caching to prevent recursion
        provider.cache_allowed_requests = False
        if isinstance(threshold, RequestCacheValidationThreshold):
            # if mainnet and threshold is "finalized" or "safe"
            threshold_block = await provider.make_request(
                RPCEndpoint("eth_getBlockByNumber"), [threshold.value, False]
            )
            # we should have a `blocknum` to compare against
            return blocknum <= int(threshold_block["result"]["number"], 16)
        elif isinstance(threshold, int):
            if not block_timestamp:
                block = await provider.make_request(
                    RPCEndpoint("eth_getBlockByNumber"), [hex(blocknum), False]
                )
                block_timestamp = int(block["result"]["timestamp"], 16)

            # if validating via `block_timestamp` from result, we should have a
            # `block_timestamp` to compare against
            return block_timestamp <= time.time() - threshold
        else:
            provider.logger.error(
                "Invalid request_cache_validation_threshold value. This should not "
                f"have happened. Request not cached.\n    threshold: {threshold}"
            )
            return False
    except Exception as e:
        _error_log(provider, e)
        return False
    finally:
        provider.cache_allowed_requests = cache_allowed_requests


async def async_validate_from_block_id_in_params(
    provider: ASYNC_PROVIDER_TYPE,
    params: Sequence[Any],
    _result: Dict[str, Any],
) -> bool:
    block_id = params[0]
    if block_id == "earliest":
        # `earliest` should always be cacheable
        return True

    blocknum = int(block_id, 16)
    return await async_is_beyond_validation_threshold(provider, blocknum=blocknum)


async def async_validate_from_blocknum_in_result(
    provider: ASYNC_PROVIDER_TYPE,
    _params: Sequence[Any],
    result: Dict[str, Any],
) -> bool:
    cache_allowed_requests = provider.cache_allowed_requests
    try:
        # turn off caching to prevent recursion
        provider.cache_allowed_requests = False

        # transaction results
        if "blockNumber" in result:
            blocknum = result.get("blockNumber")
            # make an extra call to get the block values
            block = await provider.make_request(
                RPCEndpoint("eth_getBlockByNumber"), [blocknum, False]
            )
            return await async_is_beyond_validation_threshold(
                provider,
                blocknum=int(blocknum, 16),
                block_timestamp=int(block["result"]["timestamp"], 16),
            )
        elif "number" in result:
            return await async_is_beyond_validation_threshold(
                provider,
                blocknum=int(result["number"], 16),
                block_timestamp=int(result["timestamp"], 16),
            )
        else:
            provider.logger.error(
                "Could not find block number in result. This should not have happened. "
                f"Request not cached.\n    result: {result}",
            )
            return False
    except Exception as e:
        _error_log(provider, e)
        return False
    finally:
        provider.cache_allowed_requests = cache_allowed_requests


async def async_validate_from_blockhash_in_params(
    provider: ASYNC_PROVIDER_TYPE, params: Sequence[Any], _result: Dict[str, Any]
) -> bool:
    cache_allowed_requests = provider.cache_allowed_requests
    try:
        # turn off caching to prevent recursion
        provider.cache_allowed_requests = False

        # make an extra call to get the block number from the hash
        response = await provider.make_request(
            RPCEndpoint("eth_getBlockByHash"), [params[0], False]
        )
        return await async_is_beyond_validation_threshold(
            provider,
            blocknum=int(response["result"]["number"], 16),
            block_timestamp=int(response["result"]["timestamp"], 16),
        )
    except Exception as e:
        _error_log(provider, e)
        return False
    finally:
        provider.cache_allowed_requests = cache_allowed_requests
