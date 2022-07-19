import time
import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTRequest


class SouthXchangeAuth():
    """
    Auth class required by SouthXchange API
    Learn more at https://main.southxchange.com/Content/swagger/ui/?urls.primaryName=API%20v4#/
    """
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    def get_auth_headers(self,
                         path_url: str = "",
                         data: Optional[Dict[str, Any]] = None):
        """
        Modify - SouthXchange
        """
        request_params = data or {}
        request_params['nonce'] = str(int(time.time() * 1e3))
        request_params['key'] = self.api_key
        userSignature = hmac.new(
            self.secret_key.encode('utf-8'),
            json.dumps(request_params).encode('utf8'),
            hashlib.sha512
        ).hexdigest()
        header = {'Hash': userSignature, 'Content-Type': 'application/json'}
        return {
            "header": header,
            "data": request_params,
        }

    def get_api_key(self) -> str:
        return self.api_key

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates generic headers required by SouthXchange
        :return: a dictionary of headers
        """
        header = {'Content-Type': 'application/json'}
        return {
            "header": header,
            "data": None,
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        # Generates auth headers
        headers_auth = self.get_auth_headers(request.endpoint_url)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(headers_auth)
        request.headers = headers

        return request
