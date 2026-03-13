import base64
import hmac
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BitgetPerpetualAuth(AuthBase):
    """
    Auth class required by Bitget Perpetual API
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        passphrase: str,
        time_provider: TimeSynchronizer
    ) -> None:
        self._api_key: str = api_key
        self._secret_key: str = secret_key
        self._passphrase: str = passphrase
        self._time_provider: TimeSynchronizer = time_provider

    @staticmethod
    def _union_params(timestamp: str, method: str, request_path: str, body: str) -> str:
        if body in ["None", "null"]:
            body = ""

        return str(timestamp) + method.upper() + request_path + body

    def _generate_signature(self, request_params: str) -> str:
        digest: bytes = hmac.new(
            bytes(self._secret_key, encoding="utf8"),
            bytes(request_params, encoding="utf-8"),
            digestmod="sha256"
        ).digest()
        signature = base64.b64encode(digest).decode().strip()

        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {
            "Content-Type": "application/json",
            "ACCESS-KEY": self._api_key,
            "ACCESS-TIMESTAMP": str(int(self._time_provider.time() * 1e3)),
            "ACCESS-PASSPHRASE": self._passphrase,
        }
        path = request.throttler_limit_id
        payload = str(request.data)

        if request.method is RESTMethod.GET and request.params:
            string_params = {str(k): v for k, v in request.params.items()}
            path += "?" + urlencode(string_params)

        headers["ACCESS-SIGN"] = self._generate_signature(
            self._union_params(headers["ACCESS-TIMESTAMP"], request.method.value, path, payload)
        )
        request.headers.update(headers)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Generates a dictionary with all required information for the authentication process

        :return: a dictionary of authentication info including the request signature
        """
        timestamp: str = str(int(self._time_provider.time()))
        signature: str = self._generate_signature(
            self._union_params(timestamp, "GET", "/user/verify", "")
        )

        return {
            "apiKey": self._api_key,
            "passphrase": self._passphrase,
            "timestamp": timestamp,
            "sign": signature
        }
