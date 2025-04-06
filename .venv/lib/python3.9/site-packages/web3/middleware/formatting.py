from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Literal,
    Optional,
    Union,
    cast,
)

from eth_utils.toolz import (
    assoc,
    curry,
    merge,
)

from web3.exceptions import (
    Web3ValueError,
)
from web3.middleware.base import (
    Web3MiddlewareBuilder,
)
from web3.types import (
    EthSubscriptionParams,
    Formatters,
    FormattersDict,
    RPCEndpoint,
    RPCResponse,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.middleware.base import (  # noqa: F401
        Web3Middleware,
    )
    from web3.providers import (  # noqa: F401
        PersistentConnectionProvider,
    )

FORMATTER_DEFAULTS: FormattersDict = {
    "request_formatters": {},
    "result_formatters": {},
    "error_formatters": {},
}


@curry
def _apply_response_formatters(
    method: RPCEndpoint,
    result_formatters: Formatters,
    error_formatters: Formatters,
    response: RPCResponse,
) -> RPCResponse:
    def _format_response(
        response_type: Literal["result", "error", "params"],
        method_response_formatter: Callable[..., Any],
    ) -> RPCResponse:
        appropriate_response = response[response_type]

        if response_type == "params":
            appropriate_response = cast(EthSubscriptionParams, response[response_type])
            return assoc(
                response,
                response_type,
                assoc(
                    response["params"],
                    "result",
                    method_response_formatter(appropriate_response["result"]),
                ),
            )
        else:
            return assoc(
                response, response_type, method_response_formatter(appropriate_response)
            )

    if response.get("result") is not None and method in result_formatters:
        return _format_response("result", result_formatters[method])
    elif (
        # eth_subscription responses
        response.get("params") is not None
        and response["params"].get("result") is not None
        and method in result_formatters
    ):
        return _format_response("params", result_formatters[method])
    elif "error" in response and method in error_formatters:
        return _format_response("error", error_formatters[method])
    else:
        return response


SYNC_FORMATTERS_BUILDER = Callable[["Web3", RPCEndpoint], FormattersDict]
ASYNC_FORMATTERS_BUILDER = Callable[
    ["AsyncWeb3", RPCEndpoint], Coroutine[Any, Any, FormattersDict]
]


class FormattingMiddlewareBuilder(Web3MiddlewareBuilder):
    request_formatters: Formatters = None
    result_formatters: Formatters = None
    error_formatters: Formatters = None
    sync_formatters_builder: SYNC_FORMATTERS_BUILDER = None
    async_formatters_builder: ASYNC_FORMATTERS_BUILDER = None

    @staticmethod
    @curry
    def build(
        w3: Union["AsyncWeb3", "Web3"],
        # formatters option:
        request_formatters: Optional[Formatters] = None,
        result_formatters: Optional[Formatters] = None,
        error_formatters: Optional[Formatters] = None,
        # formatters builder option:
        sync_formatters_builder: Optional[SYNC_FORMATTERS_BUILDER] = None,
        async_formatters_builder: Optional[ASYNC_FORMATTERS_BUILDER] = None,
    ) -> "FormattingMiddlewareBuilder":
        # if not both sync and async formatters are specified, raise error
        if (
            sync_formatters_builder is None and async_formatters_builder is not None
        ) or (sync_formatters_builder is not None and async_formatters_builder is None):
            raise Web3ValueError(
                "Must specify both sync_formatters_builder and async_formatters_builder"
            )

        if sync_formatters_builder is not None and async_formatters_builder is not None:
            if (
                request_formatters is not None
                or result_formatters is not None
                or error_formatters is not None
            ):
                raise Web3ValueError(
                    "Cannot specify formatters_builder and formatters at the same time"
                )

        middleware = FormattingMiddlewareBuilder(w3)
        middleware.request_formatters = request_formatters or {}
        middleware.result_formatters = result_formatters or {}
        middleware.error_formatters = error_formatters or {}
        middleware.sync_formatters_builder = sync_formatters_builder
        middleware.async_formatters_builder = async_formatters_builder
        return middleware

    def request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if self.sync_formatters_builder is not None:
            formatters = merge(
                FORMATTER_DEFAULTS,
                self.sync_formatters_builder(cast("Web3", self._w3), method),
            )
            self.request_formatters = formatters.pop("request_formatters")

        if method in self.request_formatters:
            formatter = self.request_formatters[method]
            params = formatter(params)

        return method, params

    def response_processor(self, method: RPCEndpoint, response: "RPCResponse") -> Any:
        if self.sync_formatters_builder is not None:
            formatters = merge(
                FORMATTER_DEFAULTS,
                self.sync_formatters_builder(cast("Web3", self._w3), method),
            )
            self.result_formatters = formatters["result_formatters"]
            self.error_formatters = formatters["error_formatters"]

        return _apply_response_formatters(
            method,
            self.result_formatters,
            self.error_formatters,
            response,
        )

    # -- async -- #

    async def async_request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if self.async_formatters_builder is not None:
            formatters = merge(
                FORMATTER_DEFAULTS,
                await self.async_formatters_builder(
                    cast("AsyncWeb3", self._w3), method
                ),
            )
            self.request_formatters = formatters.pop("request_formatters")

        if method in self.request_formatters:
            formatter = self.request_formatters[method]
            params = formatter(params)

        return method, params

    async def async_response_processor(
        self, method: RPCEndpoint, response: "RPCResponse"
    ) -> Any:
        if self.async_formatters_builder is not None:
            formatters = merge(
                FORMATTER_DEFAULTS,
                await self.async_formatters_builder(
                    cast("AsyncWeb3", self._w3), method
                ),
            )
            self.result_formatters = formatters["result_formatters"]
            self.error_formatters = formatters["error_formatters"]

        if self._w3.provider.has_persistent_connection:
            # asynchronous response processing
            provider = cast("PersistentConnectionProvider", self._w3.provider)
            provider._request_processor.append_middleware_response_processor(
                response,
                _apply_response_formatters(
                    method,
                    self.result_formatters,
                    self.error_formatters,
                ),
            )
            return response
        else:
            return _apply_response_formatters(
                method,
                self.result_formatters,
                self.error_formatters,
                response,
            )
