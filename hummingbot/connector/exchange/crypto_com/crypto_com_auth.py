import hashlib
import hmac
import json
from collections import OrderedDict
from typing import Any, Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class CryptoComAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self.MAX_LEVEL = 3  # max level of nested params - checkout Crypto.com API docs for Digital Signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the api_key and the signature to the request, required for authenticated interactions.
        Check out the Crypto.com API docs for Digital Signature for more information here:
        https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html#digital-signature
        :param request: the request to be configured for authenticated interaction
        """
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params(params=json.loads(request.data))
        else:
            request.params = self.add_auth_to_params(params=request.params)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. CryptoCom does not use this
        functionality
        """
        return request  # pass-through

    def params_to_str(self, obj: Any, level: int = 0):
        if level >= self.MAX_LEVEL:
            return str(obj)

        return_str = ""
        for key in sorted(obj):
            return_str += key
            if obj[key] is None:
                return_str += 'null'
            elif isinstance(obj[key], list):
                for subObj in obj[key]:
                    return_str += self.params_to_str(subObj, ++level)
            else:
                return_str += str(obj[key])
        return return_str

    def add_auth_to_params(self, params: Dict[str, Any]):
        request_params = OrderedDict(params or {})
        request_params["api_key"] = self.api_key

        if "params" in request_params:
            param_str = self.params_to_str(request_params['params'], 0)

        payload_str = request_params['method'] + str(request_params['id']) + request_params['api_key'] + \
            param_str + str(request_params['nonce'])

        signature = self._generate_signature(payload_str=payload_str)
        request_params["sig"] = signature

        return request_params

    def _generate_signature(self, payload_str: str) -> str:
        digest = hmac.new(
            bytes(str(self.secret_key), 'utf-8'),
            msg=bytes(payload_str, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        return digest
