import base64
import hashlib
import hmac
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class KucoinAuth(AuthBase):
    def __init__(self, api_key: str, passphrase: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key: str = api_key
        self.passphrase: str = passphrase
        self.secret_key: str = secret_key
        self.time_provider = time_provider

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. KuCoin does not use this
        functionality
        """
        return request  # pass-through

    def partner_header(self, timestamp: str):
        partner_payload = timestamp + CONSTANTS.HB_PARTNER_ID + self.api_key
        partner_signature = base64.b64encode(
            hmac.new(
                CONSTANTS.HB_PARTNER_KEY.encode("utf-8"),
                partner_payload.encode("utf-8"),
                hashlib.sha256).digest())
        third_party = {
            "KC-API-PARTNER": CONSTANTS.HB_PARTNER_ID,
            "KC-API-PARTNER-SIGN": str(partner_signature, "utf-8")
        }
        return third_party

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = int(self.time_provider.time() * 1000)
        header = {
            "KC-API-KEY": self.api_key,
            "KC-API-TIMESTAMP": str(timestamp),
            "KC-API-KEY-VERSION": "2"
        }

        path_url = f"/api{request.url.split('/api')[-1]}"
        if request.params:
            sorted_params = self.keysort(request.params)
            query_string_components = urlencode(sorted_params, safe=',')
            path_url = f"{path_url}?{query_string_components}"

        if request.data is not None:
            body = request.data
        else:
            body = ""
        payload = str(timestamp) + request.method.value.upper() + path_url + body

        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256).digest())
        passphrase = base64.b64encode(
            hmac.new(
                self.secret_key.encode('utf-8'),
                self.passphrase.encode('utf-8'),
                hashlib.sha256).digest())
        header["KC-API-SIGN"] = str(signature, "utf-8")
        header["KC-API-PASSPHRASE"] = str(passphrase, "utf-8")
        partner_headers = self.partner_header(str(timestamp))
        header.update(partner_headers)
        return header
