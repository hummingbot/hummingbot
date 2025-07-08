import base64
import hashlib
import hmac
import json
import time
from collections import OrderedDict
from decimal import Decimal
from typing import Any, Dict, List
from urllib.parse import urlencode

from hummingbot.connector.derivative.kucoin_perpetual import kucoin_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class KucoinPerpetualAuth(AuthBase):
    """
    Auth class required by Kucoin Perpetual API
    """

    def __init__(self, api_key: str, passphrase: str, secret_key: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key
        self._passphrase: str = passphrase
        self._secret_key: str = secret_key
        self._time_provider: TimeSynchronizer = time_provider

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    async def rest_authenticate(self, request: RESTRequest, use_time_provider=0) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request, use_time_provider=use_time_provider))
        request.headers = headers

        return request

    async def _authenticate_get(self, request: RESTRequest) -> RESTRequest:
        params = request.params or {}
        request.params = self._extend_params_with_authentication_info(params)
        return request

    async def _authenticate_post(self, request: RESTRequest) -> RESTRequest:
        data = json.loads(request.data) if request.data is not None else {}
        data = self._extend_params_with_authentication_info(data)
        data = {key: value for key, value in sorted(data.items())}
        request.data = json.dumps(data)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through

    def get_ws_auth_payload(self) -> List[str]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        expires = self._get_expiration_timestamp()
        raw_signature = "GET/realtime" + expires
        signature = hmac.new(
            self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        auth_info = [self._api_key, expires, signature]

        return auth_info

    def _extend_params_with_authentication_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["timestamp"] = self._get_timestamp()
        params["api_key"] = self._api_key
        key_value_elements = []
        for key, value in sorted(params.items()):
            converted_value = float(value) if type(value) is Decimal else value
            converted_value = converted_value if type(value) is str else json.dumps(converted_value)
            key_value_elements.append(str(key) + "=" + converted_value)
        raw_signature = "&".join(key_value_elements)
        signature = hmac.new(self._secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256).hexdigest()
        params["sign"] = signature
        return params

    def partner_header(self, timestamp: str):
        partner_payload = timestamp + CONSTANTS.HB_PARTNER_ID + self._api_key
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

    def authentication_headers(self, request: RESTRequest, use_time_provider) -> Dict[str, Any]:
        if use_time_provider == 1 and self._time_provider.time() > 0:
            timestamp = self._time_provider.time()
        else:
            timestamp = int(self._get_timestamp())

        header = {
            "KC-API-KEY": self._api_key,
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
                self._secret_key.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256).digest())
        passphrase = base64.b64encode(
            hmac.new(
                self._secret_key.encode('utf-8'),
                self._passphrase.encode('utf-8'),
                hashlib.sha256).digest())
        header["KC-API-SIGN"] = str(signature, "utf-8")
        header["KC-API-PASSPHRASE"] = str(passphrase, "utf-8")
        partner_headers = self.partner_header(str(timestamp))
        header.update(partner_headers)
        return header

    @staticmethod
    def _get_timestamp():
        return str(int(time.time() * 1e3))

    @staticmethod
    def _get_expiration_timestamp():
        return str(int((round(time.time()) + 5) * 1e3))
