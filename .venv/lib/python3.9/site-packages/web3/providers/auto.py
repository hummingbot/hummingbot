import os
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)
from urllib.parse import (
    urlparse,
)

from eth_typing import (
    URI,
)

from web3.exceptions import (
    CannotHandleRequest,
)
from web3.providers import (
    BaseProvider,
    HTTPProvider,
    IPCProvider,
    LegacyWebSocketProvider,
)
from web3.types import (
    RPCEndpoint,
    RPCResponse,
)

HTTP_SCHEMES = {"http", "https"}
WS_SCHEMES = {"ws", "wss"}


def load_provider_from_environment() -> BaseProvider:
    uri_string = URI(os.environ.get("WEB3_PROVIDER_URI", ""))
    if not uri_string:
        return None

    return load_provider_from_uri(uri_string)


def load_provider_from_uri(
    uri_string: URI, headers: Optional[Dict[str, Tuple[str, str]]] = None
) -> BaseProvider:
    uri = urlparse(uri_string)
    if uri.scheme == "file":
        return IPCProvider(uri.path)
    elif uri.scheme in HTTP_SCHEMES:
        return HTTPProvider(uri_string, headers)
    elif uri.scheme in WS_SCHEMES:
        return LegacyWebSocketProvider(uri_string)
    else:
        raise NotImplementedError(
            "Web3 does not know how to connect to scheme "
            f"{uri.scheme!r} in {uri_string!r}"
        )


class AutoProvider(BaseProvider):
    default_providers = (
        load_provider_from_environment,
        IPCProvider,
        HTTPProvider,
        LegacyWebSocketProvider,
    )
    _active_provider = None

    def __init__(
        self,
        potential_providers: Optional[
            Sequence[Union[Callable[..., BaseProvider], Type[BaseProvider]]]
        ] = None,
    ) -> None:
        """
        :param iterable potential_providers: ordered series of provider classes
            to attempt with

        AutoProvider will initialize each potential provider (without arguments),
        in an attempt to find an active node. The list will default to
        :attribute:`default_providers`.
        """
        if potential_providers:
            self._potential_providers = potential_providers
        else:
            self._potential_providers = self.default_providers

    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        try:
            return self._proxy_request(method, params)
        except OSError:
            return self._proxy_request(method, params, use_cache=False)

    def is_connected(self, show_traceback: bool = False) -> bool:
        provider = self._get_active_provider(use_cache=True)
        return provider is not None and provider.is_connected(show_traceback)

    def _proxy_request(
        self, method: RPCEndpoint, params: Any, use_cache: bool = True
    ) -> RPCResponse:
        provider = self._get_active_provider(use_cache)
        if provider is None:
            raise CannotHandleRequest(
                "Could not discover provider while making request: "
                f"method:{method}\nparams:{params}\n"
            )

        return provider.make_request(method, params)

    def _get_active_provider(self, use_cache: bool) -> Optional[BaseProvider]:
        if use_cache and self._active_provider is not None:
            return self._active_provider

        for Provider in self._potential_providers:
            provider = Provider()
            if provider is not None and provider.is_connected():
                self._active_provider = provider
                return provider

        return None
