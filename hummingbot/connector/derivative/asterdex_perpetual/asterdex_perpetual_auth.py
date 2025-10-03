import hmac
import hashlib
import time
from typing import Dict, Any, Optional

from hummingbot.connector.derivative.asterdex_perpetual import asterdex_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class AsterdexPerpetualAuth(AuthBase):
    """
    Auth class required by AsterDex Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str, use_vault: bool):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._use_vault: bool = use_vault

    def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated endpoints
        """
        if request.method == RESTMethod.GET:
            params = request.params or {}
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._generate_signature(params)
            request.params = params
        else:
            data = request.data or {}
            data["timestamp"] = int(time.time() * 1000)
            data["signature"] = self._generate_signature(data)
            request.data = data

        request.headers = request.headers or {}
        request.headers["X-MBX-APIKEY"] = self._api_key

        return request

    def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        AsterDex does not require ws authentication for public streams.
        """
        return request

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generates signature for AsterDex API
        """
        query_string = "&".join([f"{key}={value}" for key, value in sorted(params.items())])
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature
