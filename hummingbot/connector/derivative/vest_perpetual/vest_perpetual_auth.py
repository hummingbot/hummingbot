import json
from typing import Any, Dict
from urllib.parse import urlparse

from eth_abi import encode as abi_encode
from eth_account import Account as EthAccount
from eth_account.messages import encode_defunct
from eth_utils import keccak

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class VestPerpetualAuth(AuthBase):
    """Auth class required by Vest Perpetual API.

    According to Vest docs, private REST requests must include:
      * X-API-KEY header with the API key
      * xrestservermm header with the account group (restserver{accGroup})
      * For POST /orders (and similar endpoints), a signature over the order fields.
    """

    def __init__(self, api_key: str, signing_private_key: str, account_group: int):
        self._api_key = api_key
        self._signing_private_key = signing_private_key
        self._account_group = account_group

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """Attach required headers and, for specific endpoints, a body signature."""
        headers = request.headers or {}
        headers.update(self.header_for_authentication())
        request.headers = headers

        if request.method == RESTMethod.POST:
            parsed = urlparse(request.url)
            path = parsed.path or ""

            # Sign order placement requests: POST /orders
            if path.endswith("/orders"):
                data_dict = self._ensure_json_dict(request.data)
                order = data_dict.get("order") or {}
                signature = self._generate_orders_signature(order)
                data_dict["signature"] = signature
                request.data = json.dumps(data_dict)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """Vest private websockets use listenKey in the URL; no extra auth payload required here."""
        return request

    def header_for_authentication(self) -> Dict[str, str]:
        """Base headers required for all private REST/WS calls."""
        return {
            "X-API-KEY": self._api_key,
            "xrestservermm": f"restserver{self._account_group}",
        }

    @staticmethod
    def _ensure_json_dict(data: Any) -> Dict[str, Any]:
        if data is None:
            return {}
        if isinstance(data, str):
            return json.loads(data) if data else {}
        if isinstance(data, dict):
            return dict(data)
        # Fallback: try JSON-serialize other types
        return json.loads(json.dumps(data))

    def _generate_orders_signature(self, order: Dict[str, Any]) -> str:
        """Generate the signature for POST /orders as specified in Vest docs.

        The signed payload is:
            keccak(encode([
                "uint256", "uint256", "string", "string", "bool", "string", "string", "bool"
            ], [time, nonce, orderType, symbol, isBuy, size, limitPrice, reduceOnly]))
        """
        args_hash = keccak(
            abi_encode(
                [
                    "uint256",
                    "uint256",
                    "string",
                    "string",
                    "bool",
                    "string",
                    "string",
                    "bool",
                ],
                [
                    int(order["time"]),
                    int(order["nonce"]),
                    str(order["orderType"]),
                    str(order["symbol"]),
                    bool(order["isBuy"]),
                    str(order["size"]),
                    str(order["limitPrice"]),
                    bool(order["reduceOnly"]),
                ],
            )
        )
        signable_msg = encode_defunct(args_hash)
        signature = EthAccount.sign_message(signable_msg, self._signing_private_key).signature.hex()
        return signature

