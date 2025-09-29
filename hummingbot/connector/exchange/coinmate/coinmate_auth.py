import hashlib
import hmac
import time
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod, RESTRequest, WSRequest
)


class CoinmateAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, client_id: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.client_id = client_id

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.POST:
            # Data comes as a dict from the pre-processor
            params = request.data if isinstance(request.data, dict) else {}
            auth_params = self.add_auth_to_params(params=params)
            request.data = urlencode(auth_params)
        else:
            request.params = self.add_auth_to_params(params=request.params)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def add_auth_to_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nonce = self._generate_nonce()

        request_params = OrderedDict(params or {})
        request_params["publicKey"] = self.api_key
        request_params["clientId"] = self.client_id
        request_params["nonce"] = nonce

        signature = self._generate_signature(nonce=nonce)
        request_params["signature"] = signature

        return request_params

    def _generate_signature(self, nonce: str) -> str:
        message = f"{nonce}{self.client_id}{self.api_key}"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        return signature

    def get_ws_auth_data(self) -> Dict[str, str]:
        nonce = self._generate_nonce()
        return {
            "clientId": self.client_id,
            "publicKey": self.api_key,
            "signature": self._generate_signature(nonce),
            "nonce": nonce,
        }

    def _generate_nonce(self) -> str:
        return str(int(time.time() * 1000))
