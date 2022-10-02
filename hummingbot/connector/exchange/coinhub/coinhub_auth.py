import hashlib
import hmac
import json
import time
from urllib.parse import urlencode, urlparse

from hummingbot.connector.exchange.coinhub import coinhub_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class CoinhubAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        timestamp = int(time.time() * 1000)
        path_url = urlparse(request.url).path

        if request.method == RESTMethod.POST:
            data = json.dumps(json.loads(request.data), separators=(',', ":"))
            content_to_sign = f"{timestamp}{request.method}{path_url}{data}"
        else:
            encoded_param = urlencode(request.params)
            content_to_sign = f"{timestamp}{request.method}{path_url}{encoded_param}"

        signature = hmac.new(
            self.secret_key.encode("utf8"), msg=content_to_sign.encode("utf8"), digestmod=hashlib.sha256
        ).hexdigest()

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        # v1 Authentication headers
        headers.update({"API-KEY": self.api_key, "SIGN": signature, "TS": str(timestamp)})
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSJSONRequest) -> WSJSONRequest:
        access_id: str = self.api_key
        tonce = int(1000 * time.time())
        content_to_sign = f"{tonce}{RESTMethod.POST}{CONSTANTS.WS_SIGN_PATH_URL}"
        content_to_sign += "{}"
        signature = hmac.new(
            self.secret_key.encode("utf8"), msg=content_to_sign.encode("utf8"), digestmod=hashlib.sha256
        ).hexdigest()

        subscribe = {"id": 111111, "method": "server.sign", "params": [access_id, signature, tonce]}

        request.payload.update(subscribe)
        return request
