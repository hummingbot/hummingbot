import base64
import hashlib
import hmac
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class OkxAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, passphrase: str, time_provider: TimeSynchronizer):
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.passphrase: str = passphrase
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
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def _generate_signature(self, timestamp: str, method: str, path_url: str, body: Optional[str] = None) -> str:
        unsigned_signature = timestamp + method + path_url
        if body is not None:
            unsigned_signature += body

        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode("utf-8"),
                unsigned_signature.encode("utf-8"),
                hashlib.sha256).digest()).decode()
        return signature

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = datetime.utcfromtimestamp(self.time_provider.time()).isoformat(timespec="milliseconds") + "Z"

        path_url = f"/api{request.url.split('/api')[-1]}"
        if request.params:
            query_string_components = urlencode(request.params)
            path_url = f"{path_url}?{query_string_components}"

        header = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": self._generate_signature(timestamp, request.method.value.upper(), path_url, request.data),
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
        }

        return header

    def websocket_login_parameters(self) -> Dict[str, Any]:
        timestamp = str(int(self.time_provider.time()))

        return {
            "apiKey": self.api_key,
            "passphrase": self.passphrase,
            "timestamp": timestamp,
            "sign": self._generate_signature(timestamp, "GET", "/users/self/verify")
        }
