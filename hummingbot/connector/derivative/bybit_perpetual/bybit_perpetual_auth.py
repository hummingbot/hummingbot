import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import Any, Dict, List

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BybitPerpetualAuth(AuthBase):
    """
    Auth class required by Bybit Perpetual API
    """
    def __init__(self, api_key: str, secret_key: str):
        self._api_key: str = api_key
        self._secret_key: str = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.GET:
            request = await self._authenticate_get(request)
        elif request.method == RESTMethod.POST:
            request = await self._authenticate_post(request)
        else:
            raise NotImplementedError
        return request

    async def _authenticate_get(self, request: RESTRequest) -> RESTRequest:
        params = request.params or {}
        request.params = self._extend_params_with_authentication_info(params)
        return request

    async def _authenticate_post(self, request: RESTRequest) -> RESTRequest:
        data = json.loads(request.data) if request.data is not None else {}
        data = self._extend_params_with_authentication_info(data)
        data = {key: value for key, value in sorted(data.items())}
        request.data = json.dumps(data)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through

    def get_ws_auth_payload(self) -> List[str]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        expires = self._get_expiration_timestamp()
        raw_signature = "GET/realtime" + expires
        signature = hmac.new(
            self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        auth_info = [self._api_key, expires, signature]

        return auth_info

    def _extend_params_with_authentication_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["timestamp"] = self._get_timestamp()
        params["api_key"] = self._api_key
        key_value_elements = []
        for key, value in sorted(params.items()):
            converted_value = float(value) if type(value) is Decimal else value
            converted_value = converted_value if type(value) is str else json.dumps(converted_value)
            key_value_elements.append(str(key) + "=" + converted_value)
        raw_signature = "&".join(key_value_elements)
        signature = hmac.new(self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256).hexdigest()
        params["sign"] = signature
        return params

    @staticmethod
    def _get_timestamp():
        return str(int(time.time() * 1e3))

    @staticmethod
    def _get_expiration_timestamp():
        return str(int((round(time.time()) + 5) * 1e3))
