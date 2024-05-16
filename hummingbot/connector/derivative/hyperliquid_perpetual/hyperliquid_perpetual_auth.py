import json
import time
from collections import OrderedDict

import eth_account
import msgpack
from eth_account.messages import encode_structured_data
from eth_utils import keccak, to_hex

from hummingbot.connector.derivative.hyperliquid_perpetual import hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils import (
    order_spec_to_order_wire,
)
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class HyperliquidPerpetualAuth(AuthBase):
    """
    Auth class required by Hyperliquid Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str, use_vault: bool):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._use_vault: bool = use_vault
        self.wallet = eth_account.Account.from_key(api_secret)

    @classmethod
    def address_to_bytes(cls, address):
        return bytes.fromhex(address[2:] if address.startswith("0x") else address)

    @classmethod
    def action_hash(cls, action, vault_address, nonce):
        data = msgpack.packb(action)
        data += nonce.to_bytes(8, "big")
        if vault_address is None:
            data += b"\x00"
        else:
            data += b"\x01"
            data += cls.address_to_bytes(vault_address)
        return keccak(data)

    def sign_inner(self, wallet, data):
        structured_data = encode_structured_data(data)
        signed = wallet.sign_message(structured_data)
        return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}

    def construct_phantom_agent(self, hash, is_mainnet):
        return {"source": "a" if is_mainnet else "b", "connectionId": hash}

    def sign_l1_action(self, wallet, action, active_pool, nonce, is_mainnet):
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

    def _sign_update_leverage_params(self, params, base_url, timestamp):
        signature = self.sign_l1_action(
            self.wallet,
            params,
            None if not self._use_vault else self._api_key,
            timestamp,
            CONSTANTS.PERPETUAL_BASE_URL in base_url,
        )
        payload = {
            "action": params,
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": self._api_key if self._use_vault else None,
        }
        return payload

    def _sign_cancel_params(self, params, base_url, timestamp):
        order_action = {
            "type": "cancelByCloid",
            "cancels": [params["cancels"]],
        }
        signature = self.sign_l1_action(
            self.wallet,
            order_action,
            None if not self._use_vault else self._api_key,
            timestamp,
            CONSTANTS.PERPETUAL_BASE_URL in base_url,
        )
        payload = {
            "action": order_action,
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": self._api_key if self._use_vault else None,

        }
        return payload

    def _sign_order_params(self, params, base_url, timestamp):

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
            None if not self._use_vault else self._api_key,
            timestamp,
            CONSTANTS.PERPETUAL_BASE_URL in base_url,
        )

        payload = {
            "action": order_action,
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": self._api_key if self._use_vault else None,

        }
        return payload

    def add_auth_to_params_post(self, params: str, base_url):
        timestamp = int(self._get_timestamp() * 1e3)
        payload = {}
        data = json.loads(params) if params is not None else {}

        request_params = OrderedDict(data or {})

        request_type = request_params.get("type")
        if request_type == "order":
            payload = self._sign_order_params(request_params, base_url, timestamp)
        elif request_type == "cancel":
            payload = self._sign_cancel_params(request_params, base_url, timestamp)
        elif request_type == "updateLeverage":
            payload = self._sign_update_leverage_params(request_params, base_url, timestamp)
        payload = json.dumps(payload)
        return payload

    @staticmethod
    def _get_timestamp():
        return time.time()
