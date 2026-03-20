import base64
import hashlib
import hmac
import time
import urllib.parse
from urllib.parse import urlparse

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BithumbAuth(AuthBase):
    """
    Bithumb v1 API authentication.
    Private endpoints require:
      Api-Key   : API key
      Api-Sign  : Base64( HMAC-SHA512( secret, endpoint + chr(0) + query_string + chr(0) + nonce ) )
      Api-Nonce : current timestamp in milliseconds (string)
    Content-Type must be application/x-www-form-urlencoded for POST requests.
    """

    def __init__(self, api_key: str, secret_key: str):
        self._api_key = api_key
        self._secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        nonce = str(int(time.time() * 1000))

        path = urlparse(request.url).path

        data = request.data or {}
        if isinstance(data, dict):
            query_string = urllib.parse.urlencode(sorted(data.items()))
        elif isinstance(data, str):
            query_string = data
        else:
            query_string = ""

        api_sign = self._generate_signature(path, query_string, nonce)

        headers = dict(request.headers or {})
        headers["Api-Key"] = self._api_key
        headers["Api-Sign"] = api_sign
        headers["Api-Nonce"] = nonce
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # Bithumb public WebSocket does not require authentication
        return request

    def _generate_signature(self, endpoint: str, query_string: str, nonce: str) -> str:
        message = endpoint + chr(0) + query_string + chr(0) + nonce
        hmac_sig = hmac.new(
            self._secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()
        return base64.b64encode(hmac_sig.encode("utf-8")).decode("utf-8")
