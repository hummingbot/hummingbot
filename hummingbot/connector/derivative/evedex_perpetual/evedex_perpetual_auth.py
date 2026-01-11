import json
import time
from collections import OrderedDict
from typing import Any, Dict

import eth_account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class EvedexPerpetualAuth(AuthBase):
    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self.wallet = eth_account.Account.from_key(api_secret)

    @property
    def wallet_address(self) -> str:
        return self.wallet.address

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)

    def _normalize_number(self, value: float) -> int:
        return round(value * 10 ** 8)

    def _sign_typed_data(self, data: Dict[str, Any]) -> str:
        structured_data = encode_typed_data(full_message=data)
        signed = self.wallet.sign_message(structured_data)
        return signed.signature.hex()

    def sign_order(self, order_data: Dict[str, Any]) -> str:
        domain = {
            "name": "EVEDEX",
            "version": "1",
            "chainId": CONSTANTS.CHAIN_ID,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        }
        types = {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Order": [
                {"name": "market", "type": "string"},
                {"name": "side", "type": "string"},
                {"name": "type", "type": "string"},
                {"name": "price", "type": "uint256"},
                {"name": "quantity", "type": "uint256"},
                {"name": "timestamp", "type": "uint256"},
                {"name": "nonce", "type": "string"},
            ],
        }
        message = {
            "market": order_data["market"],
            "side": order_data["side"],
            "type": order_data["type"],
            "price": self._normalize_number(float(order_data.get("price", 0))),
            "quantity": self._normalize_number(float(order_data["quantity"])),
            "timestamp": order_data["timestamp"],
            "nonce": order_data["nonce"],
        }
        typed_data = {
            "domain": domain,
            "types": types,
            "primaryType": "Order",
            "message": message,
        }
        return self._sign_typed_data(typed_data)

    def sign_cancel(self, cancel_data: Dict[str, Any]) -> str:
        domain = {
            "name": "EVEDEX",
            "version": "1",
            "chainId": CONSTANTS.CHAIN_ID,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        }
        types = {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Cancel": [
                {"name": "orderId", "type": "string"},
                {"name": "timestamp", "type": "uint256"},
            ],
        }
        message = {
            "orderId": cancel_data["orderId"],
            "timestamp": cancel_data["timestamp"],
        }
        typed_data = {
            "domain": domain,
            "types": types,
            "primaryType": "Cancel",
            "message": message,
        }
        return self._sign_typed_data(typed_data)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["X-API-KEY"] = self._api_key
        request.headers["X-WALLET-ADDRESS"] = self.wallet_address

        if request.method == RESTMethod.POST and request.data:
            data = json.loads(request.data) if isinstance(request.data, str) else request.data
            if "market" in data and "side" in data:
                data["timestamp"] = self._get_timestamp()
                data["signature"] = self.sign_order(data)
                request.data = json.dumps(data)
            elif "orderId" in data:
                data["timestamp"] = self._get_timestamp()
                data["signature"] = self.sign_cancel(data)
                request.data = json.dumps(data)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        timestamp = self._get_timestamp()
        message = f"{self.wallet_address}:{timestamp}"
        signature = self.wallet.sign_message(
            eth_account.messages.encode_defunct(text=message)
        ).signature.hex()
        return {
            "apiKey": self._api_key,
            "address": self.wallet_address,
            "timestamp": timestamp,
            "signature": signature,
        }
