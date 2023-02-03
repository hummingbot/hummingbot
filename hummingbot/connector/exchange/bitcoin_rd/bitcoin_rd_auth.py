import hashlib
import hmac
import json
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode
import time

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BitcoinRDAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params(params=json.loads(request.data))
        else:
            request.params = self.add_auth_to_params(params=request.params)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. BitcoinRD does not use this
        functionality
        """
        return request  # pass-through

    def get_api_expires():
        return str(int(time.time() + 60))

    def generate_signature(self):
        method, path, api_expires = self.init_signature()
        string_to_encode = method + path + api_expires
        signature = hmac.new(self.secret_key.encode(),string_to_encode.encode(),hashlib.sha256).hexdigest()
        return signature

    def init_signature(self):
        method = "GET"
        path = "/v2/user/balance"
        api_expires = self.get_api_expires()
        return method, path, api_expires

    def auth_me(self):
        method, path, api_expires = self.init_signature()
        signature = self.generate_signature(method, path, self.get_api_expires())
        api_expires = self.get_api_expires()
        headers = {
            "api-key": self.api_key,
            "api-signature": signature,
            "api-expires": api_expires
        }
        return headers
