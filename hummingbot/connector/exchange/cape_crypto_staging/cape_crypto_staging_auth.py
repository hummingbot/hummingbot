import hashlib
import hmac
import json
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.exchange.cape_crypto_staging import (
    cape_crypto_staging_constants as CONSTANTS,
    cape_crypto_staging_utils,
    cape_crypto_staging_web_utils as web_utils,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class CapeCryptoStagingAuth(AuthBase):
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
        headers.update(self.header_for_authentication())
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
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request  # pass-through

    def header_for_authentication(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by cape_crypto_staging.com
        :return: a dictionary of auth headers
        """

        timestamp = cape_crypto_staging_utils.get_ms_timestamp()
        payload = "{}{}".format(timestamp, self.api_key)
        signature = hmac.new(self.secret_key.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
        
        return { 
            "X-Auth-Apikey": self.api_key,
            "X-Auth-Signature": signature,
            "X-Auth-Nonce": str(timestamp),
            'Content-Type': 'application/json',
        }

