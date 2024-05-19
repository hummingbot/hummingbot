import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BybitPerpetualAuth(AuthBase):
    """
    Auth class required by Bybit Perpetual API
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.GET:
            request = await self._preprocess_auth_get(request)
        elif request.method == RESTMethod.POST:
            request = await self._preprocess_auth_post(request)
        else:
            raise NotImplementedError
        self._add_auth_headers(request.method, request)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through

    def _add_auth_headers(self, method: str, request: Optional[Dict[str, Any]]):
        """
        Add authentication headers in request object

        :param method: HTTP method (POST, PUT, GET)
        :param request: The request to be configured for authenticated interaction

        :return: request object updated with xauth headers
        """
        ts = str(int(time.time() * 1e3))

        headers = {}
        headers["X-BAPI-TIMESTAMP"] = str(ts)
        headers["X-BAPI-API-KEY"] = self.api_key

        if method == RESTMethod.POST:
            payload = request.data
        else:
            payload = request.params

        signature = self._generate_rest_signature(
            timestamp=ts, method=method, payload=payload)

        headers["X-BAPI-SIGN"] = signature
        headers["X-BAPI-SIGN-TYPE"] = str(2)  # TODO: Add to constants
        headers["X-BAPI-RECV-WINDOW"] = str(CONSTANTS.X_API_RECV_WINDOW)
        request.headers = {**request.headers, **headers} if \
            request.headers is not None else headers
        return request

    def generate_ws_auth_message(self):
        """
        Generates the authentication message to start receiving messages from
        the 3 private ws channels
        """
        # Generate expires.
        # expires = int((self.time_provider.time() + 10) * 1e3)
        expires = int((self._time() + 10000) * 1000)
        # expires = self._get_expiration_timestamp()
        signature = self._generate_ws_signature(expires)
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        return auth_message

    async def _preprocess_auth_get(self, request: RESTRequest) -> RESTRequest:
        return request

    async def _preprocess_auth_post(self, request: RESTRequest) -> RESTRequest:
        return request

    def _generate_rest_signature(self, timestamp, method: RESTMethod,
                                 payload: Optional[Dict[str, Any]]) -> str:
        if payload is None:
            payload = {}
        if method == RESTMethod.GET:
            param_str = str(timestamp) + self.api_key + CONSTANTS.X_API_RECV_WINDOW + urlencode(payload)
        elif method == RESTMethod.POST:
            param_str = str(timestamp) + self.api_key + CONSTANTS.X_API_RECV_WINDOW + payload
            param_str = param_str.replace("'", "\"")
        signature = hmac.new(
            bytes(self.secret_key, "utf-8"),
            param_str.encode("utf-8"),
            digestmod="sha256"
        ).hexdigest()
        return signature

    def _generate_ws_signature(self, expires: int):
        signature = str(hmac.new(
            bytes(self.secret_key, "utf-8"),
            bytes(f"GET/realtime{expires}", "utf-8"),
            digestmod="sha256"
        ).hexdigest())
        return signature

    @staticmethod
    def _get_timestamp():
        return str(int(time.time() * 1e3))

    @staticmethod
    def _get_expiration_timestamp():
        return str(int((round(time.time()) + 5) * 1e3))

    def _time(self):
        return time.time()
