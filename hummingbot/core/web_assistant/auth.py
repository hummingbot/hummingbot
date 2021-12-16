from abc import ABC, abstractmethod

from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class AuthBase(ABC):
    @abstractmethod
    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        ...

    @abstractmethod
    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        ...
