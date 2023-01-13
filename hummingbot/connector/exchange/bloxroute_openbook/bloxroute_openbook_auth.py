import hashlib
import hmac
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlsplit

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BloxrouteOpenbookAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider: TimeSynchronizer = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        :return: The RESTRequest with auth information included
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. CI-EX does not use this
        functionality
        """
        return request  # pass-through

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = str(int(self.time_provider.time() * 1e3))

        path_url = urlsplit(request.url).path
        if request.params:
            query_string_components = urlencode(request.params)
            path_url = f"{path_url}?{query_string_components}"

        signature = self._generate_signature(timestamp, request.method.value.upper(), path_url, request.data)

        header = {
            "X-CH-APIKEY": self.api_key,
            "X-CH-TS": timestamp,
            "X-CH-SIGN": signature,
        }

        return header

    def _sign(self, payload: str):
        signature = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return signature

    def _generate_signature(self, timestamp: str, method: str, path_url: str, body: Optional[str] = None) -> str:
        unsigned_signature = timestamp + method + path_url
        if body is not None:
            unsigned_signature += body

        return self._sign(payload=unsigned_signature)
