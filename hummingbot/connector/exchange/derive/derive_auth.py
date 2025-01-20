import json
from datetime import datetime, timezone

# from collections import OrderedDict
from typing import Any, Dict, List

import eth_account
from eth_abi.abi import encode
from eth_account.messages import encode_defunct
from hexbytes import HexBytes
from web3 import Account, Web3

from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS, derive_web_utils as web_utils
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DeriveAuth(AuthBase):
    """
    Auth class required by Derive API
    """

    def __init__(self, api_key: str, api_secret: str, sub_id: int, trading_required: bool):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._sub_id: int = sub_id
        self._trading_required: bool = trading_required
        self._w3 = Web3()
        self.nonce = web_utils.get_action_nonce()
        self._signature = []
        if trading_required:
            self.session_key_wallet = Web3().eth.account.from_key(self._api_secret)

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(params=json.loads(request.data), request=request)
        else:
            request.params = self.add_auth_to_params_post(params=request.params, request=request)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    @property
    def domain_separator(self) -> bytes:
        try:
            return bytes.fromhex(CONSTANTS.DOMAIN_SEPARATOR[2:])
        except ValueError:
            raise ValueError(
                "Unable to extract bytes from DOMAIN_SEPARATOR. Ensure value is copied from Protocol Constants in docs.lyra.finance."
            )

    @property
    def action_typehash(self) -> bytes:
        try:
            return bytes.fromhex(CONSTANTS.ACTION_TYPEHASH[2:])
        except ValueError:
            raise ValueError(
                "Unable to extract bytes from ACTION_TYPEHASH. Ensure value is copied from Protocol Constants in docs.lyra.finance."
            )

    def get_ws_auth_payload(self) -> List[Dict[str, Any]]:
        payload = {}
        timestamp = str(self.utc_now_ms())
        signature = self._w3.eth.account.sign_message(
            encode_defunct(text=timestamp), private_key=self._api_secret
        ).signature.hex()
        """
        This method is intended to configure a websocket request to be authenticated. Dexalot does not use this
        functionality
        """
        payload["wallet"] = self._api_key
        payload["timestamp"] = timestamp
        payload["signature"] = signature
        return payload

    def add_auth_to_params_post(self, params: Dict[str, str], request):
        payload = {}
        data = params if params is not None else {}

        request_params = data

        if "type" in request_params:
            request_type = request_params.get("type")
            request_params.pop("type")
            if request_type == "order":
                self.sign(request_params)

            request_params.pop("asset_address")
            request_params.pop("sub_id")
            request_params = web_utils.order_to_call(request_params)
            payload = request_params.update(**self.to_json(request_params))
        else:
            payload.update(request_params)

        return json.dumps(payload) if request.method == RESTMethod.POST else payload

    # def sign(self, params):
    #     action = SignedAction(
    #         subaccount_id=30769,
    #         owner=CONSTANTS.SMART_CONTRACT_WALLET_ADDRESS,  # from Protocol Constants table in docs.lyra.finance
    #         signer=self.session_key_wallet.address,
    #         signature_expiry_sec=utils.MAX_INT_32,
    #         nonce=utils.get_action_nonce(),
    #         module_address=CONSTANTS.TRADE_MODULE_ADDRESS,  # from Protocol Constants table in docs.lyra.finance
    #         module_data=TradeModuleData(
    #             asset_address=params["asset_address"],
    #             sub_id=int(params["sub_id"]),
    #             limit_price=(Decimal(params["limit_price"])),
    #             amount=Decimal(params["amount"]),
    #             max_fee=Decimal(params["max_fee"]),
    #             recipient_id=int(params["recipient_id"]),
    #             is_bid=params["is_bid"],
    #         ),
    #         DOMAIN_SEPARATOR=CONSTANTS.DOMAIN_SEPARATOR,  # from Protocol Constants table in docs.derive.xyz
    #         ACTION_TYPEHASH=CONSTANTS.ACTION_TYPEHASH,  # from Protocol Constants table in docs.derive.xyz
    #     )
    #     action.sign(self.session_key_wallet.key)
    #     return action.to_json()

    def sign(self, params):
        signature = eth_account.Account.signHash(self._to_typed_data_hash(params))
        signature = signature.signature.hex()
        self._signature.append(signature)
        return signature

    def to_json(self, params):
        return {
            "subaccount_id": self._sub_id,
            "nonce": self.nonce,
            "signer": self.session_key_wallet.address,
            "signature_expiry_sec": web_utils.MAX_INT_32,
            "signature": self._signature[0],
            **web_utils.to_json(params),
        }

    def validate_signature(self):
        data_hash = self._to_typed_data_hash()
        recovered = Account._recover_hash(
            data_hash.hex(),
            signature=HexBytes(self.signature),
        )
        addr: str = eth_account.Account.from_key(self._api_secret).address

        if recovered.lower() != addr.lower():
            raise ValueError("Invalid signature. Recovered signer does not match expected signer.")

    def _to_typed_data_hash(self, order) -> HexBytes:
        encoded_typed_data_hash = "".join(["0x1901", CONSTANTS.DOMAIN_SEPARATOR[2:], self._get_action_hash(order).hex()])
        return Web3.keccak(hexstr=encoded_typed_data_hash)

    def _get_action_hash(self, order) -> HexBytes:
        addr = eth_account.Account.from_key(self._api_secret).address
        return Web3.keccak(
            encode(
                [
                    "bytes32",
                    "uint",
                    "uint",
                    "address",
                    "bytes32",
                    "uint",
                    "address",
                    "address",
                ],
                [
                    self.action_typehash,
                    int(self._sub_id),
                    self.nonce,
                    Web3.to_checksum_address(CONSTANTS.TRADE_MODULE_ADDRESS),
                    Web3.keccak(web_utils.to_abi_encoded(order)),
                    web_utils.MAX_INT_32,
                    Web3.to_checksum_address(addr),
                    Web3.to_checksum_address(self._api_key),
                ],
            )
        )

    def header_for_authentication(self) -> Dict[str, str]:
        timestamp = str(self.utc_now_ms())
        signature = self._w3.eth.account.sign_message(
            encode_defunct(text=timestamp), private_key=self._api_secret
        ).signature.hex()
        payload = {}

        payload["accept"] = 'application/json'
        payload["X-LyraWallet"] = self._api_key
        payload["X-LyraTimestamp"] = timestamp
        payload["X-LyraSignature"] = signature
        return payload

    @staticmethod
    def utc_now_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
