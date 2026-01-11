from typing import Any, Dict, Optional

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class ArchitectPerpetualAuth(AuthBase):

    def __init__(self, api_key: str, api_secret: str, time_provider: Optional[TimeSynchronizer] = None):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._time_provider: Optional[TimeSynchronizer] = time_provider
        self._jwt_token: Optional[str] = None
        self._jwt_expiry: Optional[float] = None

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def api_secret(self) -> str:
        return self._api_secret

    def get_credentials(self) -> Dict[str, str]:
        return {"api_key": self._api_key, "api_secret": self._api_secret}

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = request.headers or {}
        if self._jwt_token:
            headers["Authorization"] = f"Bearer {self._jwt_token}"
        else:
            headers["X-API-Key"] = self._api_key
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def set_jwt_token(self, token: str, expiry: float) -> None:
        self._jwt_token = token
        self._jwt_expiry = expiry

    def is_token_valid(self) -> bool:
        if not self._jwt_token or not self._jwt_expiry:
            return False
        current_time = self._time_provider.time() if self._time_provider else 0
        return current_time < (self._jwt_expiry - 60)

    def clear_token(self) -> None:
        self._jwt_token = None
        self._jwt_expiry = None
