import hashlib
import hmac
import json
from urllib.parse import urlencode

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


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
        secret = bytes(self._api_secret.encode("utf-8"))
        signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        expiry_timestamp = str(int(self._time_provider.time()) + CONSTANTS.ONE_MINUTE)  # expirary recommended to be set to 1 minuete
        request.headers = {"x-phemex-access-token": self._api_key}

        payload = request.url
        payload += urlencode(request.params or {}) if request.method is RESTMethod.GET else ""
        payload += expiry_timestamp
        payload += json.dumps(request.data) if request.method is RESTMethod.POST else ""

        request.headers["x-phemex-request-signature"] = self.generate_signature_from_payload(payload=payload)
        request.headers["x-phemex-request-expiry"] = expiry_timestamp
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through
