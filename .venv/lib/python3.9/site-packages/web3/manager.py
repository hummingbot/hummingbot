import asyncio
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from eth_utils.toolz import (
    pipe,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.batching import (
    RequestBatcher,
)
from web3._utils.caching import (
    generate_cache_key,
)
from web3._utils.compat import (
    Self,
)
from web3._utils.formatters import (
    apply_null_result_formatters,
)
from web3._utils.validation import (
    raise_error_for_batch_response,
    validate_rpc_response_and_raise_if_error,
)
from web3.datastructures import (
    NamedElementOnion,
)
from web3.exceptions import (
    ProviderConnectionError,
    TaskNotRunning,
    Web3TypeError,
)
from web3.method import (
    Method,
)
from web3.middleware import (
    AttributeDictMiddleware,
    BufferedGasEstimateMiddleware,
    ENSNameToAddressMiddleware,
    GasPriceStrategyMiddleware,
    ValidationMiddleware,
)
from web3.middleware.base import (
    Middleware,
    MiddlewareOnion,
)
from web3.module import (
    apply_result_formatters,
)
from web3.providers import (
    AutoProvider,
    JSONBaseProvider,
    PersistentConnectionProvider,
)
from web3.providers.async_base import (
    AsyncJSONBaseProvider,
)
from web3.types import (
    FormattedEthSubscriptionResponse,
    RPCEndpoint,
    RPCRequest,
    RPCResponse,
)

if TYPE_CHECKING:
    from web3.main import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.middleware.base import (  # noqa: F401
        Web3Middleware,
    )
    from web3.providers import (  # noqa: F401
        AsyncBaseProvider,
        BaseProvider,
    )
    from web3.providers.persistent.request_processor import (  # noqa: F401
        RequestProcessor,
    )


NULL_RESPONSES = [None, HexBytes("0x"), "0x"]


class RequestManager:
    logger = logging.getLogger("web3.manager.RequestManager")

    middleware_onion: Union["MiddlewareOnion", NamedElementOnion[None, None]]

    def __init__(
        self,
        w3: Union["AsyncWeb3", "Web3"],
        provider: Optional[Union["BaseProvider", "AsyncBaseProvider"]] = None,
        middleware: Optional[Sequence[Tuple[Middleware, str]]] = None,
    ) -> None:
        self.w3 = w3

        if provider is None:
            self.provider = AutoProvider()
        else:
            self.provider = provider

        if middleware is None:
            middleware = self.get_default_middleware()

        self.middleware_onion = NamedElementOnion(middleware)

        if isinstance(provider, PersistentConnectionProvider):
            # set up the request processor to be able to properly process ordered
            # responses from the persistent connection as FIFO
            provider = cast(PersistentConnectionProvider, self.provider)
            self._request_processor: RequestProcessor = provider._request_processor

    @property
    def provider(self) -> Union["BaseProvider", "AsyncBaseProvider"]:
        return self._provider

    @provider.setter
    def provider(self, provider: Union["BaseProvider", "AsyncBaseProvider"]) -> None:
        self._provider = provider

    @staticmethod
    def get_default_middleware() -> List[Tuple[Middleware, str]]:
        """
        List the default middleware for the request manager.
        Documentation should remain in sync with these defaults.
        """
        return [
            (GasPriceStrategyMiddleware, "gas_price_strategy"),
            (ENSNameToAddressMiddleware, "ens_name_to_address"),
            (AttributeDictMiddleware, "attrdict"),
            (ValidationMiddleware, "validation"),
            (BufferedGasEstimateMiddleware, "gas_estimate"),
        ]

    #
    # Provider requests and response
    #
    def _make_request(
        self, method: Union[RPCEndpoint, Callable[..., RPCEndpoint]], params: Any
    ) -> RPCResponse:
        provider = cast("BaseProvider", self.provider)
        request_func = provider.request_func(
            cast("Web3", self.w3), cast("MiddlewareOnion", self.middleware_onion)
        )
        self.logger.debug(f"Making request. Method: {method}")
        return request_func(method, params)

    async def _coro_make_request(
        self, method: Union[RPCEndpoint, Callable[..., RPCEndpoint]], params: Any
    ) -> RPCResponse:
        provider = cast("AsyncBaseProvider", self.provider)
        request_func = await provider.request_func(
            cast("AsyncWeb3", self.w3), cast("MiddlewareOnion", self.middleware_onion)
        )
        self.logger.debug(f"Making request. Method: {method}")
        return await request_func(method, params)

    #
    # formatted_response parses and validates JSON-RPC responses for expected
    # properties (result or an error) with the expected types.
    #
    # Required properties are not strictly enforced to further determine which
    # exception to raise for specific cases.
    #
    # See also: https://www.jsonrpc.org/specification
    #
    def formatted_response(
        self,
        response: RPCResponse,
        params: Any,
        error_formatters: Optional[Callable[..., Any]] = None,
        null_result_formatters: Optional[Callable[..., Any]] = None,
    ) -> Any:
        is_subscription_response = (
            response.get("method") == "eth_subscription"
            and response.get("params") is not None
            and response["params"].get("subscription") is not None
            and response["params"].get("result") is not None
        )

        validate_rpc_response_and_raise_if_error(
            response,
            error_formatters,
            is_subscription_response=is_subscription_response,
            logger=self.logger,
            params=params,
        )

        # format results
        if "result" in response:
            # Null values for result should apply null_result_formatters
            # Skip when result not present in the response (fallback to False)
            if response.get("result", False) in NULL_RESPONSES:
                apply_null_result_formatters(null_result_formatters, response, params)
            return response.get("result")

        # response from eth_subscription includes response["params"]["result"]
        elif is_subscription_response:
            return {
                "subscription": response["params"]["subscription"],
                "result": response["params"]["result"],
            }

    def request_blocking(
        self,
        method: Union[RPCEndpoint, Callable[..., RPCEndpoint]],
        params: Any,
        error_formatters: Optional[Callable[..., Any]] = None,
        null_result_formatters: Optional[Callable[..., Any]] = None,
    ) -> Any:
        """
        Make a synchronous request using the provider
        """
        response = self._make_request(method, params)
        return self.formatted_response(
            response, params, error_formatters, null_result_formatters
        )

    async def coro_request(
        self,
        method: Union[RPCEndpoint, Callable[..., RPCEndpoint]],
        params: Any,
        error_formatters: Optional[Callable[..., Any]] = None,
        null_result_formatters: Optional[Callable[..., Any]] = None,
    ) -> Any:
        """
        Coroutine for making a request using the provider
        """
        response = await self._coro_make_request(method, params)
        return self.formatted_response(
            response, params, error_formatters, null_result_formatters
        )

    # -- batch requests management -- #

    def _batch_requests(self) -> RequestBatcher[Method[Callable[..., Any]]]:
        """
        Context manager for making batch requests
        """
        if isinstance(self.provider, AutoProvider):
            self.provider = self.provider._get_active_provider(use_cache=True)
        if not isinstance(self.provider, (AsyncJSONBaseProvider, JSONBaseProvider)):
            raise Web3TypeError("Batch requests are not supported by this provider.")
        return RequestBatcher(self.w3)

    def _make_batch_request(
        self, requests_info: List[Tuple[Tuple["RPCEndpoint", Any], Sequence[Any]]]
    ) -> List[RPCResponse]:
        """
        Make a batch request using the provider
        """
        provider = cast(JSONBaseProvider, self.provider)
        request_func = provider.batch_request_func(
            cast("Web3", self.w3), cast("MiddlewareOnion", self.middleware_onion)
        )
        response = request_func(
            [
                (method, params)
                for (method, params), _response_formatters in requests_info
            ]
        )

        if isinstance(response, list):
            # expected format
            formatted_responses = [
                self._format_batched_response(info, cast(RPCResponse, resp))
                for info, resp in zip(requests_info, response)
            ]
            return list(formatted_responses)
        else:
            # expect a single response with an error
            raise_error_for_batch_response(response, self.logger)

    async def _async_make_batch_request(
        self,
        requests_info: List[
            Coroutine[Any, Any, Tuple[Tuple["RPCEndpoint", Any], Sequence[Any]]]
        ],
    ) -> List[RPCResponse]:
        """
        Make an asynchronous batch request using the provider
        """
        provider = cast(AsyncJSONBaseProvider, self.provider)
        request_func = await provider.batch_request_func(
            cast("AsyncWeb3", self.w3),
            cast("MiddlewareOnion", self.middleware_onion),
        )
        # since we add items to the batch without awaiting, we unpack the coroutines
        # and await them all here
        unpacked_requests_info = await asyncio.gather(*requests_info)
        response = await request_func(
            [
                (method, params)
                for (method, params), _response_formatters in unpacked_requests_info
            ]
        )

        if isinstance(response, list):
            # expected format
            response = cast(List[RPCResponse], response)
            if isinstance(self.provider, PersistentConnectionProvider):
                # call _process_response for each response in the batch
                return [
                    cast(RPCResponse, await self._process_response(resp))
                    for resp in response
                ]

            formatted_responses = [
                self._format_batched_response(info, resp)
                for info, resp in zip(unpacked_requests_info, response)
            ]
            return list(formatted_responses)
        else:
            # expect a single response with an error
            raise_error_for_batch_response(response, self.logger)

    def _format_batched_response(
        self,
        requests_info: Tuple[Tuple[RPCEndpoint, Any], Sequence[Any]],
        response: RPCResponse,
    ) -> RPCResponse:
        result_formatters, error_formatters, null_result_formatters = requests_info[1]
        validate_rpc_response_and_raise_if_error(
            response,
            error_formatters,
            is_subscription_response=False,
            logger=self.logger,
            params=requests_info[0][1],
        )
        return apply_result_formatters(
            result_formatters,
            self.formatted_response(
                response,
                requests_info[0][1],
                error_formatters,
                null_result_formatters,
            ),
        )

    # -- persistent connection -- #

    async def socket_request(
        self,
        method: RPCEndpoint,
        params: Any,
        response_formatters: Optional[
            Tuple[Dict[str, Callable[..., Any]], Callable[..., Any], Callable[..., Any]]
        ] = None,
    ) -> RPCResponse:
        provider = cast(PersistentConnectionProvider, self._provider)
        self.logger.debug(
            "Making request to open socket connection and waiting for response: "
            f"{provider.get_endpoint_uri_or_ipc_path()},\n    method: {method},\n"
            f"    params: {params}"
        )
        rpc_request = await self.send(method, params)
        provider._request_processor.cache_request_information(
            rpc_request["id"],
            rpc_request["method"],
            rpc_request["params"],
            response_formatters=response_formatters or ((), (), ()),
        )
        return await self.recv_for_request(rpc_request)

    async def send(self, method: RPCEndpoint, params: Any) -> RPCRequest:
        provider = cast(PersistentConnectionProvider, self._provider)
        async_w3 = cast("AsyncWeb3", self.w3)
        middleware_onion = cast("MiddlewareOnion", self.middleware_onion)
        send_func = await provider.send_func(
            async_w3,
            middleware_onion,
        )
        self.logger.debug(
            "Sending request to open socket connection: "
            f"{provider.get_endpoint_uri_or_ipc_path()},\n    method: {method},\n"
            f"    params: {params}"
        )
        return await send_func(method, params)

    async def recv_for_request(self, rpc_request: RPCRequest) -> RPCResponse:
        provider = cast(PersistentConnectionProvider, self._provider)
        async_w3 = cast("AsyncWeb3", self.w3)
        middleware_onion = cast("MiddlewareOnion", self.middleware_onion)
        recv_func = await provider.recv_func(
            async_w3,
            middleware_onion,
        )
        self.logger.debug(
            "Getting response for request from open socket connection:\n"
            f"    request: {rpc_request}"
        )
        response = await recv_func(rpc_request)
        try:
            return cast(RPCResponse, await self._process_response(response))
        except Exception:
            response_id_key = generate_cache_key(response["id"])
            provider._request_processor._request_information_cache.pop(response_id_key)
            raise

    async def recv(self) -> Union[RPCResponse, FormattedEthSubscriptionResponse]:
        provider = cast(PersistentConnectionProvider, self._provider)
        self.logger.debug(
            "Getting next response from open socket connection: "
            f"{provider.get_endpoint_uri_or_ipc_path()}"
        )
        # pop from the queue since the listener task is responsible for reading
        # directly from the socket
        request_response_cache = self._request_processor._request_response_cache
        _key, response = await request_response_cache.async_await_and_popitem(
            last=False,
            timeout=provider.request_timeout,
        )
        return await self._process_response(response)

    def _persistent_message_stream(self) -> "_AsyncPersistentMessageStream":
        return _AsyncPersistentMessageStream(self)

    async def _get_next_message(self) -> FormattedEthSubscriptionResponse:
        return await self._message_stream().__anext__()

    async def _message_stream(
        self,
    ) -> AsyncGenerator[FormattedEthSubscriptionResponse, None]:
        if not isinstance(self._provider, PersistentConnectionProvider):
            raise Web3TypeError(
                "Only providers that maintain an open, persistent connection "
                "can listen to streams."
            )
        async_w3 = cast("AsyncWeb3", self.w3)

        if self._provider._message_listener_task is None:
            raise ProviderConnectionError(
                "No listener found for persistent connection."
            )

        while True:
            try:
                response = await self._request_processor.pop_raw_response(
                    subscription=True
                )
                # if the subscription was unsubscribed from, we won't have a formatted
                # response because we lost the request information.
                sub_id = response.get(
                    "subscription", response.get("params", {}).get("subscription")
                )
                if async_w3.subscription_manager.get_by_id(sub_id):
                    # if active subscription, process and yield the formatted response
                    formatted_sub_response = cast(
                        FormattedEthSubscriptionResponse,
                        await self._process_response(response),
                    )
                    yield formatted_sub_response
                else:
                    # if not an active sub, skip processing and continue
                    continue
            except TaskNotRunning:
                await asyncio.sleep(0)
                self._provider._handle_listener_task_exceptions()
                self.logger.error(
                    "Message listener background task has stopped unexpectedly. "
                    "Stopping message stream."
                )
                return

    async def _process_response(
        self, response: RPCResponse
    ) -> Union[RPCResponse, FormattedEthSubscriptionResponse]:
        provider = cast(PersistentConnectionProvider, self._provider)
        request_info = self._request_processor.get_request_information_for_response(
            response
        )

        if request_info is None:
            self.logger.debug("No cache key found for response, returning raw response")
            return response
        else:
            if request_info.method == "eth_subscribe" and "result" in response.keys():
                # if response for the initial eth_subscribe request, which returns the
                # subscription id
                subscription_id = response["result"]
                cache_key = generate_cache_key(subscription_id)
                if cache_key not in self._request_processor._request_information_cache:
                    # cache by subscription id in order to process each response for the
                    # subscription as it comes in
                    request_info.subscription_id = subscription_id
                    provider.logger.debug(
                        "Caching eth_subscription info:\n    "
                        f"cache_key={cache_key},\n    "
                        f"request_info={request_info.__dict__}"
                    )
                    self._request_processor._request_information_cache.cache(
                        cache_key, request_info
                    )

            # pipe response back through middleware response processors
            if len(request_info.middleware_response_processors) > 0:
                response = pipe(response, *request_info.middleware_response_processors)

            (
                result_formatters,
                error_formatters,
                null_formatters,
            ) = request_info.response_formatters
            partly_formatted_response = self.formatted_response(
                response,
                request_info.params,
                error_formatters,
                null_formatters,
            )
            return apply_result_formatters(result_formatters, partly_formatted_response)


class _AsyncPersistentMessageStream:
    """
    Async generator for pulling subscription responses from the request processor
    subscription queue. This abstraction is necessary to define the `__aiter__()`
    method required for use with "async for" loops.
    """

    def __init__(self, manager: RequestManager, *args: Any, **kwargs: Any) -> None:
        self.manager = manager
        self.provider: PersistentConnectionProvider = cast(
            PersistentConnectionProvider, manager._provider
        )
        super().__init__(*args, **kwargs)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> FormattedEthSubscriptionResponse:
        return await self.manager._get_next_message()
