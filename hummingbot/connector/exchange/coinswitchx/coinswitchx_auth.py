import json
from datetime import datetime, timezone
from typing import Dict
from urllib.parse import urlparse

from cryptography.hazmat.primitives.asymmetric import ed25519

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class CoinswitchxAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    def _generate_signature(private_key: str, sign_params: Dict):

        private_key_bytes = bytes.fromhex(private_key)

        message_str = json.dumps(
            sign_params["message"],
            sort_keys=True,  # sort keys in the request payload
            separators=(',', ':'),  # compact encoding to remove whitespace
        )
        message_bytes = bytes(
            str(sign_params["timestamp"]) +
            sign_params["method"] +
            sign_params["urlPath"] +
            message_str,
            'utf-8'
        )

        private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        signature = private_key_obj.sign(message_bytes)

        return signature

    async def rest_authenticate(self,
                                request: RESTRequest,
                                ) -> RESTRequest:

        timestamp = int(datetime.now(timezone.utc).timestamp())

        parsed_url = urlparse(request.url)

        url_path = parsed_url.path + '?' + parsed_url.query if parsed_url.query else parsed_url.path

        data = request.data if request.data is not None else ""

        sign_params = {
            "timestamp": timestamp,  # current time in epoch seconds
            "method": request.method,
            "urlPath": url_path,  # url path with query params
            "message": data
        }

        signature = self._generate_signature(self.secret_key, sign_params)

        coinswitchx_header = {
            "CSX-ACCESS-KEY": self.api_key,
            "CSX-SIGNATURE": signature,
            "CSX-ACCESS-TIMESTAMP": timestamp,
            # TODO X-Forwarded-For
        }

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(coinswitchx_header)
        request.headers = headers

        return request

    async def ws_authenticate(self,
                              request: WSRequest,
                              ) -> WSRequest:
        pass
    #     """
    #     This method is intended to configure a websocket request to be authenticated.
    #     It should be used with empty requests to send an initial login payload.
    #     :param request: the request to be configured for authenticated interaction
    #     """

    #     request.payload = self.get_ws_authenticate_payload(request)
    #     return request

    # def get_ws_authenticate_payload(self,
    #                                 request: WSRequest = None,
    #                                 ) -> Dict[str, any]:
    #     timestamp = int(datetime.now(timezone.utc).timestamp() * 1e3)

    #     msg = '{}{}{}'.format(timestamp,
    #                           self.user_id,
    #                           self.api_key)

    #     signature = hmac.new(self.secret_key.encode("utf8"),
    #                          msg.encode("utf8"),
    #                          hashlib.sha256).digest().hex()

    #     payload = {
    #         "APIKey": self.api_key,
    #         "Signature": signature,
    #         "UserId": self.user_id,
    #         "Nonce": timestamp
    #     }

    #     if hasattr(request, 'payload'):
    #         payload.update(request.payload)

    #     return payload
