import base64
import hashlib
import hmac
import json
from urllib.parse import urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class WhitebitAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.time_provider: TimeSynchronizer = time_provider
        self._nonce_creator = NonceCreator.for_milliseconds()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction
        """

        self._add_authentication_details(request=request)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. WhiteBit does not use this
        functionality
        """
        return request  # pass-through

    def _add_authentication_details(self, request: RESTRequest) -> RESTRequest:
        timestamp = self.time_provider.time()
        nonce = self._nonce_creator.get_tracking_nonce(timestamp=timestamp)
        parsed_url = urlparse(request.url)
        path_url = parsed_url.path

        authentication_params = {
            "request": path_url,
            "nonce": str(nonce),
            "nonceWindow": True,
        }

        params = json.loads(request.data) if request.data is not None else {}
        params.update(authentication_params)

        data_json = json.dumps(params, separators=(",", ":"))
        payload = base64.b64encode(data_json.encode("ascii"))
        signature = hmac.new(self.secret_key.encode("ascii"), payload, hashlib.sha512).hexdigest()

        header = request.headers or {}
        header.update(
            {
                "X-TXC-APIKEY": self.api_key,
                "X-TXC-PAYLOAD": payload.decode("ascii"),
                "X-TXC-SIGNATURE": signature,
            }
        )

        request.headers = header
        request.data = data_json

        return request
