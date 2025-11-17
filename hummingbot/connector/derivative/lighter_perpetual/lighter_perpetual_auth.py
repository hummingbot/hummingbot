from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

SignerFactoryType = Callable[..., Any]
logger = logging.getLogger(__name__)


class LighterPerpetualAuth(AuthBase):
    """Wrapper around Lighter SignerClient exposing helpers for signing transactions and auth tokens."""

    def __init__(
        self,
        domain: str,
        api_key_private_key: str,
        account_index: int,
        api_key_index: int,
        additional_api_private_keys: Optional[Dict[int, str]] = None,
        max_api_key_index: Optional[int] = None,
        eth_private_key: Optional[str] = None,
        signer_factory: Optional[SignerFactoryType] = None,
    ):
        self._domain = domain or CONSTANTS.DEFAULT_DOMAIN
        self._api_key_private_key = api_key_private_key
        self._account_index = account_index
        self._api_key_index = api_key_index
        self._additional_private_keys = additional_api_private_keys or {}
        indexes = [api_key_index] + list(self._additional_private_keys.keys())
        self._max_api_key_index = (
            max_api_key_index
            if max_api_key_index is not None
            else max(indexes)
            if indexes
            else api_key_index
        )
        self._eth_private_key = eth_private_key
        self._signer_factory = signer_factory or self._default_signer_factory
        self._signer_params = dict(
            base_url=self._base_url,
            api_key_private_key=api_key_private_key,
            account_index=account_index,
            api_key_index=api_key_index,
            max_api_key_index=self._max_api_key_index,
            additional_private_keys=dict(self._additional_private_keys),
            eth_private_key=eth_private_key,
        )
        self._signer = None

    @property
    def signer(self):
        if self._signer is None:
            self._signer = self._signer_factory(**self._signer_params)
        return self._signer

    @property
    def account_index(self) -> int:
        return self._account_index

    @property
    def api_key_index(self) -> int:
        return self._api_key_index

    @property
    def max_api_key_index(self) -> int:
        return self._max_api_key_index

    @property
    def additional_private_keys(self) -> Dict[int, str]:
        return dict(self._additional_private_keys)

    @property
    def _base_url(self) -> str:
        return CONSTANTS.REST_URLS.get(
            self._domain, CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN]
        )

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    async def create_auth_token(self, expiry_seconds: int = 600) -> str:
        token, error = self._ensure_async(
            self.signer.create_auth_token_with_expiry, expiry_seconds
        )
        if error:
            raise RuntimeError(f"Failed to create auth token: {error}")
        return token

    async def sign_create_order(self, **kwargs) -> Tuple[Any, Any, Optional[str]]:
        return await self._execute_signer_call(self.signer.sign_create_order, **kwargs)

    async def sign_cancel_order(self, **kwargs) -> Tuple[Any, Any, Optional[str]]:
        return await self._execute_signer_call(self.signer.sign_cancel_order, **kwargs)

    async def sign_cancel_all_orders(self, **kwargs) -> Tuple[Any, Any, Optional[str]]:
        return await self._execute_signer_call(
            self.signer.sign_cancel_all_orders, **kwargs
        )

    async def sign_update_leverage(self, **kwargs) -> Tuple[Any, Any, Optional[str]]:
        return await self._execute_signer_call(
            self.signer.sign_update_leverage, **kwargs
        )

    async def sign_withdraw(self, **kwargs) -> Tuple[Any, Any, Optional[str]]:
        return await self._execute_signer_call(self.signer.sign_withdraw, **kwargs)

    async def _execute_signer_call(
        self, method: Callable[..., Awaitable], *args, **kwargs
    ):
        result = method(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _ensure_async(self, func: Callable[..., Awaitable], *args, **kwargs):
        result = func(*args, **kwargs)
        return result

    @staticmethod
    def _default_signer_factory(
        base_url: str,
        api_key_private_key: str,
        account_index: int,
        api_key_index: int,
        max_api_key_index: int,
        additional_private_keys: Dict[int, str],
        eth_private_key: Optional[str] = None,
    ):
        try:  # pragma: no cover
            from lighter.signer_client import SignerClient  # type: ignore

            return SignerClient(
                url=base_url,
                private_key=api_key_private_key,
                account_index=account_index,
                api_key_index=api_key_index,
                max_api_key_index=max_api_key_index,
                private_keys=additional_private_keys,
            )
        except Exception as exc:  # pragma: no cover - fallback for missing signer
            logger.warning(
                "Unable to initialize native Lighter signer. Falling back to mock signer. Reason: %s",
                exc,
            )
            return _MockSignerClient()


class _MockSignerClient:
    """Simple signer used when the native signer is unavailable."""

    def __init__(self):
        self._nonce = int(time.time() * 1e6)

    async def create_auth_token_with_expiry(self, expiry_seconds: int):
        self._nonce += 1
        return f"mock-auth-token-{self._nonce}", None

    def _base_payload(self, action: Dict[str, Any]) -> str:
        payload = {
            "action": action,
            "nonce": self._nonce,
            "signature": "0x0",
        }
        self._nonce += 1
        return json.dumps(payload)

    def sign_create_order(
        self,
        market_index,
        client_order_index,
        base_amount,
        price,
        is_ask,
        order_type,
        time_in_force,
        reduce_only,
        trigger_price,
        order_expiry=0,
        nonce=-1,
    ):
        action = {
            "orders": [
                {
                    "asset": market_index,
                    "b": not bool(is_ask),
                    "p": str(price),
                    "s": str(base_amount),
                    "c": str(client_order_index),
                    "ro": bool(reduce_only),
                    "t": order_type,
                    "f": time_in_force,
                }
            ],
            "grouping": "na",
        }
        return self._base_payload(action), None

    def sign_cancel_order(self, market_index, order_index, nonce=-1):
        action = {"cancel": {"asset": market_index, "oid": order_index}}
        return self._base_payload(action), None

    def sign_cancel_all_orders(self, market_index, nonce=-1):
        action = {"cancel_all": {"asset": market_index}}
        return self._base_payload(action), None

    def sign_update_leverage(self, asset, leverage, is_cross=True, nonce=-1):
        action = {
            "leverage": {"asset": asset, "leverage": leverage, "isCross": is_cross}
        }
        return self._base_payload(action), None

    def sign_withdraw(self, **kwargs):
        action = {"withdraw": kwargs}
        return self._base_payload(action), None
