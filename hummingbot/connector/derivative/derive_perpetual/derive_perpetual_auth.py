import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from eth_account.messages import encode_defunct
from web3 import Web3

from hummingbot.connector.derivative.derive_perpetual import (
    derive_perpetual_constants as CONSTANTS,
    derive_perpetual_web_utils as web_utils,
)
from hummingbot.connector.other.derive_common_utils import (
    RESTING_ORDER_VALIDITY_SEC,
    SignedAction,
    TradeModuleData,
    get_action_nonce,
    get_order_signature_expiry_sec,
    parse_subaccount_id,
)
from hummingbot.connector.utils import to_0x_hex
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DerivePerpetualAuth(AuthBase):
    """
    Auth class required by DerivePerpetual API
    """

    def __init__(self, wallet_address: str, session_private_key: str, subacct_id: int, trading_required: bool, domain: str):
        self._wallet_address: str = wallet_address
        self._session_private_key: str = session_private_key
        # Credentials arrive as strings, and most v3 routes refuse one where an integer is declared.
        self._subacct_id: Optional[int] = parse_subaccount_id(subacct_id)
        self._trading_required: bool = trading_required
        self._w3 = Web3()
        self._domain = domain
        # The session key's own expiry, set by the connector once it has looked the key up. None
        # until then, and for an owner wallet signing directly, which has no expiry.
        self.session_key_expiry_sec: Optional[int] = None
        if trading_required:
            self.session_key_wallet = Web3().eth.account.from_key(self._session_private_key)

    @property
    def signer_address(self) -> Optional[str]:
        """
        The address of the key that signs every request, or None when no usable key is configured.
        Unlike session_key_wallet it does not depend on trading being required, which `connect`
        leaves off.
        """
        try:
            return Web3().eth.account.from_key(self._session_private_key).address
        except Exception:
            return None

    @property
    def _is_testnet(self) -> bool:
        return "testnet" in self._domain

    @property
    def domain_separator(self) -> str:
        return CONSTANTS.TESTNET_DOMAIN_SEPARATOR if self._is_testnet else CONSTANTS.DOMAIN_SEPARATOR

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Derive
        authenticates the connection once via public/login rather than per request.
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

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Builds the params for the websocket ``public/login`` call.

        v3 takes ``{wallet, timestamp, signature}`` with the timestamp as a JSON *number* of
        milliseconds; the v2 shape sent it as a string alongside an ``accept`` field.
        """
        timestamp = self.utc_now_ms()
        signature = to_0x_hex(self._w3.eth.account.sign_message(
            encode_defunct(text=str(timestamp)), private_key=self._session_private_key
        ).signature)

        return {
            "wallet": self._wallet_address,
            "timestamp": timestamp,
            "signature": signature,
        }

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
        # v3 expires an order when its signature does, whatever its time in force. An order that
        # can rest is therefore signed for as long as the API allows, so that it lives until it is
        # filled or cancelled; one that cannot rest only has to outlive the request.
        can_rest = (
            params.get("order_type") == "limit"
            and params.get("time_in_force") in CONSTANTS.RESTING_TIME_IN_FORCE
        )
        action = SignedAction(
            subaccount_id=self._subacct_id,
            owner=self._wallet_address,
            signer=self.session_key_wallet.address,
            # v3 rejects the v2 habit of sending 2**31-1 (error 11011), and an action may not
            # outlive the session key that signed it (14038).
            signature_expiry_sec=get_order_signature_expiry_sec(
                RESTING_ORDER_VALIDITY_SEC if can_rest else CONSTANTS.SIGNATURE_VALIDITY_SEC,
                self.session_key_expiry_sec,
            ),
            # UTC nanoseconds, serialized as a string by SignedAction.to_json().
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
            DOMAIN_SEPARATOR=self.domain_separator,
            ACTION_TYPEHASH=CONSTANTS.ACTION_TYPEHASH,
        )
        try:
            action.sign(self.session_key_wallet.key)
        except Exception as e:
            raise Exception(f"Error signing action: {e}")

        return action.to_json()

    def header_for_authentication(self) -> Dict[str, str]:
        timestamp = str(self.utc_now_ms())
        signature = to_0x_hex(self._w3.eth.account.sign_message(
            encode_defunct(text=timestamp), private_key=self._session_private_key
        ).signature)

        return {
            "accept": "application/json",
            # v3 renamed the X-Lyra* headers, and rejects any REST request with no User-Agent.
            "User-Agent": CONSTANTS.USER_AGENT,
            "X-DeriveWallet": self._wallet_address,
            "X-DeriveTimestamp": timestamp,
            "X-DeriveSignature": signature,
        }

    @staticmethod
    def utc_now_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
