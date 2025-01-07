import hashlib
import hmac
import json
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.exchange.valr import valr_constants as CONSTANTS, valr_utils, valr_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class ValrAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add the required parameters in the request header.
        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        path_url=valr_utils.get_path_url(request.url)
        headers.update(self.header_for_authentication(method=request.method.name, path_url=path_url,body=request.data))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add the required parameters in the request header for websocket requests.
        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        path_url=valr_utils.get_path_url(request.url)
        headers.update(self.header_for_authentication(method=request.method.name, path_url=path_url))
        request.headers = headers

        return request  # pass-through

    def header_for_authentication(
        self,
        method: str,
        path_url: str,
        body: str = '') -> Dict[str, Any]:
        """
        Generates authentication headers required by valr.com
        :return: a dictionary of auth headers
        """
        if body is None:
            body = ''
        timestamp = valr_utils.get_ms_timestamp()
        payload = "{}{}{}{}".format(timestamp, method.upper(), path_url, body)
        signature = hmac.new(self.secret_key.encode('utf-8'), payload.encode('utf-8'), hashlib.sha512).hexdigest()
        
        return { 
            "X-VALR-API-KEY": self.api_key,
            "X-VALR-SIGNATURE": signature,
            "X-VALR-TIMESTAMP": str(timestamp),
            'Content-Type': 'application/json',
        }

