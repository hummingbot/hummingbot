import json
import time
from collections import OrderedDict

import eth_account
from eth_abi import encode
from eth_account.messages import encode_structured_data
from eth_utils import keccak, to_hex

from hummingbot.connector.derivative.hyperliquid_perpetual import hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils import (
    float_to_int_for_hashing,
    order_grouping_to_number,
    order_spec_to_order_wire,
    order_type_to_tuple,
    str_to_bytes16,
)
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class HyperliquidPerpetualAuth(AuthBase):
    """
    Auth class required by Hyperliquid Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str, use_vault: bool):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._use_vault: bool = use_vault
        self.wallet = eth_account.Account.from_key(api_secret)

    def sign_inner(self, wallet, data):
        structured_data = encode_structured_data(data)
        signed = wallet.sign_message(structured_data)
        return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}

    def construct_phantom_agent(self, signature_types, signature_data, is_mainnet):
        connection_id = encode(signature_types, signature_data)
        return {"source": "a" if is_mainnet else "b", "connectionId": keccak(connection_id)}

    def sign_l1_action(self, wallet, signature_types, signature_data, active_pool, nonce, is_mainnet):
        signature_types.append("address")
        signature_types.append("uint64")
        if active_pool is None:
            signature_data.append(ZERO_ADDRESS)
        else:
            signature_data.append(active_pool)
        signature_data.append(nonce)

        phantom_agent = self.construct_phantom_agent(signature_types, signature_data, is_mainnet)

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
        res = [
            params["asset"],
            params["isCross"],
            params["leverage"],
        ]
        signature_types = ["uint32", "bool", "uint32"]
        signature = self.sign_l1_action(
            self.wallet,
            signature_types,
            res,
            ZERO_ADDRESS if not self._use_vault else self._api_key,
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
        cancel = params["cancels"]
        res = (
            cancel["asset"],
            str_to_bytes16(cancel["cloid"])

        )
        signature_types = ["(uint32,bytes16)[]"]
        signature = self.sign_l1_action(
            self.wallet,
            signature_types,
            [[res]],
            ZERO_ADDRESS if not self._use_vault else self._api_key,
            timestamp,
            CONSTANTS.PERPETUAL_BASE_URL in base_url,
        )
        payload = {
            "action": {
                "type": "cancelByCloid",
                "cancels": [cancel],
            },
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": self._api_key if self._use_vault else None,

        }
        return payload

    def _sign_order_params(self, params, base_url, timestamp):

        order = params["orders"]
        order_type_array = order_type_to_tuple(order["orderType"])
        grouping = params["grouping"]

        res = (
            order["asset"],
            order["isBuy"],
            float_to_int_for_hashing(float(order["limitPx"])),
            float_to_int_for_hashing(float(order["sz"])),
            order["reduceOnly"],
            order_type_array[0],
            float_to_int_for_hashing(float(order_type_array[1])),
            str_to_bytes16(order["cloid"])
        )
        signature_types = ["(uint32,bool,uint64,uint64,bool,uint8,uint64,bytes16)[]", "uint8"]
        signature = self.sign_l1_action(
            self.wallet,
            signature_types,
            [[res], order_grouping_to_number(grouping)],
            ZERO_ADDRESS if not self._use_vault else self._api_key,
            timestamp,
            CONSTANTS.PERPETUAL_BASE_URL in base_url,
        )

        payload = {
            "action": {
                "type": "order",
                "grouping": grouping,
                "orders": [order_spec_to_order_wire(order)],
            },
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
