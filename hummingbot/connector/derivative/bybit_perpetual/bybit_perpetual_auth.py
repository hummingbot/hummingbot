import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BybitPerpetualAuth(AuthBase):
    """
    Auth class required by Bybit Perpetual API
    """
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Authenticates a REST request by adding the necessary headers for the Bybit Perpetual API.

        This method preprocesses the request based on the HTTP method, then adds the required authentication
        headers to the request. The request is then returned with the added headers.

        Args:
            request (RESTRequest): The request to be authenticated.

        Returns:
            RESTRequest: The request with the added authentication headers.

        Raises:
            NotImplementedError: If the HTTP method is not GET or POST.
        """

        if request.method == RESTMethod.GET:
            request = await self._preprocess_auth_get(request)
        elif request.method == RESTMethod.POST:
            request = await self._preprocess_auth_post(request)
        else:
            raise NotImplementedError
        await self._add_auth_headers(request.method, request)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Authenticates a WebSocket request by adding the necessary headers for the Bybit Perpetual API.

        This method passes through the provided WebSocket request without any additional processing.

        Args:
            request (WSRequest): The WebSocket request to be authenticated.

        Returns:
            WSRequest: The WebSocket request, unchanged.
        """

        return request  # pass-through

    async def _add_auth_headers(self, method: str, request: Optional[Dict[str, Any]]):
        """
        Adds the necessary authentication headers to a REST request for the Bybit Perpetual API.

        This method preprocesses the request based on the HTTP method, then adds the required authentication
        headers to the request. The request is then returned with the added headers.

        Args:
            method (str): The HTTP method of the request (GET, POST, etc.).
            request (Optional[Dict[str, Any]]): The request to be authenticated.

        Returns:
            The request with the added authentication headers.

        Raises:
            NotImplementedError: If the HTTP method is not GET or POST.
        """

        # ts = await self._get_server_timestamp()
        ts = self._get_local_timestamp()

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
        the private ws channels
        """
        expires = self._get_expiration_timestamp()
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
        """
        Generate a REST API signature for authentication.

        Args:
            timestamp (int): The timestamp to use in the signature.
            method (RESTMethod): The HTTP method (GET, POST, etc.) to use in the signature.
            payload (Optional[Dict[str, Any]]): The request payload to include in the signature.

        Returns:
            str: The generated signature.
        """

        if payload is None:
            payload = {}
        if method == RESTMethod.GET:
            param_str = str(timestamp) + self.api_key + CONSTANTS.X_API_RECV_WINDOW + urlencode(payload)
        elif method == RESTMethod.POST:
            param_str = str(timestamp) + self.api_key + CONSTANTS.X_API_RECV_WINDOW + str(payload)
            param_str = param_str.replace("'", "\"")
        signature = hmac.new(
            bytes(self.secret_key, "utf-8"),
            param_str.encode("utf-8"),
            digestmod="sha256"
        ).hexdigest()
        return signature

    def _generate_ws_signature(self, expires: int):
        """
        Generates the WebSocket authentication signature for the Bybit Perpetual connector.

        Args:
            expires (int): The expiration timestamp for the authentication message.

        Returns:
            str: The generated WebSocket authentication signature.
        """

        signature = str(hmac.new(
            bytes(self.secret_key, "utf-8"),
            bytes(f"GET/realtime{expires}", "utf-8"),
            digestmod="sha256"
        ).hexdigest())
        return signature

    @staticmethod
    def _get_local_timestamp():
        """
        Returns the current local timestamp in milliseconds.

        Returns:
            str: The current local timestamp in milliseconds.
        """

        return str(int(time.time_ns() * 1e-6))

    @staticmethod
    def _get_expiration_timestamp():
        """
        Generates the expiration timestamp for the Bybit Perpetual WebSocket authentication token.

        Returns:
            int: The expiration timestamp for the WebSocket authentication token, in milliseconds.
        """

        # return str(int(time.time_ns() * 1e-6) + 1000 * 1e3)
        return int((time.time() + CONSTANTS.AUTH_TOKEN_EXPIRATION) * 1000)

    def _time(self):
        return time.time()

    async def _get_server_timestamp(self):
        """
        Retrieves the current server timestamp from the Bybit Perpetual API.

        Returns:
            str: The current server timestamp in milliseconds.
        """

        return str(int(await web_utils.get_current_server_time()))
