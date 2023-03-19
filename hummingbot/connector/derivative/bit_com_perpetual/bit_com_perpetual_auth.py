import hashlib
import hmac
import json
import time
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlparse

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BitComPerpetualAuth(AuthBase):
    """
    Auth class required by BitCom Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret

    def generate_signature_from_payload(self, payload: str) -> str:
        secret = bytes(self._api_secret.encode("utf-8"))
        signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        _path = urlparse(request.url).path
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(request.data, _path)
        else:
            request.params = self.add_auth_to_params(request.params, _path)
        request.headers = {"X-Bit-Access-Key": self._api_key}
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    def _encode_list(self, item_list):
        list_val = []
        for item in item_list:
            obj_val = self._encode_object(item)
            list_val.append(obj_val)
        sorted_list = sorted(list_val)
        output = '&'.join(sorted_list)
        output = '[' + output + ']'
        return output

    def _encode_object(self, param_map):
        sorted_keys = sorted(param_map.keys())
        ret_list = []
        for key in sorted_keys:
            val = param_map[key]
            if isinstance(val, list):
                list_val = self._encode_list(val)
                ret_list.append(f'{key}={list_val}')
            elif isinstance(val, dict):
                # call encode_object recursively
                dict_val = self._encode_object(val)
                ret_list.append(f'{key}={dict_val}')
            elif isinstance(val, bool):
                bool_val = str(val).lower()
                ret_list.append(f'{key}={bool_val}')
            else:
                general_val = str(val)
                ret_list.append(f'{key}={general_val}')

        sorted_list = sorted(ret_list)
        output = '&'.join(sorted_list)
        return output

    def add_auth_to_params(self, params: Dict[str, Any], path):
        timestamp = int(self._get_timestamp() * 1e3)

        request_params = OrderedDict(params or {})
        request_params.update({'timestamp': timestamp})
        str_to_sign = path + '&' + self._encode_object(request_params)
        request_params["signature"] = self.generate_signature_from_payload(payload=str_to_sign)

        return request_params

    def add_auth_to_params_post(self, params: str, path):
        timestamp = int(self._get_timestamp() * 1e3)

        data = json.loads(params) if params is not None else {}

        request_params = OrderedDict(data or {})
        request_params.update({'timestamp': timestamp})
        str_to_sign = path + '&' + self._encode_object(request_params)
        request_params["signature"] = self.generate_signature_from_payload(payload=str_to_sign)
        res = json.dumps(request_params)
        return res

    @staticmethod
    def _get_timestamp():
        return time.time()
