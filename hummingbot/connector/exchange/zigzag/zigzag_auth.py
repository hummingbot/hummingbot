from datetime import datetime
import hashlib
import hmac
import json
from collections import OrderedDict
from time import time
from typing import Any, List, Dict
from urllib.parse import urlencode
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class ZigzagAuth(AuthBase):
    def __init__(self, chain_id: str, wallet: str, passphrase: str, time_provider: TimeSynchronizer):
        self.chain_id = chain_id
        self.wallet = wallet
        self.passphrase = passphrase
        self.time_provider = time_provider
        self._time = time

    def add_auth_to_params(self,
                           params: Dict[str, Any]):
        request_params = OrderedDict(params or {})
        return request_params

    def _get_auth_headers():
        return {
            "User-Agent": "hummingbot"
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        No REST authentication functionality for ZigZag
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self._get_auth_headers(request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Zigzag does not use this
        functionality
        """
        time_now = self._time()
        tag = datetime.utcfromtimestamp(int(time_now)).isoformat()
        timestamp = int(time_now * 1e3)

        request.payload = {
            "op": "login",
            "args": [
                self.chain_id,
                self.wallet,
            ]
        }

        return request  # pass-through

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        encoded_params_str = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"), encoded_params_str.encode("utf8"), hashlib.sha256).hexdigest()
        return digest

    def websocket_login_parameters(self) -> List[str]:
        return [
            self.chain_id,
            self.zksync_address,
        ]
