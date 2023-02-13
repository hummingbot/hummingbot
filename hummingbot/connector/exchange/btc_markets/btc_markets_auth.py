import base64
import hashlib
import hmac
import time
from typing import Any, Dict

import hummingbot.connector.exchange.btc_markets.btc_markets_constants as CONSTANTS
from hummingbot.connector.exchange.btc_markets import btc_markets_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BtcMarketsAuth(AuthBase):
    """
    Auth class required by btc_markets API
    Learn more at https://api.btcmarkets.net/doc/v3#section/Authentication/Authentication-process
    """
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
        now = self._timestamp_in_milliseconds()
        sig = self.get_signature(
            request.method.name,
            web_utils.get_path_from_url(request.url),
            now,
            request.data if request.method.name == "POST" else {}
        )

        headers = self._generate_auth_headers(now, sig)
        if request.headers is not None:
            headers.update(request.headers)
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. BtcMarkets does not use this
        functionality
        """
        return request  # pass-through

    def get_referral_code_headers(self):
        """
        Generates authentication headers required by BtcMarkets
        :return: a dictionary of auth headers
        """
        return {
            "referer": CONSTANTS.HBOT_BROKER_ID
        }

    def get_signature(
        self,
        method: str,
        path_url: str,
        nonce: int,
        data: Dict[str, Any] = None
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        data = data or {}

        if data is None or data == {}:
            payload = f"{method}/{path_url}{nonce}{''}"
        else:
            bjson = str(data)
            payload = f"{method}/{path_url}{nonce}{bjson}"

        return self._generate_signature(payload)

    def _generate_auth_headers(self, nonce: int, sig: str):
        """
        Generates HTTP headers
        """
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "UTF-8",
            "Content-Type": "application/json",
            "BM-AUTH-APIKEY": self.api_key,
            "BM-AUTH-TIMESTAMP": str(nonce),
            "BM-AUTH-SIGNATURE": sig
        }

        return headers

    def _generate_signature(self, payload: str) -> str:
        """
        Generates a presigned signature
        :return: a signature of auth params
        """
        digest = base64.b64encode(hmac.new(
            base64.b64decode(self.secret_key), payload.encode("utf8"), digestmod=hashlib.sha512).digest())
        return digest.decode('utf8')

    def _generate_auth_dict_ws(self, nonce: int) -> str:
        """
        Generates an authentication params for websockets login
        :return: a signature of auth params
        """

        payload = "/users/self/subscribe" + "\n" + str(nonce)
        return self._generate_signature(payload)

    def generate_ws_authentication_message(self) -> str:
        """
        Generates the authentication message to start receiving messages from
        the 3 private ws channels
        """
        now = self._timestamp_in_milliseconds()
        signature = self._generate_auth_dict_ws(now)
        auth_message = {
            "signature": signature,
            "key": self.api_key,
            "timestamp": str(now),
            "messageType": CONSTANTS.SUBSCRIBE,
        }
        return auth_message

    def _timestamp_in_milliseconds(self) -> int:
        return int(self._time() * 1e3)

    def _time(self):
        return time.time()
