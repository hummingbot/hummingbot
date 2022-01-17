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
            payload = urlencode(dict(request.params.items()))
            request.params["signature"] = self.generate_signature_from_payload(payload=payload)
        if request.data is not None:
            payload = urlencode(dict(request.data.items()))
            request.data["signature"] = self.generate_signature_from_payload(payload=payload)

        request.headers = {"X-MBX-APIKEY": self._api_key}

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through
