import hashlib
import hmac
import json
from typing import Any, Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BtseAuth(AuthBase):
    """
    Auth class
    Learn more at https://btsecom.github.io/docs/spot/en/#authentication
    """
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
        if request.is_auth_required is not True:
            return request

        # Generates auth headers
        headers_auth = self.get_auth_headers(request.url, request.params)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)

        headers.update(headers_auth)
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Btse does not use this
        functionality
        """
        return request  # pass-through

    def header_for_authentication(self) -> Dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    def get_auth_headers(
        self,
        path_url: str,
        body_data: Dict[str, Any] = None
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :param path_url: URL of the auth API endpoint
        :param body_data: data to be sent to server
        :return: a dictionary of request info including the request signature
        """
        timestamp = int(self.time_provider.time() * 1e3)
        body_json_str = json.dumps(body_data, separators=(',', ':')) if body_data is not None else ''
        encrypted_text = f'{path_url}{str(timestamp)}{body_json_str}'
        print(encrypted_text)

        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            encrypted_text.encode('utf-8'),
            hashlib.sha384
        ).hexdigest()

        return {
            "btse-api": self.api_key,
            "btse-sign": signature,
            "btse-nonce": timestamp,
        }
