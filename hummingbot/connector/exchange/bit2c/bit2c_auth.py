import base64
import hashlib
import hmac
import json
import time
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class Bit2cAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the Key and the signature to the headers and nonce to the request parameters, required for authenticated interactions.
        :param request: the request to be configured for authenticated interaction
        """
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)

        nonce = int(time.time_ns() * 1e-3)
        auth_headers = {}
        if request.method == RESTMethod.POST:
            params = json.loads(request.data)
            params = params if params is not None else {}
            params["nonce"] = nonce
            auth_headers = self.add_auth_to_headers(params=params)
            request.data = params
        else:
            params = request.params
            params = params if params is not None else {}
            params["nonce"] = nonce
            auth_headers = self.add_auth_to_headers(params=params)
            request.params = params

        headers.update(auth_headers)
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Bit2c does not use this
        functionality
        """
        return request  # pass-through

    def add_auth_to_headers(self,
                            params: Dict[str, Any]):
        headers = OrderedDict({})
        signature = self._generate_signature(params=params)

        headers["Key"] = self.api_key
        headers["Sign"] = signature
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        return headers

    def _generate_signature(self, params: Dict[str, Any]) -> str:

        encoded_params_str = urlencode(params)
        # signature generation(complex!) as per Bit2c documentation - https://bit2c.co.il/home/api#generatekey
        signature = base64.b64encode(hmac.new(self.secret_key.upper().encode("ASCII"), encoded_params_str.encode("ASCII"), hashlib.sha512).digest()).decode("ASCII").replace("\n", "")

        return signature
