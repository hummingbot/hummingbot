import hashlib
import hmac
from urllib.parse import urlencode, urlsplit

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class PhemexPerpetualAuth(AuthBase):
    """
    Auth class required by Phemex Perpetual API
    https://phemex-docs.github.io/#rest-request-header
    """

    def __init__(self, api_key: str, api_secret: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._time_provider: TimeSynchronizer = time_provider

    def generate_signature_from_payload(self, payload: str) -> str:
        signature = hmac.new(self._api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        expiry_timestamp = str(int(self._time_provider.time()) + CONSTANTS.ONE_MINUTE)  # expirary recommended to be set to 1 minuete
        request.headers = {"x-phemex-access-token": self._api_key}

        payload = urlsplit(request.url).path
        payload += urlencode(request.params) if request.params is not None else ""
        payload += expiry_timestamp
        payload += request.data if request.data is not None else ""

        request.headers["x-phemex-request-signature"] = self.generate_signature_from_payload(payload=payload)
        request.headers["x-phemex-request-expiry"] = expiry_timestamp
        request.headers["Content-Type"] = "application/json"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    def get_ws_auth_payload(self) -> dict:
        expiry_timestamp = int(self._time_provider.time()) + CONSTANTS.ONE_SECOND * 2
        signature = self.generate_signature_from_payload(payload=f"{self._api_key}{expiry_timestamp}")
        return {
            "method": "user.auth",
            "params": [
                "API",
                self._api_key,
                signature,
                expiry_timestamp,
            ],
            "id": 0
        }
