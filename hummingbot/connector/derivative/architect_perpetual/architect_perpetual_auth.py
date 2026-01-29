from typing import Any, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class ArchitectPerpetualAuth(AuthBase):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        paper_trading: bool = False
    ):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._paper_trading: bool = paper_trading
        self._architect_client: Optional[Any] = None

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def api_secret(self) -> str:
        return self._api_secret

    @property
    def paper_trading(self) -> bool:
        return self._paper_trading

    async def get_architect_client(self):
        if self._architect_client is None:
            from architect_py import AsyncClient
            endpoint = CONSTANTS.TESTNET_ENDPOINT if self._paper_trading else CONSTANTS.PERPETUAL_ENDPOINT
            self._architect_client = await AsyncClient.connect(
                api_key=self._api_key,
                api_secret=self._api_secret,
                paper_trading=self._paper_trading,
                endpoint=endpoint,
            )
        return self._architect_client

    async def close_client(self):
        if self._architect_client is not None:
            await self._architect_client.close()
            self._architect_client = None

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
