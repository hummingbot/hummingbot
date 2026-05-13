import random
import time
from datetime import datetime
from decimal import Decimal
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional

import aiohttp
from eth_account import Account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class GrvtPerpetualAuth(AuthBase):
    _EIP712_ORDER_MESSAGE_TYPE = {
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
    }
    _SIGN_TIME_IN_FORCE = {
        CONSTANTS.TIME_IN_FORCE_GOOD_TILL_TIME: 1,
        "ALL_OR_NONE": 2,
        CONSTANTS.TIME_IN_FORCE_IMMEDIATE_OR_CANCEL: 3,
        CONSTANTS.TIME_IN_FORCE_FILL_OR_KILL: 4,
    }
    _CHAIN_IDS = {
        CONSTANTS.DEFAULT_DOMAIN: 325,
        CONSTANTS.TESTNET_DOMAIN: 326,
    }

    def __init__(self, api_key: str, private_key: str, trading_account_id: str, domain: str):
        self._api_key = api_key
        self._private_key = private_key
        self._trading_account_id = trading_account_id
        self._domain = domain
        self._wallet = Account.from_key(private_key) if private_key else None
        self._session_cookie: Optional[str] = None
        self._session_expiry_ts: float = 0
        self._grvt_account_id: Optional[str] = None
        self._session_lock = None

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.is_auth_required:
            headers = dict(request.headers or {})
            headers.update(await self.get_rest_auth_headers())
            request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    async def get_rest_auth_headers(self) -> Dict[str, str]:
        await self._ensure_authenticated()
        return self._auth_headers()

    async def get_ws_auth_headers(self) -> Dict[str, str]:
        await self._ensure_authenticated()
        return self._auth_headers()

    async def _ensure_authenticated(self):
        if self._session_lock is None:
            import asyncio

            self._session_lock = asyncio.Lock()
        if not self._should_refresh_session():
            return
        async with self._session_lock:
            if self._should_refresh_session():
                await self._refresh_session()

    def _should_refresh_session(self) -> bool:
        return (
            self._session_cookie is None
            or self._session_expiry_ts - time.time() <= CONSTANTS.COOKIE_REFRESH_INTERVAL_BUFFER
        )

    def _auth_headers(self) -> Dict[str, str]:
        headers = {
            "Cookie": f"gravity={self._session_cookie}",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
        }
        if self._grvt_account_id:
            headers["X-Grvt-Account-Id"] = self._grvt_account_id
        return headers

    async def _refresh_session(self):
        url = web_utils.edge_rest_url(CONSTANTS.AUTH_PATH_URL, domain=self._domain)
        async with aiohttp.ClientSession(headers={"Content-Type": "application/json", "Accept-Encoding": "identity"}) as session:
            async with session.post(url=url, json={"api_key": self._api_key}, timeout=5) as response:
                if response.status >= 400:
                    raise IOError(f"GRVT auth failed with status {response.status}")
                cookie = SimpleCookie()
                cookie.load(response.headers.get("Set-Cookie", ""))
                gravity_cookie = cookie.get("gravity")
                if gravity_cookie is None:
                    raise IOError("GRVT auth response did not contain gravity cookie")
                self._session_cookie = gravity_cookie.value
                self._session_expiry_ts = datetime.strptime(
                    gravity_cookie["expires"],
                    "%a, %d %b %Y %H:%M:%S %Z",
                ).timestamp()
                self._grvt_account_id = response.headers.get("X-Grvt-Account-Id")

    def get_order_payload(
        self,
        instrument: Dict[str, Any],
        client_order_id: str,
        exchange_symbol: str,
        amount: Decimal,
        price: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        reduce_only: bool,
        expiration_seconds: int = CONSTANTS.ORDER_SIGNATURE_EXPIRATION_SECS,
    ) -> Dict[str, Any]:
        time_in_force = self._time_in_force_for_order_type(order_type=order_type)
        is_market = order_type == OrderType.MARKET
        limit_price = Decimal("0") if is_market else price
        nonce = random.randint(0, 2**32 - 1)
        expiration = str(time.time_ns() + expiration_seconds * 1_000_000_000)
        is_buy = trade_type == TradeType.BUY
        message = self._signable_message(
            instrument=instrument,
            amount=amount,
            limit_price=limit_price,
            is_buy=is_buy,
            is_market=is_market,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            post_only=order_type == OrderType.LIMIT_MAKER,
            nonce=nonce,
            expiration=expiration,
        )
        signed = Account.sign_message(message, self._private_key)

        return {
            "order": {
                "sub_account_id": str(self._trading_account_id),
                "is_market": is_market,
                "time_in_force": time_in_force,
                "post_only": order_type == OrderType.LIMIT_MAKER,
                "reduce_only": reduce_only,
                "legs": [
                    {
                        "instrument": exchange_symbol,
                        "size": str(amount),
                        "limit_price": str(limit_price),
                        "is_buying_asset": is_buy,
                    }
                ],
                "signature": {
                    "r": f"0x{signed.r.to_bytes(32, byteorder='big').hex()}",
                    "s": f"0x{signed.s.to_bytes(32, byteorder='big').hex()}",
                    "v": signed.v,
                    "expiration": expiration,
                    "nonce": nonce,
                    "signer": self._wallet.address,
                },
                "metadata": {
                    "client_order_id": str(client_order_id),
                    "broker": CONSTANTS.HBOT_BROKER_ID,
                },
            }
        }

    def _signable_message(
        self,
        instrument: Dict[str, Any],
        amount: Decimal,
        limit_price: Decimal,
        is_buy: bool,
        is_market: bool,
        time_in_force: str,
        reduce_only: bool,
        post_only: bool,
        nonce: int,
        expiration: str,
    ):
        size_multiplier = 10 ** int(instrument["base_decimals"])
        message_data = {
            "subAccountID": int(self._trading_account_id),
            "isMarket": is_market,
            "timeInForce": self._SIGN_TIME_IN_FORCE[time_in_force],
            "postOnly": post_only,
            "reduceOnly": reduce_only,
            "legs": [
                {
                    "assetID": instrument["instrument_hash"],
                    "contractSize": int(amount * Decimal(size_multiplier)),
                    "limitPrice": int(limit_price * Decimal(CONSTANTS.PRICE_SCALE)),
                    "isBuyingContract": is_buy,
                }
            ],
            "nonce": nonce,
            "expiration": int(expiration),
        }
        domain_data = {
            "name": "GRVT Exchange",
            "version": "0",
            "chainId": self._CHAIN_IDS[self._domain],
        }
        return encode_typed_data(domain_data, self._EIP712_ORDER_MESSAGE_TYPE, message_data)

    @staticmethod
    def _time_in_force_for_order_type(order_type: OrderType) -> str:
        if order_type == OrderType.MARKET:
            return CONSTANTS.TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
        return CONSTANTS.TIME_IN_FORCE_GOOD_TILL_TIME
