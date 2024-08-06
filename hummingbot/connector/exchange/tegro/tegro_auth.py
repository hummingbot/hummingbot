import json
from collections import OrderedDict
from typing import Any, Dict

from eth_account import Account, messages

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class TegroAuth(AuthBase):
    """
    Auth class required by Tegro API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret

    def sign_inner(self, data):
        """
        Sign the provided data using the API secret key.
        """
        wallet = Account.from_key(self._api_secret)
        signed_data = wallet.sign_message(data)
        # Convert signature components to bytes before returning
        return signed_data.signature.hex()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        if request.method == RESTMethod.POST and request.data is not None:
            request.data = self.add_auth_to_params(params=json.loads(request.data) if request.data is not None else {})
        else:
            request.params = self.add_auth_to_params(params=request.params)
        # Generates auth headers

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    def add_auth_to_params(self,
                           params: Dict[str, Any]):
        request_params = OrderedDict(params or {})

        addr = self._api_key
        address = addr.lower()
        structured_data = messages.encode_defunct(text=address)
        signature = self.sign_inner(structured_data)
        request_params["signature"] = signature
        return request_params

    def header_for_authentication(self) -> Dict[str, Any]:
        return {
            "Content-Type": 'application/json',
        }

    def get_auth_headers(self):
        headers = self.header_for_authentication()
        headers.update(self._generate_auth_dict())
        return headers
