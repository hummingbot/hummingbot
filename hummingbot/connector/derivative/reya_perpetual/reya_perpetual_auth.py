import json
import time
from decimal import Decimal
from urllib.parse import urlparse

from eth_account import Account
from eth_utils import keccak

from hummingbot.connector.derivative.reya_perpetual import reya_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

ORDER_FIELDS = [
    ("accountId", "uint128"), ("marketId", "uint128"), ("exchangeId", "uint128"), ("orderType", "uint8"),
    ("quantity", "int256"), ("limitPrice", "uint256"), ("triggerPrice", "uint256"), ("timeInForce", "uint8"),
    ("clientOrderId", "uint64"), ("reduceOnly", "bool"), ("postOnly", "bool"), ("expiresAfter", "uint256"),
    ("signer", "address"), ("nonce", "uint256"),
]


def wire_client_id(client_order_id: str) -> str:
    # Stable across restarts; the full Hummingbot id stays in persisted tracking state.
    return str(int.from_bytes(keccak(text=client_order_id)[:8], "big") or 1)


def scale_e18(value: Decimal) -> int:
    # Integer arithmetic avoids Decimal's default 28-digit context rounding large values.
    if not value.is_finite() or value <= 0:
        raise ValueError("Quantity and price must be finite and positive")
    numerator, denominator = value.as_integer_ratio()
    scaled, remainder = divmod(numerator * 10**18, denominator)
    if remainder:
        raise ValueError("Quantity and price exceed 18 decimal places")
    return scaled


class ReyaPerpetualAuth(AuthBase):
    def __init__(self, private_key, market_ids, domain=CONSTANTS.DEFAULT_DOMAIN):
        self._wallet = Account.from_key(private_key)
        self._market_ids = market_ids
        self._chain_id = CONSTANTS.CHAIN_IDS[domain]
        self._domain = {"name": "Reya", "version": "1", "verifyingContract": CONSTANTS.ORDERS_GATEWAYS[domain]}
        self._last_nonce = 0

    @property
    def signer_address(self) -> str:
        return self._wallet.address

    def nonce(self):
        self._last_nonce = max(time.time_ns() // 1000, self._last_nonce + 1)
        return self._last_nonce

    def sign_payload(self, path, payload):
        data = dict(payload)
        nonce = int(data.get("nonce", self.nonce()))
        deadline = int(data.get("deadline", int(time.time()) + CONSTANTS.SIGNATURE_DEADLINE))
        market_id = self._market_ids[data["symbol"]] if data.get("symbol") else 0
        if path == "createOrder":
            if data.get("orderType") != "LIMIT":
                raise ValueError("Only LIMIT order signatures are supported")
            quantity = Decimal(data["qty"])
            price = Decimal(data["limitPx"])
            scaled_qty, scaled_price = scale_e18(quantity), scale_e18(price)
            envelope, member, detail_type, width = "Order", "order", "OrderDetails", "uint256"
            fields = ORDER_FIELDS
            detail = {
                "accountId": int(data["accountId"]), "marketId": market_id, "exchangeId": int(data["exchangeId"]),
                "orderType": 0, "quantity": int(scaled_qty) * (1 if data["isBuy"] else -1),
                "limitPrice": int(scaled_price), "triggerPrice": 0,
                "timeInForce": {"GTC": 0, "IOC": 1, "GTT": 2}[data["timeInForce"]],
                "clientOrderId": int(data.get("clientOrderId", 0)), "reduceOnly": data.get("reduceOnly", False),
                "postOnly": data.get("postOnly", False), "expiresAfter": int(data.get("expiresAfter", 0)),
                "signer": self._wallet.address, "nonce": nonce,
            }
            data["signerWallet"] = self._wallet.address
        elif path in ("cancelOrder", "cancelAll"):
            width = "uint64"
            detail = {"accountId": int(data["accountId"]), "marketId": market_id}
            if path == "cancelOrder":
                envelope, member, detail_type = "OrderCancel", "cancel", "OrderCancelDetails"
                detail.update(orderId=int(data.get("orderId", 0)), clOrdId=int(data.get("clientOrderId", 0)))
            else:
                envelope, member, detail_type = "MassCancel", "massCancel", "MassCancelDetails"
            detail["nonce"] = nonce
            fields = [(field, "uint64") for field in detail]
        else:
            raise ValueError(f"Unsupported signed endpoint: {path}")
        types = {
            envelope: [{"name": "verifyingChainId", "type": width}, {"name": "deadline", "type": width},
                       {"name": member, "type": detail_type}],
            detail_type: [{"name": name, "type": kind} for name, kind in fields],
        }
        message = {"verifyingChainId": self._chain_id, "deadline": deadline, member: detail}
        signed = self._wallet.sign_typed_data(self._domain, types, message)
        data.update(signature="0x" + signed.signature.hex().removeprefix("0x"), nonce=str(nonce), deadline=deadline)
        return data

    async def rest_authenticate(self, request):
        if request.method != RESTMethod.POST:
            return request
        path = urlparse(request.url).path.rsplit("/", 1)[-1]
        payload = json.loads(request.data) if isinstance(request.data, str) else request.data
        request.data = json.dumps(self.sign_payload(path, payload))
        return request

    async def ws_authenticate(self, request):
        # Wallet data is public; only order entry requires a signature.
        return request
