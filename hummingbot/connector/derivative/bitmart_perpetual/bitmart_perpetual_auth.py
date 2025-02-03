import hashlib
import hmac
from typing import Any, Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BitmartPerpetualAuth(AuthBase):
    """
    Auth class required by Bitmart Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str, memo: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._memo: str = memo
        self._time_provider: TimeSynchronizer = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        payload = request.data if request.data is not None else {}
        timestamp = int(self._time_provider.time() * 1e3)
        auth_headers = {
            "X-BM-KEY": self._api_key,
            "X-BM-SIGN": self.generate_signature_from_payload(payload, timestamp),
            "X-BM-TIMESTAMP": str(timestamp)
        }
        request.headers.update(auth_headers)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    def generate_signature_from_payload(self, payload: str, timestamp: int) -> str:
        raw_message = f"{timestamp}#{self._memo}#{payload}"
        secret = self._api_secret.encode("utf-8")
        message = raw_message.encode("utf-8")
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return signature

    def get_ws_login_with_args(self) -> Dict[str, Any]:
        """
        Constructs the arguments for WebSocket authentication.
        """
        timestamp = str(int(self._time_provider.time() * 1e3))  # Timestamp in milliseconds
        raw_message = f"{timestamp}#{self._memo}#bitmart.WebSocket"
        secret = self._api_secret.encode("utf-8")
        message = raw_message.encode("utf-8")
        sign = hmac.new(secret, message, hashlib.sha256).hexdigest()

        return {
            "action": "access",
            "args": [self._api_key, timestamp, sign, "web"]
        }
