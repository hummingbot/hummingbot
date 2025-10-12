import hashlib
import hmac
import json
from typing import Any, Dict, Optional

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class EvedexAuth(AuthBase):
    """
    Authentication class for EVEDEX exchange.
    Handles signing of REST requests and WebSocket authentication.
    """

    def __init__(self,
                 api_key: str,
                 secret_key: Optional[str],
                 access_token: Optional[str],
                 time_provider: TimeSynchronizer):
        """
        Initialize the EVEDEX authenticator.

        :param api_key: The API key for authentication
        :param secret_key: The secret key for signing requests
        :param time_provider: A time synchronizer for generating timestamps
        """
        self.api_key: str = api_key
        self.secret_key: Optional[str] = secret_key
        self.access_token: Optional[str] = access_token
        self.time_provider: TimeSynchronizer = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication headers to a REST request.

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
        Configures a websocket request to be authenticated.
        For EVEDEX, authentication is typically done via a login message after connection.

        :param request: the websocket request to authenticate
        :return: the authenticated websocket request
        """
        return request  # WebSocket auth is done via login message, not request modification

    def generate_signature(self, payload: Dict[str, Any]) -> str:
        """Generates an HMAC signature for the provided payload."""
        if not self.secret_key:
            raise ValueError("Secret key is required to generate EVEDEX signatures.")

        # Sort keys to produce consistent payload representation
        canonical_payload = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            canonical_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        """
        Generates authentication headers for a REST request.

        :param request: the REST request to generate headers for
        :return: dictionary of authentication headers
        """
        headers: Dict[str, Any] = {"Content-Type": "application/json"}

        if self.api_key:
            headers["X-API-Key"] = self.api_key

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    def websocket_login_parameters(self) -> Dict[str, Any]:
        """
        Generates login parameters for WebSocket authentication.

        :return: dictionary with login parameters
        """
        timestamp = str(int(self.time_provider.time() * 1000))

        login_payload = {
            "apiKey": self.api_key,
            "timestamp": timestamp,
        }

        if self.secret_key:
            login_payload["signature"] = hmac.new(
                self.secret_key.encode("utf-8"),
                f"{timestamp}websocket".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

        return {
            "op": "login",
            "args": login_payload,
        }

    def get_ws_login_message(self) -> Dict[str, Any]:
        """
        Returns the WebSocket login message.

        :return: WebSocket login message as a dictionary
        """
        return self.websocket_login_parameters()
