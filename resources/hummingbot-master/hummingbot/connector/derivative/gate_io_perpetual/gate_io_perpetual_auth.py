import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import urlparse

import six

from hummingbot.connector.derivative.gate_io_perpetual import gate_io_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class GateIoPerpetualAuth(AuthBase):
    """
    Auth Gate.io API
    https://www.gate.io/docs/apiv4/en/#authentication
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self._get_auth_headers(request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        request.payload["auth"] = self._get_auth_headers_ws(payload=request.payload)
        return request

    def _get_auth_headers_ws(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generates authn for Gate.io websockets

        :return: a dictionary with headers
        """
        sig = self._sign_payload_ws(payload['channel'], payload['event'], payload['time'])
        headers = {
            "method": "api_key",
            "KEY": f"{self.api_key}",
            "SIGN": f"{sig}",
        }
        return headers

    def _get_auth_headers(self, request: RESTRequest) -> Dict[str, Any]:
        """
        Generates authentication headers for Gate.io REST API

        :return: a dictionary with headers
        """
        sign, ts = self._sign_payload(request)
        headers = {
            "X-Gate-Channel-Id": CONSTANTS.HBOT_BROKER_ID,
            "KEY": f"{self.api_key}",
            "Timestamp": f"{ts}",
            "SIGN": f"{sign}",
            "Content-Type": "application/json",
        }
        return headers

    def _sign_payload_ws(self, channel, event, time) -> str:
        return self._sign(f"channel={channel}&event={event}&time={time}")

    def _sign_payload(self, r: RESTRequest) -> (str, int):
        query_string = ""
        body = r.data

        ts = self._get_timestamp()
        m = hashlib.sha512()
        path = urlparse(r.url).path

        if body is not None:
            if not isinstance(r.data, six.string_types):
                body = json.dumps(r.data)
            m.update(body.encode('utf-8'))
        body_hash = m.hexdigest()

        if r.params:
            qs = []
            for k, v in r.params.items():
                qs.append(f"{k}={v}")
            query_string = "&".join(qs)

        s = f'{r.method}\n{path}\n{query_string}\n{body_hash}\n{ts}'
        return self._sign(s), ts

    def _sign(self, payload) -> str:
        return hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512).hexdigest()

    @staticmethod
    def _get_timestamp():
        return time.time()
