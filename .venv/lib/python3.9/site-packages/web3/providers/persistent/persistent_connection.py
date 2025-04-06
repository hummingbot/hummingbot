from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Union,
    cast,
)

from web3.types import (
    FormattedEthSubscriptionResponse,
    RPCEndpoint,
    RPCResponse,
)

if TYPE_CHECKING:
    from web3.main import (  # noqa: F401
        AsyncWeb3,
    )
    from web3.manager import (  # noqa: F401
        _AsyncPersistentMessageStream,
    )
    from web3.providers.persistent import (  # noqa: F401
        PersistentConnectionProvider,
    )


class PersistentConnection:
    """
    A class that houses the public API for interacting with the persistent connection
    via a `AsyncWeb3` instance instantiated with a `PersistentConnectionProvider` class.
    """

    def __init__(self, w3: "AsyncWeb3"):
        self._manager = w3.manager
        self.provider = cast("PersistentConnectionProvider", self._manager.provider)

    @property
    def subscriptions(self) -> Dict[str, Any]:
        """
        Return the active subscriptions on the persistent connection.

        :return: The active subscriptions on the persistent connection.
        :rtype: Dict[str, Any]
        """
        return self._manager._request_processor.active_subscriptions

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        """
        Make a request to the persistent connection and return the response. This method
        does not process the response as it would when invoking a method via the
        appropriate module on the `AsyncWeb3` instance,
        e.g. `w3.eth.get_block("latest")`.

        :param method: The RPC method, e.g. `eth_getBlockByNumber`.
        :param params: The RPC method parameters, e.g. `["0x1337", False]`.

        :return: The unprocessed response from the persistent connection.
        :rtype: RPCResponse
        """
        return await self.provider.make_request(method, params)

    async def send(self, method: RPCEndpoint, params: Any) -> None:
        """
        Send a raw, unprocessed message to the persistent connection.

        :param method: The RPC method, e.g. `eth_getBlockByNumber`.
        :param params: The RPC method parameters, e.g. `["0x1337", False]`.

        :return: None
        """
        await self._manager.send(method, params)

    async def recv(self) -> Union[RPCResponse, FormattedEthSubscriptionResponse]:
        """
        Receive the next unprocessed response for a request from the persistent
        connection.

        :return: The next unprocessed response for a request from the persistent
                 connection.
        :rtype: Union[RPCResponse, FormattedEthSubscriptionResponse]
        """
        return await self._manager.recv()

    def process_subscriptions(self) -> "_AsyncPersistentMessageStream":
        """
        Asynchronous iterator that yields messages from the subscription message stream.

        :return: The subscription message stream.
        :rtype: _AsyncPersistentMessageStream
        """
        return self._manager._persistent_message_stream()
