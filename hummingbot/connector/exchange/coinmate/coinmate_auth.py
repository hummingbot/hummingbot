import hashlib
import hmac
import time
from collections import OrderedDict
from typing import Any, Dict

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod, RESTRequest, WSRequest
)


class CoinmateAuth(AuthBase):
    """
    Coinmate authentication using HMAC-SHA256

    Coinmate API requires:
    - publicKey: API key
    - privateKey: API secret  
    - clientId: Client ID
    - nonce: Timestamp in milliseconds
    - signature: HMAC-SHA256(nonce + clientId + publicKey, privateKey)
    """

    def __init__(self, api_key: str, secret_key: str, client_id: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.client_id = client_id

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication parameters to the request, required for authenticated 
        interactions.
        :param request: the request to be configured for authenticated interaction
        """
        if request.method == RESTMethod.POST:
            params = request.data if isinstance(request.data, dict) else None
            request.data = self.add_auth_to_params(params=params)
        else:
            request.params = self.add_auth_to_params(params=request.params)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
         This method is intended to configure a websocket request to be authenticated.
         functionality
         """
        return request  # pass-through

    def add_auth_to_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add authentication parameters to the request parameters.
        :param params: existing request parameters
        :return: parameters with authentication data added
        """
        nonce = str(int(time.time() * 1000))

        request_params = OrderedDict(params or {})
        request_params["publicKey"] = self.api_key
        request_params["clientId"] = self.client_id
        request_params["nonce"] = nonce

        signature = self._generate_signature(nonce=nonce)
        request_params["signature"] = signature

        return request_params

    def _generate_signature(self, nonce: str) -> str:
        """
        Generate HMAC-SHA256 signature for Coinmate API.
        :param nonce: timestamp in milliseconds as string
        :return: HMAC-SHA256 signature in uppercase hexadecimal format
        """
        message = f"{nonce}{self.client_id}{self.api_key}"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        return signature
