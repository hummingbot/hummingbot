import hashlib
import hmac
import time
import urllib
import uuid
from typing import Any, Dict

import ujson

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BittrexAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authenticate_REST_request(request=request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        auth_params = self.authenticate_WS_request()
        request.payload['A'] = auth_params
        return request

    @staticmethod
    def construct_content_hash(body) -> str:
        json_byte: bytes = "".encode()
        if body:
            json_byte = ujson.dumps(body).encode()
            return hashlib.sha512(json_byte).hexdigest()
        return hashlib.sha512(json_byte).hexdigest()

    def authenticate_REST_request(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = str(int(time.time() * 1000))
        url = request.url
        request_body = {}
        if "body" in request.__dict__:
            request_body = request.body
        content_hash = self.construct_content_hash(request_body)
        if request.params:
            param_str = urllib.parse.urlencode(request.params)
            url = f"{url}?{param_str}"
        content_to_sign = "".join([timestamp, url, request.method.name, content_hash, ""])
        signature = hmac.new(self.secret_key.encode(), content_to_sign.encode(), hashlib.sha512).hexdigest()
        headers = {
            "Api-Key": self.api_key,
            "Api-Timestamp": timestamp,
            "Api-Content-Hash": content_hash,
            "Api-Signature": signature,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        return headers

    def authenticate_WS_request(self):
        timestamp = str(int(time.time() * 1000))
        randomized = str(uuid.uuid4())
        content_to_sign = f"{timestamp}{randomized}"
        signature = hmac.new(self.secret_key.encode(), content_to_sign.encode(), hashlib.sha512).hexdigest()
        return [self.api_key, timestamp, randomized, signature]
