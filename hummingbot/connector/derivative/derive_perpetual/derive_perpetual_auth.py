import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from eth_account.messages import encode_defunct
from web3 import Web3

from hummingbot.connector.derivative.derive_perpetual import (
    derive_perpetual_constants as CONSTANTS,
    derive_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_web_utils import MAX_INT_32, get_action_nonce
from hummingbot.connector.other.derive_common_utils import SignedAction, TradeModuleData
from hummingbot.connector.utils import to_0x_hex
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DerivePerpetualAuth(AuthBase):
    """
    Auth class required by DerivePerpetual API
    """

    def __init__(self, api_key: str, api_secret: str, sub_id: int, trading_required: bool, domain: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._sub_id: int = sub_id
        self._trading_required: bool = trading_required
        self._w3 = Web3()
        self._domain = domain
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

    def get_ws_auth_payload(self) -> List[Dict[str, Any]]:
        payload = {}
        timestamp = str(self.utc_now_ms())
        signature = to_0x_hex(self._w3.eth.account.sign_message(
            encode_defunct(text=timestamp), private_key=self._api_secret
        ).signature)
        """
        This method is intended to configure a websocket request to be authenticated. Dexalot does not use this
        functionality
        """
        payload["accept"] = 'application/json'
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
                action = self.sign(request_params)
            request_params = web_utils.order_to_call(request_params)
            request_params.update(action)
            payload.update(request_params)
        else:
            payload.update(request_params)

        return json.dumps(payload) if request.method == RESTMethod.POST else payload

    def sign(self, params):
        domain_seperator = CONSTANTS.DOMAIN_SEPARATOR if "testnet" not in self._domain else CONSTANTS.TESTNET_DOMAIN_SEPARATOR
        action_typehash = CONSTANTS.ACTION_TYPEHASH if "testnet" not in self._domain else CONSTANTS.TESTNET_ACTION_TYPEHASH
        action = SignedAction(
            subaccount_id=int(self._sub_id),
            owner=self._api_key,
            signer=self.session_key_wallet.address,
            signature_expiry_sec=MAX_INT_32,
            nonce=get_action_nonce(),
            module_address=CONSTANTS.TRADE_MODULE_ADDRESS,
            module_data=TradeModuleData(
                asset_address=params["asset_address"],
                sub_id=int(params["sub_id"]),
                limit_price=(Decimal(params["limit_price"])),
                amount=Decimal(params["amount"]),
                max_fee=Decimal(params["max_fee"]),
                recipient_id=int(params["recipient_id"]),
                is_bid=params["is_bid"],
            ),
            DOMAIN_SEPARATOR=domain_seperator,  # from Protocol Constants table in docs.derive_perpetual.xyz
            ACTION_TYPEHASH=action_typehash,  # from Protocol Constants table in docs.derive_perpetual.xyz
        )
        try:
            action.sign(self.session_key_wallet.key)
        except Exception as e:
            raise Exception(f"Error signing action: {e}")

        return action.to_json()

    def header_for_authentication(self) -> Dict[str, str]:
        timestamp = str(self.utc_now_ms())
        signature = to_0x_hex(self._w3.eth.account.sign_message(
            encode_defunct(text=timestamp), private_key=self._api_secret
        ).signature)
        payload = {}

        payload["accept"] = 'application/json'
        payload["X-LyraWallet"] = self._api_key
        payload["X-LyraTimestamp"] = timestamp
        payload["X-LyraSignature"] = signature
        return payload

    @staticmethod
    def utc_now_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
