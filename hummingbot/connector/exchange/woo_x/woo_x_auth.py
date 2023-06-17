import hashlib
import hmac
import json
from typing import Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class WooXAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication headers to the request
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        timestamp = str(int(self.time_provider.time() * 1e3))

        if request.method == RESTMethod.POST:
            request.headers = self.headers(timestamp, **json.loads(request.data or json.dumps({})))

            request.data = json.loads(request.data or json.dumps({}))  # Allow aiohttp to send as application/x-www-form-urlencoded
        else:
            request.headers = self.headers(timestamp, **(request.params or {}))

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        Woo X does not use this functionality
        """
        return request  # pass-through

    def signature(self, timestamp, **kwargs):
        signable = '&'.join([f"{key}={value}" for key, value in sorted(kwargs.items())]) + f"|{timestamp}"

        return hmac.new(
            bytes(self.secret_key, "utf-8"),
            bytes(signable, "utf-8"),
            hashlib.sha256
        ).hexdigest().upper()

    def headers(self, timestamp, **kwargs) -> Dict[str, str]:
        return {
            'x-api-timestamp': timestamp,
            'x-api-key': self.api_key,
            'x-api-signature': self.signature(timestamp, **kwargs),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache',
        }
