from typing import Any, AsyncGenerator, Coroutine, Optional, Protocol, runtime_checkable

from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


@runtime_checkable
class CoinbaseAdvancedTradeExchangePairProtocol(Protocol):
    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        ...

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        ...


@runtime_checkable
class CoinbaseAdvancedTradeWSAssistantProtocol(Protocol):
    async def send(self, request: WSJSONRequest) -> Coroutine[Any, Any, None]:
        ...

    async def connect(self, ws_url, ping_timeout) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        ...

    async def disconnect(self) -> None:
        ...

    async def iter_messages(self) -> AsyncGenerator[Optional[WSResponse], None]:
        ...


# These adapters are used to adapt the CoinbaseAdvancedTradeWSAssistantProtocol to the WSAssistant
# interface. This is done to avoid having to change the WSAssistant and WebAssistantsFactory classes
# to support the CoinbaseAdvancedTradeWSAssistantProtocol.
# TODO: Remove these adapters once the WSAssistant and WebAssistantsFactory classes implement Protocols

class CoinbaseAdvancedTradeWSAssistantAdapter(CoinbaseAdvancedTradeWSAssistantProtocol):
    def __init__(self, ws_assistant: WSAssistant):
        self._ws_assistant = ws_assistant

    # Implement required methods for CoinbaseAdvancedTradeWSAssistantProtocol
    # and delegate the calls to self._ws_assistant
    async def send(self, request: WSJSONRequest) -> Coroutine[Any, Any, None]:
        return await self._ws_assistant.send(request)

    async def connect(self, ws_url, ping_timeout) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        return await self._ws_assistant.connect(ws_url, ping_timeout=ping_timeout)

    async def disconnect(self) -> None:
        await self._ws_assistant.disconnect()

    async def iter_messages(self) -> AsyncGenerator[Optional[WSResponse], None]:  # type: ignore  # PyCharm issue
        async for message in self._ws_assistant.iter_messages():
            yield message


@runtime_checkable
class CoinbaseAdvancedTradeWebAssistantsFactoryProtocol(Protocol):
    async def get_ws_assistant(self) -> CoinbaseAdvancedTradeWSAssistantProtocol:
        ...


class CoinbaseAdvancedTradeWebAssistantsFactoryAdapter(CoinbaseAdvancedTradeWebAssistantsFactoryProtocol):
    def __init__(self, web_assistants_factory: WebAssistantsFactory):
        self._web_assistants_factory = web_assistants_factory

    async def get_ws_assistant(self) -> CoinbaseAdvancedTradeWSAssistantProtocol:
        ws_assistant = await self._web_assistants_factory.get_ws_assistant()
        return CoinbaseAdvancedTradeWSAssistantAdapter(ws_assistant)


@runtime_checkable
class CoinbaseAdvancedTradeAuthProtocol(Protocol):
    pass
