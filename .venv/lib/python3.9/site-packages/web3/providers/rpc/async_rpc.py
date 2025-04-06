import asyncio
import logging
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from aiohttp import (
    ClientError,
    ClientSession,
)
from eth_typing import (
    URI,
)
from eth_utils import (
    combomethod,
    to_dict,
)

from web3._utils.empty import (
    Empty,
    empty,
)
from web3._utils.http import (
    construct_user_agent,
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)

from ..._utils.batching import (
    sort_batch_response_by_response_ids,
)
from ..._utils.caching import (
    async_handle_request_caching,
)
from ..._utils.http_session_manager import (
    HTTPSessionManager,
)
from ..async_base import (
    AsyncJSONBaseProvider,
)
from .utils import (
    ExceptionRetryConfiguration,
    check_if_retry_on_failure,
)


class AsyncHTTPProvider(AsyncJSONBaseProvider):
    logger = logging.getLogger("web3.providers.AsyncHTTPProvider")
    endpoint_uri = None
    _request_kwargs = None

    def __init__(
        self,
        endpoint_uri: Optional[Union[URI, str]] = None,
        request_kwargs: Optional[Any] = None,
        exception_retry_configuration: Optional[
            Union[ExceptionRetryConfiguration, Empty]
        ] = empty,
        **kwargs: Any,
    ) -> None:
        self._request_session_manager = HTTPSessionManager()

        if endpoint_uri is None:
            self.endpoint_uri = (
                self._request_session_manager.get_default_http_endpoint()
            )
        else:
            self.endpoint_uri = URI(endpoint_uri)

        self._request_kwargs = request_kwargs or {}
        self._exception_retry_configuration = exception_retry_configuration

        super().__init__(**kwargs)

    async def cache_async_session(self, session: ClientSession) -> ClientSession:
        return await self._request_session_manager.async_cache_and_return_session(
            self.endpoint_uri, session
        )

    def __str__(self) -> str:
        return f"RPC connection {self.endpoint_uri}"

    @property
    def exception_retry_configuration(self) -> ExceptionRetryConfiguration:
        if isinstance(self._exception_retry_configuration, Empty):
            self._exception_retry_configuration = ExceptionRetryConfiguration(
                errors=(ClientError, TimeoutError)
            )
        return self._exception_retry_configuration

    @exception_retry_configuration.setter
    def exception_retry_configuration(
        self, value: Union[ExceptionRetryConfiguration, Empty]
    ) -> None:
        self._exception_retry_configuration = value

    @to_dict
    def get_request_kwargs(self) -> Iterable[Tuple[str, Any]]:
        if "headers" not in self._request_kwargs:
            yield "headers", self.get_request_headers()
        yield from self._request_kwargs.items()

    @combomethod
    def get_request_headers(cls) -> Dict[str, str]:
        if isinstance(cls, AsyncHTTPProvider):
            cls_name = cls.__class__.__name__
        else:
            cls_name = cls.__name__
        module = cls.__module__

        return {
            "Content-Type": "application/json",
            "User-Agent": construct_user_agent(module, cls_name),
        }

    async def _make_request(self, method: RPCEndpoint, request_data: bytes) -> bytes:
        """
        If exception_retry_configuration is set, retry on failure; otherwise, make
        the request without retrying.
        """
        if (
            self.exception_retry_configuration is not None
            and check_if_retry_on_failure(
                method, self.exception_retry_configuration.method_allowlist
            )
        ):
            for i in range(self.exception_retry_configuration.retries):
                try:
                    return await self._request_session_manager.async_make_post_request(
                        self.endpoint_uri, request_data, **self.get_request_kwargs()
                    )
                except tuple(self.exception_retry_configuration.errors):
                    if i < self.exception_retry_configuration.retries - 1:
                        await asyncio.sleep(
                            self.exception_retry_configuration.backoff_factor * 2**i
                        )
                        continue
                    else:
                        raise
            return None
        else:
            return await self._request_session_manager.async_make_post_request(
                self.endpoint_uri, request_data, **self.get_request_kwargs()
            )

    @async_handle_request_caching
    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug(
            f"Making request HTTP. URI: {self.endpoint_uri}, Method: {method}"
        )
        request_data = self.encode_rpc_request(method, params)
        raw_response = await self._make_request(method, request_data)
        response = self.decode_rpc_response(raw_response)
        self.logger.debug(
            f"Getting response HTTP. URI: {self.endpoint_uri}, "
            f"Method: {method}, Response: {response}"
        )
        return response

    async def make_batch_request(
        self, batch_requests: List[Tuple[RPCEndpoint, Any]]
    ) -> Union[List[RPCResponse], RPCResponse]:
        self.logger.debug(f"Making batch request HTTP - uri: `{self.endpoint_uri}`")
        request_data = self.encode_batch_rpc_request(batch_requests)
        raw_response = await self._request_session_manager.async_make_post_request(
            self.endpoint_uri, request_data, **self.get_request_kwargs()
        )
        self.logger.debug("Received batch response HTTP.")
        response = self.decode_rpc_response(raw_response)
        if not isinstance(response, list):
            # RPC errors return only one response with the error object
            return response
        return sort_batch_response_by_response_ids(
            cast(List[RPCResponse], sort_batch_response_by_response_ids(response))
        )

    async def disconnect(self) -> None:
        cache = self._request_session_manager.session_cache
        for _, session in cache.items():
            await session.close()
        cache.clear()

        self.logger.info(f"Successfully disconnected from: {self.endpoint_uri}")
