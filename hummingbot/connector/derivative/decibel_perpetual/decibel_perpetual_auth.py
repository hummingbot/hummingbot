from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


@dataclass
class DecibelPerpetualAuth(AuthBase):
    """Decibel authentication.

    REST: Every endpoint requires headers:
      - Origin: your app origin
      - Authorization: Bearer <token>

    WebSocket: authentication is done at connection time using the
    `Sec-WebSocket-Protocol: decibel, <token>` header (handled by data sources).
    """

    bearer_token: str
    origin: str

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = dict(request.headers or {})
        headers["Origin"] = self.origin
        headers["Authorization"] = f"Bearer {self.bearer_token}"
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # No-op: WS auth is done via the Sec-WebSocket-Protocol header.
        return request

    @property
    def ws_headers(self) -> dict:
        # aiohttp expects a comma-separated list in this header.
        return {"Sec-WebSocket-Protocol": f"decibel, {self.bearer_token}"}
