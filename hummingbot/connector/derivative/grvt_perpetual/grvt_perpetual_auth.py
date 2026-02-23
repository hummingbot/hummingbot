import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import aiohttp
import eth_account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

logger = logging.getLogger(__name__)


class GrvtPerpetualAuth(AuthBase):
    """
    Auth class for GRVT Perpetual API.

    GRVT uses two auth mechanisms:
    1. Session cookie auth: POST to edge /auth/api_key/login with api_key.
       Returns a ``gravity`` cookie and ``X-Grvt-Account-Id`` header.
    2. EIP-712 order signing: Orders are signed with an Ethereum private key
       using GRVT's typed-data schema.
    """

    # Session cookie refresh interval (25 min to be safe; cookie lasts 30 min)
    SESSION_REFRESH_INTERVAL = 25 * 60

    def __init__(
        self,
        api_key: str,
        private_key: str,
        sub_account_id: str,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key: str = api_key
        self._private_key: str = private_key
        self._sub_account_id: str = sub_account_id
        self._domain: str = domain

        # Session cookie state
        self._session_cookie: Optional[str] = None
        self._account_id: Optional[str] = None
        self._session_lock = asyncio.Lock()
        self._last_session_time: float = 0.0

        # Ethereum wallet for EIP-712 signing
        self._wallet = eth_account.Account.from_key(private_key)

    @property
    def is_mainnet(self) -> bool:
        return self._domain == CONSTANTS.DOMAIN

    @property
    def chain_id(self) -> int:
        return CONSTANTS.MAINNET_CHAIN_ID if self.is_mainnet else CONSTANTS.TESTNET_CHAIN_ID

    @property
    def session_cookie(self) -> Optional[str]:
        return self._session_cookie

    @property
    def account_id(self) -> Optional[str]:
        return self._account_id

    def _get_edge_url(self) -> str:
        if self.is_mainnet:
            return CONSTANTS.EDGE_BASE_URL
        return CONSTANTS.TESTNET_EDGE_BASE_URL

    async def ensure_session(self):
        """
        Ensures a valid session cookie exists. Acquires one from the edge
        server if needed. Thread-safe via asyncio lock.
        """
        now = time.time()
        if self._session_cookie and (now - self._last_session_time) < self.SESSION_REFRESH_INTERVAL:
            return

        async with self._session_lock:
            # Double check after acquiring lock
            now = time.time()
            if self._session_cookie and (now - self._last_session_time) < self.SESSION_REFRESH_INTERVAL:
                return

            edge_url = self._get_edge_url()
            login_url = f"{edge_url}{CONSTANTS.AUTH_LOGIN_URL}"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        login_url,
                        json={"api_key": self._api_key},
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        if response.status != 200:
                            body = await response.text()
                            raise IOError(
                                f"GRVT login failed (HTTP {response.status}): {body}"
                            )

                        # Extract the gravity cookie
                        cookies = response.cookies
                        gravity_cookie = cookies.get("gravity")
                        if gravity_cookie is None:
                            # Try from Set-Cookie header directly
                            for cookie in response.headers.getall("Set-Cookie", []):
                                if "gravity=" in cookie:
                                    gravity_cookie = cookie.split("gravity=")[1].split(";")[0]
                                    break

                        if gravity_cookie is None:
                            raise IOError("GRVT login did not return gravity cookie")

                        cookie_value = (
                            gravity_cookie.value
                            if hasattr(gravity_cookie, "value")
                            else str(gravity_cookie)
                        )

                        # Extract account ID from response headers or body
                        self._account_id = response.headers.get("X-Grvt-Account-Id", "")
                        if not self._account_id:
                            resp_data = await response.json()
                            self._account_id = resp_data.get("account_id", "")

                        self._session_cookie = cookie_value
                        self._last_session_time = time.time()
                        logger.info("GRVT session cookie acquired successfully.")

            except aiohttp.ClientError as e:
                raise IOError(f"GRVT login connection error: {e}")

    def sign_order(
        self,
        sub_account_id: int,
        is_market: bool,
        time_in_force: int,
        post_only: bool,
        reduce_only: bool,
        asset_id: int,
        contract_size: int,
        limit_price: int,
        is_buying_contract: bool,
        nonce: int,
        expiration: int,
    ) -> Dict[str, Any]:
        """
        Signs an order using EIP-712 typed data with GRVT's Order schema.

        Price precision: multiply by 1e9 for signing.
        Size: multiply by 10^base_decimals.

        Returns the signature dict with r, s, v components.
        """
        order_leg = {
            "assetID": asset_id,
            "contractSize": contract_size,
            "limitPrice": limit_price,
            "isBuyingContract": is_buying_contract,
        }

        order_message = {
            "subAccountID": sub_account_id,
            "isMarket": is_market,
            "timeInForce": time_in_force,
            "postOnly": post_only,
            "reduceOnly": reduce_only,
            "legs": [order_leg],
            "nonce": nonce,
            "expiration": expiration,
        }

        typed_data = {
            "domain": {
                "name": "GRVT Exchange",
                "version": "0",
                "chainId": self.chain_id,
            },
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                "Order": [
                    {"name": "subAccountID", "type": "uint64"},
                    {"name": "isMarket", "type": "bool"},
                    {"name": "timeInForce", "type": "uint8"},
                    {"name": "postOnly", "type": "bool"},
                    {"name": "reduceOnly", "type": "bool"},
                    {"name": "legs", "type": "OrderLeg[]"},
                    {"name": "nonce", "type": "uint32"},
                    {"name": "expiration", "type": "int64"},
                ],
                "OrderLeg": [
                    {"name": "assetID", "type": "uint256"},
                    {"name": "contractSize", "type": "uint64"},
                    {"name": "limitPrice", "type": "uint64"},
                    {"name": "isBuyingContract", "type": "bool"},
                ],
            },
            "primaryType": "Order",
            "message": order_message,
        }

        structured_data = encode_typed_data(full_message=typed_data)
        signed = self._wallet.sign_message(structured_data)

        return {
            "r": hex(signed["r"]),
            "s": hex(signed["s"]),
            "v": signed["v"],
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds session cookie authentication to REST requests.
        Only authenticated (trade) endpoints need the cookie.
        """
        await self.ensure_session()

        if request.headers is None:
            request.headers = {}

        if self._session_cookie:
            request.headers["Cookie"] = f"gravity={self._session_cookie}"
        if self._account_id:
            request.headers["X-Grvt-Account-Id"] = self._account_id

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        WebSocket authentication is handled via session cookie in the
        connection headers. Pass-through here as the cookie is added
        during WS connection setup.
        """
        return request

    def get_ws_auth_headers(self) -> Dict[str, str]:
        """
        Returns headers needed for authenticated WebSocket connections.
        Must call ensure_session() before using this.
        """
        headers = {}
        if self._session_cookie:
            headers["Cookie"] = f"gravity={self._session_cookie}"
        if self._account_id:
            headers["X-Grvt-Account-Id"] = self._account_id
        return headers

    @staticmethod
    def _get_timestamp() -> float:
        return time.time()
