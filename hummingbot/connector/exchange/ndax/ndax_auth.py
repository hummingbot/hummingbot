import hashlib
import hmac
import json
from typing import Any, Dict

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class NdaxAuth(AuthBase):
    """
    Auth class required by NDAX API
    """

    def __init__(self, uid: str, api_key: str, secret_key: str, account_name: str):
        self._uid: str = uid
        self._api_key: str = api_key
        self._secret_key: str = secret_key
        self._account_name: str = account_name

    @property
    def uid(self) -> int:
        return int(self._uid)

    @property
    def account_name(self) -> str:
        return self._account_name

    def generate_nonce(self):
        return str(get_tracking_nonce_low_res())

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params(params=json.loads(request.data) if request.data is not None else {})
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
        This method is intended to configure a websocket request to be authenticated. Mexc does not use this
        functionality
        """
        return request

    def add_auth_to_params(self, params: Dict[str, Any]):
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        nonce = self.generate_nonce()
        raw_signature = nonce + self._uid + self._api_key

        auth_info = {
            "Nonce": nonce,
            "APIKey": self._api_key,
            "Signature": hmac.new(
                self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256
            ).hexdigest(),
            "UserId": self._uid,
        }

        return auth_info

    def header_for_authentication(self) -> Dict[str, str]:
        """
        Generates authentication headers required by ProBit
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": "application/json",
        }
