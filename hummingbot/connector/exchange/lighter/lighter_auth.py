import asyncio
import time
from typing import Any

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest, WSRequest


class LighterAuth(AuthBase):
    def __init__(self, signer_client: Any, api_key_index: int):
        self._signer_client = signer_client
        self._api_key_index = api_key_index
        self._auth_token = None
        self._auth_token_expiry_ts = 0
        self._lock = asyncio.Lock()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        auth_token = await self._get_auth_token()
        headers = dict(request.headers or {})
        headers["authorization"] = auth_token
        request.headers = headers

        params = dict(request.params or {})
        params.setdefault("auth", auth_token)
        request.params = params
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        auth_token = await self._get_auth_token()
        if isinstance(request, WSJSONRequest):
            payload = dict(request.payload)
            payload.setdefault("auth", auth_token)
            request.payload = payload
        return request

    async def _get_auth_token(self) -> str:
        now = int(time.time())
        if (
            self._auth_token is not None
            and now < self._auth_token_expiry_ts - CONSTANTS.AUTH_TOKEN_REFRESH_BUFFER_SECONDS
        ):
            return self._auth_token

        async with self._lock:
            now = int(time.time())
            if (
                self._auth_token is not None
                and now < self._auth_token_expiry_ts - CONSTANTS.AUTH_TOKEN_REFRESH_BUFFER_SECONDS
            ):
                return self._auth_token

            auth_token, error = self._signer_client.create_auth_token_with_expiry(
                deadline=CONSTANTS.DEFAULT_AUTH_TOKEN_EXPIRY_SECONDS,
                api_key_index=self._api_key_index,
            )
            if error is not None:
                raise IOError(f"Error creating Lighter auth token: {error}")

            self._auth_token = auth_token
            self._auth_token_expiry_ts = now + CONSTANTS.DEFAULT_AUTH_TOKEN_EXPIRY_SECONDS

        return self._auth_token
