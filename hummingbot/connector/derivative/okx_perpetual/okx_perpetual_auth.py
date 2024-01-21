import base64
import hashlib
import hmac
from typing import Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class OKXPerpetualAuth(AuthBase):
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
        self._time_provider: TimeSynchronizer = time_provider

    def generate_signature_from_payload(self, method: RESTMethod, request_path: str, body: str) -> str:
        """
        The OK-ACCESS-SIGN header is generated as follows:

            - Create a prehash string of timestamp + method + requestPath + body (where + represents String
            concatenation).
            - Prepare the SecretKey.
            - Sign the prehash string with the SecretKey using the HMAC SHA256.
            - Encode the signature in the Base64 format.
        """
        timestamp = int(self._time_provider.time() * 1e3)
        prehash_string = f"{timestamp}{method.value}{request_path}{body}"
        secret_key_bytes = bytes(self._api_secret, 'utf-8')
        signature = hmac.new(secret_key_bytes, prehash_string.encode('utf-8'), hashlib.sha256).digest()
        ok_access_sign = base64.b64encode(signature).decode('utf-8')
        return ok_access_sign

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        _access_sign = self.generate_signature_from_payload(method=request.method,
                                                            request_path=request.url,
                                                            body=request.data)
        request.headers = self.header_for_authentication(access_sign=_access_sign)

        return request

    def header_for_authentication(self, access_sign: str) -> Dict[str, str]:
        return {"OK-ACCESS-KEY": self._api_key,
                "OK-ACCESS-SIGN": access_sign,
                "OK-ACCESS-TIMESTAMP": self._time_provider.time(),
                "OK-ACCESS-PASSPHRASE": self._passphrase}

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through
