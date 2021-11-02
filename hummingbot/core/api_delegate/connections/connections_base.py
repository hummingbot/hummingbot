from abc import ABC, abstractmethod
from typing import Optional

from hummingbot.core.api_delegate.data_types import RESTRequest, RESTResponse, WSRequest, WSResponse


class ConnectionsFactoryBase(ABC):
    @abstractmethod
    async def get_rest_connection(self) -> "RESTConnectionBase":
        ...

    @abstractmethod
    async def get_ws_connection(self) -> "WSConnectionBase":
        ...


class RESTConnectionBase(ABC):
    @abstractmethod
    async def call(self, request: RESTRequest) -> RESTResponse:
        ...


class WSConnectionBase(ABC):
    @property
    @abstractmethod
    def last_recv_time(self) -> float:
        ...

    @property
    @abstractmethod
    def connected(self) -> bool:
        ...

    @abstractmethod
    async def connect(
        self,
        ws_url: str,
        ping_timeout: float = 10,
        message_timeout: Optional[float] = None,
    ):
        ...

    @abstractmethod
    async def disconnect(self):
        ...

    @abstractmethod
    async def send(self, request: WSRequest):
        ...

    @abstractmethod
    async def receive(self) -> WSResponse:
        ...
