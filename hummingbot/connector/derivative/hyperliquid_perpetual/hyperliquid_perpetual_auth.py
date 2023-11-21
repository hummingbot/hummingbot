import hashlib
import hmac
import json
import time
import eth_account
from collections import OrderedDict
from typing import Any, Dict, List
from urllib.parse import urlparse
from eth_abi import encode
from eth_utils import keccak, to_hex
from eth_account.messages import encode_structured_data

# from hyperliquid.utils.types import Any, List, Literal, Meta, Optional, Tuple, Cloid

from hummingbot.connector.derivative.hyperliquid_perpetual import (
    hyperliquid_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils import order_type_to_tuple, \
    float_to_int_for_hashing, str_to_bytes16, order_grouping_to_number

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class HyperliquidPerpetualAuth(AuthBase):
    """
    Auth class required by Hyperliquid Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
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

    #
    # def generate_signature_from_payload(self, payload: str) -> str:
    #     secret = bytes(self._api_secret.encode("utf-8"))
    #     signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    #     return signature
    #
    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        # _path = urlparse(request.url).path
        base_url = request.endpoint_url
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(request.data, base_url)
        # else:
        #     request.params = self.add_auth_to_params(request.params, base_url)
        # request.headers = {"X-Bit-Access-Key": self._api_key}
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    #
    # def _encode_list(self, item_list):
    #     list_val = []
    #     for item in item_list:
    #         obj_val = self._encode_object(item)
    #         list_val.append(obj_val)
    #     sorted_list = sorted(list_val)
    #     output = '&'.join(sorted_list)
    #     output = '[' + output + ']'
    #     return output
    #
    # def _encode_object(self, param_map):
    #     sorted_keys = sorted(param_map.keys())
    #     ret_list = []
    #     for key in sorted_keys:
    #         val = param_map[key]
    #         if isinstance(val, list):
    #             list_val = self._encode_list(val)
    #             ret_list.append(f'{key}={list_val}')
    #         elif isinstance(val, dict):
    #             # call encode_object recursively
    #             dict_val = self._encode_object(val)
    #             ret_list.append(f'{key}={dict_val}')
    #         elif isinstance(val, bool):
    #             bool_val = str(val).lower()
    #             ret_list.append(f'{key}={bool_val}')
    #         else:
    #             general_val = str(val)
    #             ret_list.append(f'{key}={general_val}')
    #
    #     sorted_list = sorted(ret_list)
    #     output = '&'.join(sorted_list)
    #     return output
    #
    # def add_auth_to_params(self, params: Dict[str, Any], path):
    #     timestamp = int(self._get_timestamp() * 1e3)
    #
    #     request_params = OrderedDict(params or {})
    #     request_params.update({'timestamp': timestamp})
    #     str_to_sign = path + '&' + self._encode_object(request_params)
    #     request_params["signature"] = self.generate_signature_from_payload(payload=str_to_sign)
    #
    #     return request_params

    def _sign_update_leverage_params(self, params, base_url, timestamp):
        res = [
            params["asset"],
            params["isCross"],
            params["leverage"],
        ]
        signature_types = CONSTANTS.SIGNATURE_TYPE["updateLeverage"]
        signature = self.sign_l1_action(
            self.wallet,
            signature_types,
            res,
            ZERO_ADDRESS,
            timestamp,
            base_url == CONSTANTS.PERPETUAL_BASE_URL,
        )
        payload = {
            "action": params,
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": ZERO_ADDRESS,
        }
        return payload

    def _sign_cancel_params(self, params, base_url, timestamp):
        cancel = params["cancels"]
        res = (
            cancel["asset"],
            str_to_bytes16(cancel["cloid"])

        )
        signature_types = CONSTANTS.SIGNATURE_TYPE["cancel_by_cloid"]
        signature = self.sign_l1_action(
            self.wallet,
            signature_types,
            [[res]],
            ZERO_ADDRESS,
            timestamp,
            base_url == CONSTANTS.PERPETUAL_BASE_URL,
        )
        payload = {
            "action": {
                "type": "cancelByCloid",
                "cancels": [cancel],
            },
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": ZERO_ADDRESS,
        }
        return payload

    def _sign_order_params(self, params, base_url, timestamp):

        order = params["orders"]
        order_type_array = order_type_to_tuple(order["orderType"])
        grouping = params["grouping"]

        res = (
            order["asset"],
            order["isBuy"],
            float_to_int_for_hashing(order["limitPx"]),
            float_to_int_for_hashing(order["sz"]),
            order["reduceOnly"],
            order_type_array[0],
            float_to_int_for_hashing(order_type_array[1]),
            str_to_bytes16(order["cloid"])
        )
        signature_types = CONSTANTS.SIGNATURE_TYPE["orderl_by_cloid"]
        signature = self.sign_l1_action(
            self.wallet,
            signature_types,
            [[res], order_grouping_to_number(grouping)],
            ZERO_ADDRESS,
            timestamp,
            base_url == CONSTANTS.PERPETUAL_BASE_URL,
        )

        payload = {
            "action": {
                "type": "order",
                "grouping": grouping,
                "orders": [order],
            },
            "nonce": timestamp,
            "signature": signature,
            "vaultAddress": ZERO_ADDRESS,
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
        res = json.dumps(payload)
        return res

    @staticmethod
    def _get_timestamp():
        return time.time()
