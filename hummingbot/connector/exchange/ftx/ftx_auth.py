import hashlib
import hmac
import time
from collections import OrderedDict
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode, urlsplit

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class FtxAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, subaccount_name: Optional[str] = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.subaccount = subaccount_name

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

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = int(self._time() * 1e3)

        path_url = urlsplit(request.url).path
        if request.params:
            query_string_components = urlencode(request.params, safe="/")
            path_url = f"{path_url}?{query_string_components}"

        header = {
            "FTX-KEY": self.api_key,
            "FTX-TS": str(timestamp),
            "FTX-SIGN": self._generate_signature(timestamp, request.method.value.upper(), path_url, request.data),
        }

        if self.subaccount:
            header["FTX-SUBACCOUNT"] = quote(self.subaccount)

        return header

    def websocket_login_parameters(self) -> Dict[str, Any]:
        timestamp = int(self._time() * 1e3)
        signature = self._sign(payload=f"{timestamp}websocket_login")

        payload = {
            "key": self.api_key,
            "sign": signature,
            "time": timestamp,
        }

        if self.subaccount:
            payload["subaccount"] = quote(self.subaccount)

        return payload

    def _sign(self, payload: str):
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256).hexdigest()
        return signature

    def _generate_signature(self, timestamp: int, method: str, path_url: str, body: Optional[str] = None) -> str:
        unsigned_signature = str(timestamp) + method + path_url
        if body is not None:
            unsigned_signature += body

        return self._sign(payload=unsigned_signature)

    def _time(self):
        return time.time()
