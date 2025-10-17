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
        # Accept SecretStr or plain str; never cast SecretStr via str() because it masks the value
        def _unwrap_secret(value):
            if value is None:
                return ""
            # Pydantic SecretStr
            if hasattr(value, "get_secret_value"):
                try:
                    return value.get_secret_value()
                except Exception:
                    pass
            return value

        raw_key = _unwrap_secret(api_key)
        raw_secret = _unwrap_secret(api_secret)

        # Ensure final types are strings
        self._api_key: str = (raw_key if isinstance(raw_key, str) else str(raw_key)).strip()
        self._api_secret: str = (raw_secret if isinstance(raw_secret, str) else str(raw_secret)).strip()
        self._use_vault: bool = use_vault

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Authenticate REST requests.
        - v1 private: timestamp + signature (X-MBX-APIKEY)
        - v3 private: nonce + signature (X-API-KEY)
        """
        if request.params is None:
            request.params = {}
        elif isinstance(request.params, list):
            request.params = {}

        # Determine version by path
        url = request.url or ""
        use_v3 = "/fapi/v3/" in url

        if use_v3:
            # v3 uses nonce and X-API-KEY
            nonce = str(int(time.time() * 1000))
            request.params["nonce"] = nonce
            # Keep v3 fields but also include legacy signature for safety
            query_string = self._build_query_string(request.params)
            signature = hmac.new(self._api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
            request.params["signer"] = signature

            headers = {}
            if request.headers is not None:
                headers.update(request.headers)
            headers["X-API-KEY"] = self._api_key
            request.headers = headers
        else:
            # v1 uses timestamp and X-MBX-APIKEY
            timestamp = str(int(time.time() * 1000))
            request.params["timestamp"] = timestamp
            # Align with working curl by setting a recvWindow
            if "recvWindow" not in request.params:
                request.params["recvWindow"] = 5000
            query_string = self._build_query_string(request.params)
            signature = hmac.new(self._api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
            request.params["signature"] = signature

            headers = {}
            if request.headers is not None:
                headers.update(request.headers)
            headers["X-MBX-APIKEY"] = self._api_key
            request.headers = headers

        return request

    def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        AsterDex does not require ws authentication for public streams.
        """
        return request

    def _build_query_string(self, params: Dict[str, Any]) -> str:
        """
        Build query string from parameters for signature generation
        :param params: dictionary of parameters
        :return: URL-encoded query string
        """
        import urllib.parse
        return urllib.parse.urlencode(params)

    def _time(self) -> float:
        return time.time()
