import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import urlparse

import eth_account
from eth_account.messages import encode_typed_data
from eth_utils import to_hex
from yarl import URL

from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class AevoPerpetualAuth(AuthBase):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        signing_key: str,
        account_address: str,
        domain: str,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._signing_key = signing_key
        self._account_address = account_address
        self._domain = domain
        self._wallet = eth_account.Account.from_key(signing_key)

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def api_secret(self) -> str:
        return self._api_secret

    @property
    def account_address(self) -> str:
        return self._account_address

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        timestamp = str(int(time.time() * 1e9))
        if request.url is None:
            raise ValueError("Request URL is required for Aevo authentication.")
        parsed_url = urlparse(request.url)
        path = parsed_url.path
        body = ""

        if request.method in [RESTMethod.GET, RESTMethod.DELETE] and request.params:
            sorted_params = [(str(k), str(v)) for k, v in sorted(request.params.items(), key=lambda item: item[0])]
            request.params = sorted_params
        elif parsed_url.query:
            path = URL(request.url).raw_path_qs
        elif request.data is not None:
            if isinstance(request.data, (dict, list)):
                request.data = json.dumps(request.data)
            else:
                body = str(request.data)

        payload = f"{self._api_key},{timestamp},{request.method.value.upper()},{path},{body}"
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = request.headers or {}
        headers.update({
            "AEVO-TIMESTAMP": timestamp,
            "AEVO-SIGNATURE": signature,
            "AEVO-KEY": self._api_key,
        })
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        return {
            "op": "auth",
            "data": {
                "key": self._api_key,
                "secret": self._api_secret,
            },
        }

    def sign_order(
        self,
        is_buy: bool,
        limit_price: int,
        amount: int,
        salt: int,
        instrument: int,
        timestamp: int,
    ) -> str:
        domain = {
            "name": "Aevo Mainnet" if self._domain == CONSTANTS.DEFAULT_DOMAIN else "Aevo Testnet",
            "version": "1",
            "chainId": 1 if self._domain == CONSTANTS.DEFAULT_DOMAIN else 11155111,
        }
        types = {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "Order": [
                {"name": "maker", "type": "address"},
                {"name": "isBuy", "type": "bool"},
                {"name": "limitPrice", "type": "uint256"},
                {"name": "amount", "type": "uint256"},
                {"name": "salt", "type": "uint256"},
                {"name": "instrument", "type": "uint256"},
                {"name": "timestamp", "type": "uint256"},
            ],
        }
        message = {
            "maker": self._account_address,
            "isBuy": is_buy,
            "limitPrice": int(limit_price),
            "amount": int(amount),
            "salt": int(salt),
            "instrument": int(instrument),
            "timestamp": int(timestamp),
        }
        typed_data = {
            "domain": domain,
            "types": types,
            "primaryType": "Order",
            "message": message,
        }
        encoded = encode_typed_data(full_message=typed_data)
        signed = self._wallet.sign_message(encoded)

        return to_hex(signed.signature)
