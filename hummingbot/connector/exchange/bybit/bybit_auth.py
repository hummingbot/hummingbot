import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import hummingbot.connector.exchange.bybit.bybit_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BybitAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        return self.add_auth_headers(method=request.method, request=request)

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Bybit does not use this
        functionality
        """
        return request  # pass-through

    def get_referral_code_headers(self):
        """
        Generates referral headers
        :return: a dictionary of auth headers
        """
        headers = {
            "referer": CONSTANTS.HBOT_BROKER_ID
        }
        return headers

    def add_auth_headers(self, method: str, request: Optional[Dict[str, Any]]):
        """
        Add authentication headers in request object

        :param method: HTTP method (POST, PUT, GET)
        :param request: The request to be configured for authenticated interaction

        :return: request object updated with xauth headers
        """
        ts = str(int(time.time() * 10 ** 3))

        headers = {}
        headers["X-BAPI-TIMESTAMP"] = str(ts)
        headers["X-BAPI-API-KEY"] = self.api_key

        signature = self._generate_signature(timestamp=ts, method=method, payload=request.params)

        headers["X-BAPI-SIGN"] = signature
        headers["X-BAPI-SIGN-TYPE"] = str(2)
        headers["X-BAPI-RECV-WINDOW"] = str(CONSTANTS.X_API_RECV_WINDOW)
        headers["Content-Type"] = 'application/json'
        request.headers = {**request.headers, **headers} if request.headers is not None else headers
        return request

    def _generate_signature(self, timestamp, method: str, payload: Optional[Dict[str, Any]]) -> str:
        if payload is None:
            payload = {}

        param_str = str(timestamp) + self.api_key + CONSTANTS.X_API_RECV_WINDOW + urlencode(payload)
        return hmac.new(bytes(self.secret_key, "utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_ws_authentication_message(self):
        """
        Generates the authentication message to start receiving messages from
        the 3 private ws channels
        """
        expires = int((self.time_provider.time() + 10) * 1e3)
        _val = f'GET/realtime{expires}'
        signature = hmac.new(self.secret_key.encode("utf8"),
                             _val.encode("utf8"), hashlib.sha256).hexdigest()
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        return auth_message

    def _time(self):
        return time.time()
