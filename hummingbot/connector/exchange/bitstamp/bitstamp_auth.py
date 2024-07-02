import hashlib
import hmac
import uuid
from typing import Dict
from urllib.parse import urlencode, urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BitstampAuth(AuthBase):
    AUTH_VERSION = "v2"

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
        local_headers = {}
        if request.headers is not None:
            local_headers.update(request.headers)

        auth_headers = self._generate_headers_for_authentication(
            request_url=request.url,
            content_type=local_headers.get("Content-Type"),
            payload=request.data,
            method=request.method,
        )

        local_headers.update(auth_headers)
        request.headers = local_headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Bitstamp does not use this
        functionality
        """
        return request  # pass-through

    def _generate_headers_for_authentication(self, method: RESTMethod, request_url: str, content_type: str, payload) -> Dict[str, str]:
        nonce = str(uuid.uuid4())
        timestamp_str = str(int(self.time_provider.time() * 1e3))

        headers = {
            'X-Auth': 'BITSTAMP ' + self.api_key,
            'X-Auth-Signature': self._generate_signature(self._generate_message(method, request_url, content_type, payload, nonce, timestamp_str)),
            'X-Auth-Nonce': nonce,
            'X-Auth-Timestamp': timestamp_str,
            'X-Auth-Version': self.AUTH_VERSION
        }

        return headers

    def _generate_message(self, method: RESTMethod, request_url: str, content_type: str, payload, nonce: str, timestamp_str: str) -> str:
        content_type = content_type or ""
        payload_str = urlencode(payload) if payload else ""
        url = urlparse(request_url)
        message = f"BITSTAMP {self.api_key}{method}{url.hostname}{url.path}{content_type}{nonce}{timestamp_str}{self.AUTH_VERSION}{payload_str}"

        return message

    def _generate_signature(self, msg: str) -> str:
        digest = hmac.new(self.secret_key.encode("utf8"), msg=msg.encode("utf8"), digestmod=hashlib.sha256).hexdigest()
        return digest
