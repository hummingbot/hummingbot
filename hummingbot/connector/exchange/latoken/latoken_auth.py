import hashlib
import hmac
from collections import OrderedDict
from time import time
from typing import Dict, Mapping, Optional
from urllib.parse import urlencode, urlsplit

import ujson
from aiohttp import payload

import hummingbot.connector.exchange.latoken.latoken_stomper as stomper
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSPlainTextRequest


class LatokenAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider  # not used atm

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:

        request_params = self.add_auth_to_params(params=request.params)
        if request.method == RESTMethod.POST:
            request.data = payload.JsonPayload(dict(request_params), dumps=ujson.dumps)
            request.params = None
        else:
            request.params = request_params

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        endpoint = str(urlsplit(request.url).path)
        signature = self._generate_signature(method=request.method.name, endpoint=endpoint, params=request_params)
        headers.update(self.header_for_authentication(signature))

        request.headers = headers
        return request

    @staticmethod
    def add_auth_to_params(params: Optional[Mapping[str, str]]) -> Optional[Mapping[str, str]]:
        # timestamp = int(self.time_provider.time() * 1e3)
        request_params = OrderedDict(params or {})
        # request_params["timestamp"] = timestamp
        # signature = self._generate_signature(params=request_params)
        # request_params["signature"] = signature
        return request_params

    def header_for_authentication(self, signature: str) -> Dict[str, str]:
        return {"X-LA-APIKEY": self.api_key,
                "X-LA-SIGNATURE": signature,
                "X-LA-DIGEST": 'HMAC-SHA512'}

    def _generate_signature(self, method: str, endpoint: str, params: Optional[Mapping[str, str]]) -> str:
        encoded_params = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"),
                          (method + endpoint + encoded_params).encode('ascii'),
                          hashlib.sha512).hexdigest()
        return digest

    async def ws_authenticate(self, request: WSPlainTextRequest) -> WSPlainTextRequest:

        timestamp = str(int(float(time()) * 1000))
        signature = hmac.new(
            self.secret_key.encode("utf8"),
            timestamp.encode('ascii'),
            hashlib.sha512
        )

        headers = {"X-LA-APIKEY": self.api_key,
                   "X-LA-SIGNATURE": signature.hexdigest(),
                   "X-LA-DIGEST": 'HMAC-SHA512',
                   "X-LA-SIGDATA": timestamp}

        rq_payload = stomper.Frame()
        rq_payload.unpack(request.payload)
        rq_payload.headers.update(headers)
        request.payload = rq_payload.pack()
        return request  # pass-through

    def generate_auth_payload(self, param):
        pass
