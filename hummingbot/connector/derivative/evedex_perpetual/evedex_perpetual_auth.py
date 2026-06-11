import time
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from eth_account import Account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

# EIP-712 Type Schemas
EIP712_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "salt", "type": "bytes32"},
    ],
    "New limit order": [
        {"name": "id", "type": "string"},
        {"name": "instrument", "type": "string"},
        {"name": "side", "type": "string"},
        {"name": "leverage", "type": "uint8"},
        {"name": "quantity", "type": "uint96"},
        {"name": "limitPrice", "type": "uint80"},
        {"name": "chainId", "type": "uint256"},
    ],
    "New market order": [
        {"name": "id", "type": "string"},
        {"name": "instrument", "type": "string"},
        {"name": "side", "type": "string"},
        {"name": "timeInForce", "type": "string"},
        {"name": "leverage", "type": "uint8"},
        {"name": "cashQuantity", "type": "uint96"},
        {"name": "chainId", "type": "uint256"},
    ],
    "Position close order": [
        {"name": "id", "type": "string"},
        {"name": "instrument", "type": "string"},
        {"name": "leverage", "type": "uint8"},
        {"name": "quantity", "type": "uint96"},
        {"name": "chainId", "type": "uint256"},
    ],
}


def to_eth_number(value: Decimal) -> int:
    """
    Converts a decimal value to an integer using MATCHER_PRECISION.
    Formula: Round(floatValue * 10 ^ 8, HalfUp)
    """
    multiplier = Decimal(10 ** CONSTANTS.MATCHER_PRECISION)
    return int((value * multiplier).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))


class EvedexPerpetualAuth(AuthBase):
    """
    Auth class required by Evedex Perpetual API.

    Uses API-key headers for REST requests, a short-lived access token for private
    websocket subscriptions, and EIP-712 typed data signatures for order placement.
    """

    def __init__(self, api_key: str, time_provider: TimeSynchronizer, private_key: str = ""):
        """
        Initialize EvedEx authentication.

        :param api_key: API key for header authentication
        :param time_provider: Time synchronizer for timestamp generation
        :param private_key: Ethereum wallet private key (hex string, with or without 0x prefix)
                           Required for EIP-712 order signing
        """
        self._api_key: str = api_key
        self._time_provider: TimeSynchronizer = time_provider
        self._access_token: Optional[str] = None
        self._access_token_expiry: float = 0
        self._token_fetcher: Optional[Callable[[], Any]] = None
        self._wallet: Optional[Account] = None

        # Initialize wallet if private key is provided
        if private_key:
            # Handle both with and without 0x prefix
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key
            self._wallet = Account.from_key(private_key)

    def set_token_fetcher(self, fetcher: Callable[[], Any]):
        """
        Set the token fetcher function that will be called to get access tokens.
        This is typically set by the connector to use its API methods.
        """
        self._token_fetcher = fetcher

    async def get_access_token(self) -> str:
        """
        Get or refresh the access token for WebSocket authentication.
        The access token is a JWT obtained from /api/dx-feed/auth endpoint.
        Token expires typically in 15 minutes (900 seconds).
        """
        current_time = time.time()

        # Refresh token if expired or about to expire (with 60 second buffer)
        if self._access_token is None or current_time >= (self._access_token_expiry - 60):
            if self._token_fetcher is not None:
                token_data = await self._token_fetcher()
                self._access_token = token_data.get("token", "")
                # Token expires at 'expireAt' (timestamp in seconds)
                self._access_token_expiry = token_data.get("expireAt", current_time + 900)
            else:
                # Fallback: return empty string if no fetcher is set
                self._access_token = ""

        return self._access_token or ""

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the API key to the request header for authenticated interactions.
        :param request: the request to be configured for authenticated interaction
        """
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        """
        return request  # pass-through

    def header_for_authentication(self) -> Dict[str, str]:
        return {"X-API-Key": self._api_key}

    @property
    def wallet_address(self) -> Optional[str]:
        """Returns the wallet address if a private key was provided."""
        if self._wallet:
            return self._wallet.address
        return None

    def _get_domain_data(self, chain_id: int) -> Dict[str, Any]:
        """
        Get the EIP-712 domain data for EvedEx.

        :param chain_id: The blockchain chain ID
        :return: Domain data dictionary
        """
        return {
            "name": CONSTANTS.EVEDEX_DOMAIN_NAME,
            "version": CONSTANTS.EVEDEX_DOMAIN_VERSION,
            "chainId": int(chain_id),
            "salt": CONSTANTS.EVEDEX_DOMAIN_SALT,
        }

    def sign_limit_order(
        self,
        order_id: str,
        instrument: str,
        side: str,
        leverage: int,
        quantity: Decimal,
        limit_price: Decimal,
        chain_id: int = CONSTANTS.CHAIN_ID,
    ) -> str:
        """
        Sign a limit order using EIP-712.

        :param order_id: Unique order ID
        :param instrument: Trading instrument (e.g., "XRPUSD")
        :param side: Order side ("BUY" or "SELL")
        :param leverage: Leverage multiplier
        :param quantity: Order quantity
        :param limit_price: Limit price
        :param chain_id: Blockchain chain ID (default: 161803)
        :return: Hex signature string
        """
        if not self._wallet:
            raise ValueError("Private key not configured for signing")

        message = {
            "id": order_id,
            "instrument": instrument,
            "side": side,
            "leverage": leverage,
            "quantity": to_eth_number(quantity),
            "limitPrice": to_eth_number(limit_price),
            "chainId": int(chain_id),
        }

        typed_data = {
            "types": {
                "EIP712Domain": EIP712_TYPES["EIP712Domain"],
                "New limit order": EIP712_TYPES["New limit order"],
            },
            "primaryType": "New limit order",
            "domain": self._get_domain_data(chain_id),
            "message": message,
        }

        signable_message = encode_typed_data(full_message=typed_data)
        signed = self._wallet.sign_message(signable_message)
        signature = signed.signature.hex()
        return signature if signature.startswith("0x") else f"0x{signature}"

    def sign_market_order(
        self,
        order_id: str,
        instrument: str,
        side: str,
        time_in_force: str,
        leverage: int,
        cash_quantity: Decimal,
        chain_id: int = CONSTANTS.CHAIN_ID,
    ) -> str:
        """
        Sign a market order using EIP-712.

        :param order_id: Unique order ID
        :param instrument: Trading instrument (e.g., "XRPUSD")
        :param side: Order side ("BUY" or "SELL")
        :param time_in_force: Time in force (e.g., "IOC")
        :param leverage: Leverage multiplier
        :param cash_quantity: Cash quantity for the order
        :param chain_id: Blockchain chain ID (default: 161803)
        :return: Hex signature string
        """
        if not self._wallet:
            raise ValueError("Private key not configured for signing")

        message = {
            "id": order_id,
            "instrument": instrument,
            "side": side,
            "timeInForce": time_in_force,
            "leverage": leverage,
            "cashQuantity": to_eth_number(cash_quantity),
            "chainId": int(chain_id),
        }

        typed_data = {
            "types": {
                "EIP712Domain": EIP712_TYPES["EIP712Domain"],
                "New market order": EIP712_TYPES["New market order"],
            },
            "primaryType": "New market order",
            "domain": self._get_domain_data(chain_id),
            "message": message,
        }

        signable_message = encode_typed_data(full_message=typed_data)
        signed = self._wallet.sign_message(signable_message)
        signature = signed.signature.hex()
        return signature if signature.startswith("0x") else f"0x{signature}"

    def sign_position_close(
        self,
        order_id: str,
        instrument: str,
        leverage: int,
        quantity: Decimal,
        chain_id: int = CONSTANTS.CHAIN_ID,
    ) -> str:
        """
        Sign a position close order using EIP-712.

        :param order_id: Unique order ID
        :param instrument: Trading instrument (e.g., "XRPUSD")
        :param leverage: Leverage multiplier
        :param quantity: Quantity to close
        :param chain_id: Blockchain chain ID (default: 161803)
        :return: Hex signature string
        """
        if not self._wallet:
            raise ValueError("Private key not configured for signing")

        message = {
            "id": order_id,
            "instrument": instrument,
            "leverage": leverage,
            "quantity": to_eth_number(quantity),
            "chainId": int(chain_id),
        }

        typed_data = {
            "types": {
                "EIP712Domain": EIP712_TYPES["EIP712Domain"],
                "Position close order": EIP712_TYPES["Position close order"],
            },
            "primaryType": "Position close order",
            "domain": self._get_domain_data(chain_id),
            "message": message,
        }

        signable_message = encode_typed_data(full_message=typed_data)
        signed = self._wallet.sign_message(signable_message)
        signature = signed.signature.hex()
        return signature if signature.startswith("0x") else f"0x{signature}"
