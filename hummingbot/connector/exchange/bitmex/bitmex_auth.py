import hashlib
import hmac
import json
import time
from urllib.parse import urlencode, urlparse

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

EXPIRATION = 25  # seconds


class BitmexAuth(AuthBase):
    """
    Auth class required by Bitmex API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret

    @property
    def api_key(self):
        return self._api_key

    def generate_signature_from_payload(self, payload: str) -> str:
        secret = bytes(self._api_secret.encode("utf-8"))
        signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        verb = str(request.method)
        expires = str(int(time.time()) + EXPIRATION)
        data = json.dumps(request.data) if request.data is not None else ''
        parsed_url = urlparse(request.url)
        path = parsed_url.path
        query = urlencode(request.params) if request.params is not None else ''
        if not (query == ''):
            query = '?' + query
        payload = verb + path + query + expires + data
        signature = self.generate_signature_from_payload(payload)

        request.headers = {
            "api-expires": expires,
            "api-key": self._api_key,
            "api-signature": signature,
        }

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    async def generate_ws_signature(self, ts: str):
        payload = 'GET/realtime' + ts
        signature = self.generate_signature_from_payload(payload)
        return signature
