from typing import Any, Dict
from urllib.parse import urlencode

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class VestAuth(AuthBase):

    def __init__(self, api_key: str, primary_address: str, signing_address: str, private_key: str, time_provider: TimeSynchronizer):
        if not ETH_ACCOUNT_AVAILABLE:
            raise ImportError("eth-account is required for Vest Markets connector. Install with 'pip install eth-account'")

        self.api_key: str = api_key
        self.primary_address: str = primary_address
        self.signing_address: str = signing_address
        self.private_key: str = private_key
        self.time_provider: TimeSynchronizer = time_provider
        self.account = Account.from_key(private_key)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the authentication headers to the request for Vest Markets API

        :param request: the request to be configured for authenticated interaction

        :return: The RESTRequest with auth information included
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        """
        return request  # pass-through for now

    def _generate_signature(self, timestamp: int, method: str, path: str, body: str = "") -> str:
        """
        Generate signature for Vest Markets API using Ethereum signing
        """
        # Create message to sign based on Vest's authentication requirements
        message = f"{timestamp}{method.upper()}{path}{body}"
        message_hash = encode_defunct(text=message)

        # Sign with private key
        signed_message = self.account.sign_message(message_hash)
        return signed_message.signature.hex()

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        """
        Generate authentication headers for Vest Markets
        """
        timestamp = int(self.time_provider.time() * 1000)  # milliseconds

        # Extract path from full URL
        if "/v2/" in request.url:
            path = "/" + request.url.split("/v2/")[-1]
            path = "/v2" + path
        else:
            # Fallback to using the path component of the URL
            from urllib.parse import urlparse
            parsed_url = urlparse(request.url)
            path = parsed_url.path or "/"

        # Add query parameters to path if present
        if request.params:
            query_string = urlencode(request.params)
            path = f"{path}?{query_string}"

        body = request.data if request.data else ""

        signature = self._generate_signature(timestamp, request.method.value, path, body)

        headers = {
            "X-API-KEY": self.api_key,
            "X-PRIMARY-ADDR": self.primary_address,
            "X-SIGNING-ADDR": self.signing_address,
            "X-TIMESTAMP": str(timestamp),
            "X-SIGNATURE": signature,
            "Content-Type": "application/json"
        }

        return headers

    def websocket_login_parameters(self) -> Dict[str, Any]:
        """
        Generate WebSocket login parameters for Vest Markets
        """
        timestamp = int(self.time_provider.time() * 1000)

        # Create authentication signature for WebSocket
        signature = self._generate_signature(timestamp, "GET", "/ws-login", "")

        return {
            "apiKey": self.api_key,
            "primaryAddr": self.primary_address,
            "signingAddr": self.signing_address,
            "timestamp": timestamp,
            "signature": signature
        }
