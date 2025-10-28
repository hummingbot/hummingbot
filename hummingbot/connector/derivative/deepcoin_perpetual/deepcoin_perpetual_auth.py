import base64
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class DeepcoinPerpetualAuth(AuthBase):
    """
    Auth class required by Deepcoin Perpetual API
    """

    def __init__(self, api_key: str, secret_key: str, passphrase: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        All private REST requests must contain the following headers:

            - DeepCoin-ACCESS-KEY The API Key as a String.
            - DeepCoin-ACCESS-SIGN The Base64-encoded signature
            - DeepCoin-ACCESS-TIMESTAMP The UTC timestamp of your request .e.g : 2020-12-08T09:08:57.715Z
            - DeepCoin-ACCESS-PASSPHRASE The passphrase you specified when creating the APIKey.

        Request bodies should have content type application/json and be in valid JSON format.
        """
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        return request

    def get_referral_code_headers(self):
        """
        Generates referral headers
        """
        headers = {
            "referer": CONSTANTS.HBOT_BROKER_ID
        }
        return headers

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = self._get_timestamp()
        path_url = request.throttler_limit_id
        if request.params:
            query_string_components = urlencode(request.params)
            query_string_components_with_comma = query_string_components.replace("%2C", ",")
            path_url = f"{request.throttler_limit_id}?{query_string_components_with_comma}"

        header = {
            "DC-ACCESS-KEY": self.api_key,
            "DC-ACCESS-SIGN": self._generate_signature(timestamp, request.method.value.upper(), path_url, request.data),
            "DC-ACCESS-TIMESTAMP": timestamp,
            "DC-ACCESS-PASSPHRASE": self.passphrase,
        }

        return header

    def _generate_signature(self, timestamp: str, method: str, path_url: str, body: Optional[str] = None) -> str:
        unsigned_signature = timestamp + method + path_url
        if body is not None:
            unsigned_signature += body

        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode("utf-8"),
                unsigned_signature.encode("utf-8"),
                hashlib.sha256).digest()).decode()
        return signature

    @staticmethod
    def _get_timestamp() -> str:
        ts = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        return ts.replace('+00:00', 'Z')

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through
