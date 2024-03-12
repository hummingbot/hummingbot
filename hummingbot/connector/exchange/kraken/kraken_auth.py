import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class KrakenAuth(AuthBase):
    _last_tracking_nonce: int = 0

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    @classmethod
    def get_tracking_nonce(self) -> str:
        nonce = int(time.time())
        self._last_tracking_nonce = nonce if nonce > self._last_tracking_nonce else self._last_tracking_nonce + 1
        return str(self._last_tracking_nonce)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:

        data = json.loads(request.data) if request.data is not None else {}
        _path = urlparse(request.url).path

        auth_dict: Dict[str, Any] = self._generate_auth_dict(_path, data)
        request.headers = auth_dict["headers"]
        request.data = auth_dict["postDict"]
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Mexc does not use this
        functionality
        """
        return request  # pass-through

    def _generate_auth_dict(self, uri: str, data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generates authentication signature and returns it in a dictionary
        :return: a dictionary of request info including the request signature and post data
        """

        # Decode API private key from base64 format displayed in account management
        api_secret: bytes = base64.b64decode(self.secret_key)

        # Variables (API method, nonce, and POST data)
        api_path: bytes = bytes(uri, 'utf-8')
        api_nonce: str = self.get_tracking_nonce()
        api_post: str = "nonce=" + api_nonce

        if data is not None:
            for key, value in data.items():
                api_post += f"&{key}={value}"

        # Cryptographic hash algorithms
        api_sha256: bytes = hashlib.sha256(bytes(api_nonce + api_post, 'utf-8')).digest()
        api_hmac: hmac.HMAC = hmac.new(api_secret, api_path + api_sha256, hashlib.sha512)

        # Encode signature into base64 format used in API-Sign value
        api_signature: bytes = base64.b64encode(api_hmac.digest())

        return {
            "headers": {
                "API-Key": self.api_key,
                "API-Sign": str(api_signature, 'utf-8')
            },
            "post": api_post,
            "postDict": {"nonce": api_nonce, **data} if data is not None else {"nonce": api_nonce}
        }
