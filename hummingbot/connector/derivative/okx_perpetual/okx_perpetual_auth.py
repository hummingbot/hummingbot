import base64
import hashlib
import hmac
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class OkxPerpetualAuth(AuthBase):
    """
    Auth class required by OKX Perpetual API.

    All private REST requests must contain the following headers:

        - "OK-ACCESS-KEY" -> The API Key as a String.
        - "OK-ACCESS-SIGN" -> The Base64-encoded signature.
        - "OK-ACCESS-TIMESTAMP" -> The UTC timestamp of your request .e.g : 2020-12-08T09:08:57.715Z
        - "OK-ACCESS-PASSPHRASE" -> The passphrase you specified when creating the APIKey.

        Request bodies should have content type application/json and be in valid JSON format.
    """

    def __init__(self, api_key: str, api_secret: str, passphrase: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._passphrase: str = passphrase
        self.time_provider: TimeSynchronizer = time_provider

    def _generate_signature(self, timestamp: str, method: str, path_url: str, body: Optional[str] = None) -> str:
        unsigned_signature = timestamp + method + path_url
        if body is not None:
            unsigned_signature += body

        signature = base64.b64encode(
            hmac.new(
                self._api_secret.encode("utf-8"),
                unsigned_signature.encode("utf-8"),
                hashlib.sha256).digest()).decode()
        return signature

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = datetime.utcfromtimestamp(self.time_provider.time()).isoformat(timespec="milliseconds") + "Z"

        path_url = f"/api{request.url.split('/api')[-1]}"
        if request.params:
            query_string_components = urlencode(request.params)
            query_string_components_with_comma = query_string_components.replace("%2C", ",")
            path_url = f"{path_url}?{query_string_components_with_comma}"

        header = {
            "OK-ACCESS-KEY": self._api_key,
            "OK-ACCESS-SIGN": self._generate_signature(timestamp, request.method.value.upper(), path_url, request.data),
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self._passphrase,
        }

        return header

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        All private REST requests must contain the following headers:

            - OK-ACCESS-KEY The API Key as a String.
            - OK-ACCESS-SIGN The Base64-encoded signature
            - OK-ACCESS-TIMESTAMP The UTC timestamp of your request .e.g : 2020-12-08T09:08:57.715Z
            - OK-ACCESS-PASSPHRASE The passphrase you specified when creating the APIKey.

        Request bodies should have content type application/json and be in valid JSON format.
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        return request

    @staticmethod
    def get_path_from_url(url: str) -> str:
        """
        The requestPath is the path of requesting an endpoint.

            - Example: /api/v5/account/balance

        """
        pattern = re.compile(r'https://www.okx.com')
        return re.sub(pattern, '', url)

    def get_ws_auth_args(self) -> Dict[str, str]:
        """
            - api_key: Unique identification for invoking API. Requires user to apply one manually.
            - passphrase: API Key password
            - timestamp: the Unix Epoch time, the unit is seconds
            - sign: signature string, the signature algorithm is as follows:

        First concatenate timestamp, method, requestPath, strings, then use HMAC SHA256 method to encrypt
        the concatenated string with SecretKey, and then perform Base64 encoding.
        """
        timestamp = int(time.time())
        _access_sign = self.generate_ws_signature_from_payload(timestamp=timestamp,
                                                               method=RESTMethod.GET,
                                                               request_path=CONSTANTS.REST_WS_LOGIN_PATH["ENDPOINT"])
        return [
            {
                "apiKey": self._api_key,
                "passphrase": self._passphrase,
                "timestamp": timestamp,
                "sign": _access_sign
            }
        ]

    def generate_ws_signature_from_payload(self, timestamp: int, method: RESTMethod, request_path: str) -> str:
        message = str(timestamp) + str.upper(method.value) + request_path
        mac = hmac.new(bytes(self._api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        return str(base64.b64encode(d), encoding='utf-8')

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    @staticmethod
    def _get_timestamp() -> str:
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
