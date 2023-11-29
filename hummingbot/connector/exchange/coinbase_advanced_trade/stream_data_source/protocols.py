from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Protocol, Tuple

from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.enums import StreamAction
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse


class WSAssistantPtl(Protocol):
    """
    Websocket assistant protocol - Ideally this would be associated to the WSAssistant class
    """

    async def connect(
            self,
            ws_url: str,
            *,
            ping_timeout: float,
            message_timeout: float | None = None,
            ws_headers: Dict[str, Any] | None = None,
    ) -> None:
        """Connect to the websocket server."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the websocket server."""
        ...

    async def send(self, request: WSRequest) -> None:
        """Send a message to the websocket server."""
        ...

    async def ping(self) -> None:
        """Send a ping message to the websocket server."""
        ...

    async def receive(self) -> WSResponse | None:
        """Receive a message from the websocket server."""
        ...

    @property
    def last_recv_time(self) -> float:
        """Returns the time of the last received message"""
        return ...

    async def iter_messages(self) -> AsyncGenerator[WSResponse | None, None]:
        """Iterate over the messages received from the websocket server."""
        yield ...


class SubscriptionBuilderT(Protocol):
    """
    SubscriptionBuilderT is the prototype, or type hint for the method
    that builds the subscribe/unsubscribe payload.
    """

    async def __call__(
            self,
            *,
            action: StreamAction,
            channel: str,
            pairs: Tuple[str, ...],
            pair_to_symbol: Callable[[str], Awaitable[str]]) -> Dict[str, Any]:
        ...

    def __await__(
            self,
            *,
            action: StreamAction,
            channel: str,
            pairs: Tuple[str, ...],
            pair_to_symbol: Callable[[str], Awaitable[str]]) -> Dict[str, Any]:
        ...


class WSResponsePtl(Protocol):
    """
    WSResponsePtl is the prototype, or type hint for the websocket response.
    """
    type: str

    @property
    def data(self) -> Any:
        """Returns the data of the response."""
        return ...
