import base64
import hmac
import re
from datetime import datetime
from typing import Dict

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
        self.timestamp = self._get_timestamp()

    def generate_signature_from_payload(self, method: RESTMethod, request_path: str, body: str) -> str:
        """
        The OK-ACCESS-SIGN header is generated as follows:

            - Create a prehash string of timestamp + method + requestPath + body (where + represents String
            concatenation).
            - Prepare the SecretKey.
            - Sign the prehash string with the SecretKey using the HMAC SHA256.
            - Encode the signature in the Base64 format.
        """
        if body is None:
            body = ''
        message = str(self.timestamp) + str.upper(method.value) + self.get_path_from_url() + body
        mac = hmac.new(bytes(self._api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        return str(base64.b64encode(d), encoding='utf-8')

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        _access_sign = self.generate_signature_from_payload(method=request.method,
                                                            request_path=request.url,
                                                            body=request.data)
        request.headers = self.header_for_authentication(access_sign=_access_sign)

        return request

    @staticmethod
    def get_path_from_url(url: str) -> str:
        pattern = re.compile(r'https://www.okx.com')
        return re.sub(pattern, '', url)

    def header_for_authentication(self, access_sign: str) -> Dict[str, str]:
        return {"OK-ACCESS-KEY": self._api_key,
                "OK-ACCESS-SIGN": access_sign,
                "OK-ACCESS-TIMESTAMP": self.timestamp,
                "OK-ACCESS-PASSPHRASE": self._passphrase}

    def get_ws_auth_args(self, request_path) -> Dict[str, str]:
        _access_sign = self.generate_signature_from_payload(request_path=request_path)
        return [
            {
                "op": "login",
                "args": [
                    {
                        "apiKey": self._api_key,
                        "passphrase": self._passphrase,
                        "timestamp": self.timestamp,
                        "sign": _access_sign
                    }
                ]
            }
        ]

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    @staticmethod
    def _get_timestamp():
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
