import json
import threading
import time
from collections import OrderedDict
from typing import Any

import eth_account
import msgpack
from eth_account.messages import encode_typed_data
from eth_utils import keccak, to_hex

from hummingbot.connector.exchange.hyperliquid import hyperliquid_constants as CONSTANTS
from hummingbot.connector.exchange.hyperliquid.hyperliquid_web_utils import order_spec_to_order_wire
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class HyperliquidAuth(AuthBase):
    """
    Auth class required by Hyperliquid API with centralized, collision-free nonce generation.
    """

    def __init__(
        self,
        api_address: str,
        api_secret: str,
        use_vault: bool
    ):
        # can be as Arbitrum wallet address or Vault address
        self._api_address: str = api_address
        # can be as Arbitrum wallet private key or Hyperliquid API wallet private key
        self._api_secret: str = api_secret
        self._vault_address = api_address if use_vault else None
        self.wallet = eth_account.Account.from_key(api_secret)
        # one nonce manager per connector instance (shared by orders/cancels/updates)
        self._nonce = _NonceManager()

    @classmethod
    def address_to_bytes(cls, address: str) -> bytes:
        """
        Converts an Ethereum address to bytes.
        """
        return bytes.fromhex(address[2:] if address.startswith("0x") else address)

    @classmethod
    def action_hash(cls, action, vault_address: str, nonce: int):
        """
        Computes the hash of an action.
        """
        data = msgpack.packb(action)
        data += int(nonce).to_bytes(8, "big")  # ensure int, 8-byte big-endian
        if vault_address is None:
            data += b"\x00"
        else:
            data += b"\x01"
            data += cls.address_to_bytes(vault_address)

        return keccak(data)

    def sign_inner(self, wallet, data):
        """
        Signs a request.
        """
        structured_data = encode_typed_data(full_message=data)
        signed = wallet.sign_message(structured_data)

        return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}

    def construct_phantom_agent(self, hash_iterable: bytes, is_mainnet: bool) -> dict[str, Any]:
        """
        Constructs a phantom agent.
        """
        return {"source": "a" if is_mainnet else "b", "connectionId": hash_iterable}

    def sign_l1_action(
        self,
        wallet,
        action: dict[str, Any],
        active_pool,
        nonce: int,
        is_mainnet: bool
    ) -> dict[str, Any]:
        """
        Signs a L1 action.
        """
        _hash = self.action_hash(action, active_pool, nonce)
        phantom_agent = self.construct_phantom_agent(_hash, is_mainnet)

        data = {
            "domain": {
                "chainId": 1337,
                "name": "Exchange",
                "verifyingContract": "0x0000000000000000000000000000000000000000",
                "version": "1",
            },
            "types": {
                "Agent": [
                    {"name": "source", "type": "string"},
                    {"name": "connectionId", "type": "bytes32"},
                ],
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
            },
            "primaryType": "Agent",
            "message": phantom_agent,
        }

        return self.sign_inner(wallet, data)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        base_url = request.url
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(request.data, base_url)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    def _sign_update_leverage_params(self, params, base_url: str, nonce_ms: int) -> dict[str, Any]:
        signature = self.sign_l1_action(
            self.wallet,
            params,
            self._vault_address,
            nonce_ms,
            CONSTANTS.BASE_URL in base_url,
        )

        return {
            "action": params,
            "nonce": nonce_ms,
            "signature": signature,
            "vaultAddress": self._vault_address,
        }

    def _sign_cancel_params(self, params, base_url: str, nonce_ms: int):
        order_action = {
            "type": "cancelByCloid",
            "cancels": [params["cancels"]],
        }
        signature = self.sign_l1_action(
            self.wallet,
            order_action,
            self._vault_address,
            nonce_ms,
            CONSTANTS.BASE_URL in base_url,
        )

        return {
            "action": order_action,
            "nonce": nonce_ms,
            "signature": signature,
            "vaultAddress": self._vault_address,
        }

    def _sign_order_params(
        self,
        params: OrderedDict,
        base_url: str,
        nonce_ms: int
    ) -> dict[str, Any]:
        order = params["orders"]
        grouping = params["grouping"]
        order_action = {
            "type": "order",
            "orders": [order_spec_to_order_wire(order)],
            "grouping": grouping,
        }
        signature = self.sign_l1_action(
            self.wallet,
            order_action,
            self._vault_address,
            nonce_ms,
            CONSTANTS.BASE_URL in base_url,
        )

        return {
            "action": order_action,
            "nonce": nonce_ms,
            "signature": signature,
            "vaultAddress": self._vault_address,
        }

    def add_auth_to_params_post(self, params: str, base_url: str) -> str:
        """
        Adds authentication to a request.
        """
        nonce_ms = self._nonce.next_ms()
        data = json.loads(params) if params is not None else {}
        request_params = OrderedDict(data or {})

        request_type = request_params.get("type")
        if request_type == "order":
            payload = self._sign_order_params(request_params, base_url, nonce_ms)
        elif request_type == "cancel":
            payload = self._sign_cancel_params(request_params, base_url, nonce_ms)
        elif request_type == "updateLeverage":
            payload = self._sign_update_leverage_params(request_params, base_url, nonce_ms)
        else:
            payload = {"action": request_params, "nonce": nonce_ms}

        return json.dumps(payload)

    # ---------- agent registration (ApproveAgent) ----------

    def sign_user_signed_action(
        self,
        wallet,
        action: dict[str, Any],
        payload_types: list[dict[str, str]],
        primary_type: str,
        is_mainnet: bool,
    ) -> dict[str, Any]:
        """
        Signs a user-signed action.
        """
        domain = {
            "name": "HyperliquidSignTransaction",
            "version": "1",
            "chainId": 42161 if is_mainnet else 421614,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        }

        types = {
            primary_type: payload_types
        }

        data = {
            "domain": domain,
            "types": types,
            "primaryType": primary_type,
            "message": action,
        }

        return self.sign_inner(wallet, data)

    def approve_agent(
        self,
        base_url: str,
    ) -> dict[str, Any]:
        """
        Registers an API wallet (agent) under the master wallet using ApproveAgent.
        Returns API response dict.
        """
        nonce_ms = self._nonce.next_ms()
        is_mainnet = CONSTANTS.BASE_URL in base_url
        action = {
            "type": "approveAgent",
            "hyperliquidChain": 'Mainnet' if is_mainnet else 'Testnet',
            "signatureChainId": '0xa4b1' if is_mainnet else '0x66eee',
            "agentAddress": self._api_address,
            "agentName": CONSTANTS.DEFAULT_AGENT_NAME,
            "nonce": nonce_ms,
        }

        payload_types = [
            {"name": "hyperliquidChain", "type": "string"},
            {"name": "agentAddress", "type": "address"},
            {"name": "agentName", "type": "string"},
            {"name": "nonce", "type": "uint64"},
        ]

        signature = self.sign_user_signed_action(
            self.wallet,
            action,
            payload_types,
            "HyperliquidTransaction:ApproveAgent",
            is_mainnet,
        )

        return {
            "action": action,
            "nonce": nonce_ms,
            "signature": signature,
        }


class _NonceManager:
    """
    Generates strictly increasing epoch-millisecond nonces, safe for concurrent use.
    Prevents collisions when multiple coroutines/threads sign in the same millisecond.
    """

    def __init__(self):
        # start at current ms
        self._last = int(time.time() * 1000)
        self._lock = threading.Lock()

    def next_ms(self) -> int:
        now = int(time.time() * 1000)
        with self._lock:
            if now <= self._last:
                # bump by 1 to ensure strict monotonicity
                now = self._last + 1
            self._last = now
            return now
