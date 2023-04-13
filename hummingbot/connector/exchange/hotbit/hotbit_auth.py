import hashlib
import json
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class HotbitAuth(AuthBase):
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
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params(params=json.loads(request.data))
            headers = request.headers if request.headers is not None else {}
            headers.update({
                "Content-Type": "application/x-www-form-urlencoded"
            })
            request.headers = headers
        else:
            request.params = self.add_auth_to_params(params=request.params)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Hotbit does not use this
        functionality
        """
        return request  # pass-through

    def add_auth_to_params(self,
                           params: Dict[str, Any]):
        params['sign'] = self.sign(params)
        # print(params)
        return urlencode(params)

    def sign(self, params: Dict[str, Any]):
        params['api_key'] = self.api_key
        paramsStr = json.dumps(params, sort_keys=True, indent=4)
        # print(paramsStr)

        params_json = json.loads(paramsStr)
        out_str = ""
        items = params_json.items()
        for key, value in items:
            out_str += key + '=' + value + '&'
        out_str += 'secret_key=' + self.secret_key
        # print(out_str)
        hash_md5 = hashlib.md5(out_str.encode(encoding='utf-8'))
        sign = hash_md5.hexdigest().upper()
        # print(sign)
        return sign
