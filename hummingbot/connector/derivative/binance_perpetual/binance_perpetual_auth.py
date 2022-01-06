import hashlib
import hmac
from typing import Optional

from urllib.parse import urlencode

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BinancePerpetualAuth(AuthBase):
    """
    Auth class required by Binance Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret

    def generate_signature_from_payload(self, payload: str) -> str:
        secret = bytes(self._api_secret.encode("utf-8"))
        signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        payload: Optional[str] = None
        if request.params is not None:
            payload = urlencode(sorted(request.params.items()))
        if request.data is not None:
            payload = urlencode(sorted(request.data.items()))

        if payload is not None:
            signature = self.generate_signature_from_payload(payload=payload)
            request.url = f"{request.url}?{payload}&signature={signature}"

        request.params = None
        request.data = None

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through
