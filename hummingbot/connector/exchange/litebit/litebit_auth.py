import hashlib
import hmac
import json
import urllib
from typing import Any, Dict, Optional
from urllib import parse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class LitebitAuth(AuthBase):
    """
    Auth class required by Litebit Exchange API
    """

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
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(
            self.get_headers(
                request.method,
                urllib.parse.urlsplit(request.url).path,
                request.params,
                json.loads(request.data) if request.data is not None else None
            )
        )
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. LiteBit Exchange does not use this
        functionality
        """
        return request  # pass-through

    def get_headers(self, method: RESTMethod, path: str, params: Optional[dict], body: Optional[dict]) -> Dict[str, any]:
        """
        Generates authentication headers required by Litebit Exchange
        :return: a dictionary of auth headers
        """
        # headers need to be strings
        timestamp = str(int(self.time_provider.time() * 1e3))

        return {
            "Accept": "application/json",
            "LITEBIT-API-KEY": self.api_key,
            "LITEBIT-TIMESTAMP": timestamp,
            "LITEBIT-WINDOW": "60000",
            "LITEBIT-SIGNATURE": self._calculate_signature(timestamp, method, path, params, body),
        }

    def websocket_login_parameters(self) -> Dict[str, Any]:
        timestamp = int(self.time_provider.time() * 1e3)
        signature = self._sign(f"authenticate{timestamp}")

        payload = {
            "api_key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
        }

        return payload

    def _calculate_signature(
        self,
        timestamp: str,
        method: RESTMethod,
        path: str,
        params: Optional[dict],
        body: Optional[dict],
    ) -> str:
        data = ""

        if params:
            data += "?" + parse.urlencode(params)

        if body is not None:
            data += json.dumps(body)

        return self._sign(f"{timestamp}{method.name}{path}{data}")

    def _sign(self, data: str):
        signature = hmac.new(
            self.secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
        )
        return signature.hexdigest()
