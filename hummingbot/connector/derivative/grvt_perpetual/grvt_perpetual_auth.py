import json
import logging
from collections import OrderedDict
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional

import aiohttp
import eth_account
from eth_account.messages import encode_typed_data

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest
from hummingbot.logger import HummingbotLogger

# EIP-712 Message Types for Order
EIP712_ORDER_MESSAGE_TYPE = {
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


class GRVTPerpetualAuth(AuthBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, api_key: str, api_secret: str, sub_account_id: str, domain: str = CONSTANTS.DOMAIN):
        self._api_key = api_key
        self._api_secret = api_secret
        self._sub_account_id = sub_account_id
        self._domain = domain
        self._wallet = eth_account.Account.from_key(api_secret)

        self._cookie_value: Optional[str] = None
        self._cookie_expires: Optional[datetime] = None
        self._grvt_account_id: Optional[str] = None
        self._chain_id = CONSTANTS.CHAIN_IDS[self._domain]

    def _should_refresh_cookie(self) -> bool:
        if not self._cookie_value or not self._cookie_expires:
            return True
        time_till_expiration = (self._cookie_expires - datetime.utcnow()).total_seconds()
        return time_till_expiration < 10

    async def _refresh_cookie(self):
        if not self._should_refresh_cookie():
            return
        
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils import public_rest_url
        login_url = public_rest_url(CONSTANTS.AUTH_URL, domain=self._domain, rpc_type=CONSTANTS.GRVT_EDGE_RPC)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(login_url, json={"api_key": self._api_key}, timeout=10) as response:
                if response.status == 200:
                    cookie_header = response.headers.get("Set-Cookie")
                    if cookie_header:
                        cookie = SimpleCookie()
                        cookie.load(cookie_header)
                        if "gravity" in cookie:
                            self._cookie_value = cookie["gravity"].value
                            expires_str = cookie["gravity"].get("expires", "")
                            if expires_str:
                                try:
                                    self._cookie_expires = datetime.strptime(expires_str, "%a, %d %b %Y %H:%M:%S %Z")
                                except ValueError:
                                    self._cookie_expires = datetime.strptime(expires_str, "%a, %d-%b-%Y %H:%M:%S %Z")
                            else:
                                self._cookie_expires = datetime.utcnow()
                    self._grvt_account_id = response.headers.get("X-Grvt-Account-Id")
                else:
                    self.logger().error(f"Failed to fetch cookie: {response.status} {await response.text()}")

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        await self._refresh_cookie()
        if self._cookie_value:
            if request.headers is None:
                request.headers = {}
            request.headers["Cookie"] = f"gravity={self._cookie_value}"
            if self._grvt_account_id:
                request.headers["X-Grvt-Account-Id"] = self._grvt_account_id
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        await self._refresh_cookie()
        if self._cookie_value:
            # For WS, we usually can't set headers in the browser, but python aiohttp supports it
            pass
        return request

    def generate_ws_auth_message(self) -> Dict[str, Any]:
        """
        Generates the authentication message for websockets if needed.
        Currently using cookie auth, but some exchanges need a login message.
        """
        return {}

    def get_eip712_domain_data(self) -> dict:
        return {
            "name": "GRVT Exchange",
            "version": "0",
            "chainId": self._chain_id,
        }

    def sign_order_payload(self, message_data: dict) -> dict:
        """
        Signs the EIP-712 order message and returns the signature dictionary.
        """
        domain_data = self.get_eip712_domain_data()
        signable_message = encode_typed_data(domain_data, EIP712_ORDER_MESSAGE_TYPE, message_data)
        signed_message = self._wallet.sign_message(signable_message)
        
        return {
            "r": "0x" + signed_message.r.to_bytes(32, byteorder="big").hex(),
            "s": "0x" + signed_message.s.to_bytes(32, byteorder="big").hex(),
            "v": signed_message.v,
            "signer": str(self._wallet.address)
        }
