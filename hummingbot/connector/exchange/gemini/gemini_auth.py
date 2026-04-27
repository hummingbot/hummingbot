import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class GeminiAuth(AuthBase):
    """
    Implements Gemini's payload-in-headers REST authentication and WebSocket handshake authentication.

    REST: All params go into a JSON payload with "request" (URL path) and "nonce". The payload is
    base64-encoded -> X-GEMINI-PAYLOAD, then HMAC-SHA384 signed -> X-GEMINI-SIGNATURE. The HTTP body
    stays empty.

    WS (Order Events): The nonce string is base64-encoded as the payload, signed with HMAC-SHA384.
    Headers are passed at WebSocket handshake time.
    """

    def __init__(self, api_key: str, secret_key: str, time_provider: Optional[TimeSynchronizer] = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self._nonce_creator = NonceCreator.for_milliseconds()

    def _generate_nonce(self) -> int:
        return self._nonce_creator.get_tracking_nonce()

    def generate_rest_signature(self, payload_dict: dict) -> Tuple[str, str]:
        """
        Given a payload dict (must include "request" and "nonce"), returns (base64_payload, hex_signature).
        """
        payload_json = json.dumps(payload_dict)
        b64_payload = base64.b64encode(payload_json.encode("utf-8"))
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            b64_payload,
            hashlib.sha384
        ).hexdigest()
        return b64_payload.decode("utf-8"), signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Gemini REST auth:
        1. Build JSON payload with "request" (URL path), "nonce", plus any order params from request.data
        2. Base64-encode the JSON payload -> X-GEMINI-PAYLOAD
        3. HMAC-SHA384(secret, base64_payload) -> X-GEMINI-SIGNATURE
        4. Set headers and clear the body
        """
        headers = dict(request.headers or {})

        # Build the payload from request.data (dict) or empty
        payload_dict: Dict[str, Any] = {}
        if request.data is not None:
            if isinstance(request.data, str):
                payload_dict = json.loads(request.data)
            else:
                payload_dict = dict(request.data)

        # Inject the required "request" and "nonce" fields
        url_path = urlparse(str(request.url)).path
        payload_dict["request"] = url_path
        payload_dict["nonce"] = self._generate_nonce()

        # Generate signature
        b64_payload, signature = self.generate_rest_signature(payload_dict)

        headers.update({
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "Cache-Control": "no-cache",
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-PAYLOAD": b64_payload,
            "X-GEMINI-SIGNATURE": signature,
        })
        request.headers = headers

        # Gemini requires an empty body for authenticated requests
        request.data = None

        return request

    def generate_ws_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for the WebSocket order events endpoint.
        The WS auth payload is just the base64 of the nonce string (not a JSON payload).
        """
        nonce = str(self._generate_nonce())
        b64_payload = base64.b64encode(nonce.encode("utf-8")).decode("utf-8")
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            b64_payload.encode("utf-8"),
            hashlib.sha384
        ).hexdigest()
        return {
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-PAYLOAD": b64_payload,
            "X-GEMINI-SIGNATURE": signature,
        }

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # WS auth for Gemini is done via headers at connect time, not per-message
        return request
