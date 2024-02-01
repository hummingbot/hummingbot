import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime
from typing import Dict
from urllib.parse import urlencode

import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_constants as CONSTANTS
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

    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._passphrase: str = passphrase

    @staticmethod
    def pre_hash(timestamp: str, method: str, request_path: str, params: dict) -> str:
        query_string = ''
        if method == 'GET' and bool(params):
            query_string = '?' + urlencode(params)
        if method == 'POST' and bool(params):
            query_string = json.dumps(params)
        return timestamp + method + request_path + query_string

    @staticmethod
    def sign(message, secret_key):
        # Sign the pre-signed string using HMAC-SHA256
        mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), hashlib.sha256)
        d = mac.digest()
        return base64.b64encode(d).decode('utf-8')

    def create_access_sign(self, method, request_path, params):
        timestamp = self._get_timestamp()
        message = self.pre_hash(timestamp, method, request_path, params)
        _access_sign = self.sign(message, self._api_secret)
        return _access_sign, timestamp

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        All private REST requests must contain the following headers:

            - OK-ACCESS-KEY The API Key as a String.
            - OK-ACCESS-SIGN The Base64-encoded signature
            - OK-ACCESS-TIMESTAMP The UTC timestamp of your request .e.g : 2020-12-08T09:08:57.715Z
            - OK-ACCESS-PASSPHRASE The passphrase you specified when creating the APIKey.

        Request bodies should have content type application/json and be in valid JSON format.
        """
        request.headers = {
            "OK-ACCESS-KEY": self._api_key,
            "OK-ACCESS-SIGN": "",
            "OK-ACCESS-TIMESTAMP": "",
            "OK-ACCESS-PASSPHRASE": self._passphrase
        }
        if request.method == RESTMethod.GET:
            request.headers["OK-ACCESS-SIGN"], request.headers["OK-ACCESS-TIMESTAMP"] = self.create_access_sign(
                method=request.method.value,
                request_path=self.get_path_from_url(request.url),
                params=request.params if request.params is not None else {}
            )
        elif request.method == RESTMethod.POST:
            request.headers["OK-ACCESS-SIGN"], request.headers["OK-ACCESS-TIMESTAMP"] = self.create_access_sign(
                method=request.method.value,
                request_path=self.get_path_from_url(request.url),
                params=json.loads(request.data) if request.data is not None else {}
            )
            request.headers["Content-Type"] = "application/json"

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
