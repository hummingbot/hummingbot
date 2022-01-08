from abc import ABC, abstractmethod

from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class AuthBase(ABC):
    """A base class for authentication objects that can be fed to the `WebAssistantsFactory`.

    Hint: If the authentication requires a simple REST request to acquire information from the
    server that is required in the message signature, this class can be passed a `RESTConnection`
    object that it can use to that end.
    """

    @abstractmethod
    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        ...

    @abstractmethod
    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        ...
