import hashlib
import hmac
from inspect import signature
import json
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode, urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class ScallopAuth(AuthBase):
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
        headers.update(self.get_auth_headers(request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Scallop does not use this
        functionality
        """
        return request  # pass-through

    def get_auth_headers(self, request: RESTRequest) -> Dict[str, str]:
        timestamp = int(self.time_provider.time() * 1e3)
        path = urlparse(request.url).path
        payload = str(timestamp) + request.method.name + path
        if request.method == RESTMethod.GET:
            if request.params:
                query_string = urlencode(request.params)
                payload += '?' + query_string
        elif request.method == RESTMethod.POST:
            if request.params:
                body = json.dumps(request.params)
                payload += body

        return {
            'X-CH-APIKEY': self.api_key,
            'X-CH-SIGN': self._generate_signature(payload),
            'X-CH-TS': str(timestamp),
            'Content-Type': 'application/json',
        }

    def _generate_signature(self, payload) -> str:
        return hmac.new(self.secret_key.encode("utf8"), payload.encode("utf8"), hashlib.sha256).hexdigest()
