import json
import sys
import types
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

if "eth_account" not in sys.modules:
    eth_account_module = types.ModuleType("eth_account")

    class _DummyAccount:
        @staticmethod
        def from_key(key):
            return SimpleNamespace(
                address=key,
                sign_message=lambda *_args, **_kwargs: SimpleNamespace(signature=b"\x01" * 65),
            )

    eth_account_module.Account = _DummyAccount
    sys.modules["eth_account"] = eth_account_module

    messages_module = types.ModuleType("eth_account.messages")
    messages_module.encode_defunct = lambda text=None, **_kwargs: text
    messages_module.encode_typed_data = lambda full_message: full_message
    sys.modules["eth_account.messages"] = messages_module

sys.modules.setdefault("pandas", MagicMock())
sys.modules.setdefault("numpy", MagicMock())
sys.modules.setdefault("aiohttp", MagicMock())
sys.modules.setdefault("ujson", MagicMock())
sys.modules.setdefault("cachetools", types.SimpleNamespace(TTLCache=lambda *_, **__: {}))
core_schema_stub = types.SimpleNamespace(
    CoreSchema=object,
    no_info_after_validator_function=lambda *_, **__: None,
    dict_schema=lambda *_, **__: None,
    any_schema=lambda *_, **__: None,
    set_schema=lambda *_, **__: None,
)
sys.modules.setdefault("pydantic_core", types.SimpleNamespace(core_schema=core_schema_stub, __version__="0.0.0"))
sys.modules.setdefault("pydantic", types.SimpleNamespace())
sys.modules.setdefault("hummingbot.connector.exchange_base", types.SimpleNamespace(ExchangeBase=object))
sys.modules.setdefault("hummingbot.connector.trading_rule", types.SimpleNamespace(TradingRule=object))
sys.modules.setdefault("hummingbot.core.data_type.limit_order", types.SimpleNamespace(LimitOrder=object))
sys.modules.setdefault("hexbytes", types.SimpleNamespace(HexBytes=bytes))
network_status_stub = types.SimpleNamespace(NetworkStatus=types.SimpleNamespace(CONNECTED="connected", NOT_CONNECTED="not_connected"))
sys.modules.setdefault("hummingbot.core.network_iterator", network_status_stub)

class _DummyTimeout:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


sys.modules.setdefault("async_timeout", types.SimpleNamespace(timeout=lambda *_, **__: _DummyTimeout()))

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import (
    EvedexPerpetualAuth,
)


class MockResponse:
    def __init__(self, status, data):
        self.status = status
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._data

    async def text(self):
        return json.dumps(self._data)


class MockSession:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def post(self, url, json=None, headers=None):
        response = self._responses.pop(0)
        self.calls.append({"url": url, "json": json, "headers": headers})
        return MockResponse(**response)


class EvedexPerpetualAuthTests(IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        self.wallet_address = "0xA000000000000000000000000000000000000001"
        self.base_url = "https://market-data-api.evedex.tech"
    
    def _build_signer(self):
        return SimpleNamespace(
            address=self.wallet_address,
            sign_message=lambda *_args, **_kwargs: SimpleNamespace(signature=b"\x01" * 65),
        )

    async def test_authenticate_siwe_success(self):
        auth = EvedexPerpetualAuth(
            api_key=None,
            api_secret=None,
            wallet_address=self.wallet_address,
            auth_base_url=self.base_url,
        )
        auth._wallet_signer = self._build_signer()

        session = MockSession(
            responses=[
                {
                    "status": 200,
                    "data": {
                        "nonce": "abc123",
                        "message": "Sign in with nonce abc123",
                        "chainId": 5,
                    },
                },
                {
                    "status": 200,
                    "data": {
                        "accessToken": "access",
                        "refreshToken": "refresh",
                        "expiresIn": 3600,
                        "userExchangeId": "user-1",
                    },
                },
            ]
        )

        result = await auth._authenticate_siwe(session)

        self.assertTrue(result)
        self.assertEqual(auth._tokens.access_token, "access")
        self.assertEqual(auth._tokens.refresh_token, "refresh")
        self.assertEqual(auth._tokens.user_exchange_id, "user-1")
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(
            session.calls[0]["json"]["walletAddress"].lower(),
            self.wallet_address.lower(),
        )
        signup_payload = session.calls[1]["json"]
        self.assertEqual(signup_payload["message"], "Sign in with nonce abc123")
        self.assertIn("signature", signup_payload)

    async def test_authenticate_siwe_builds_default_message_when_missing(self):
        auth = EvedexPerpetualAuth(
            api_key=None,
            api_secret=None,
            wallet_address=self.wallet_address,
            auth_base_url=self.base_url,
        )
        auth._wallet_signer = self._build_signer()

        session = MockSession(
            responses=[
                {
                    "status": 200,
                    "data": {
                        "nonce": "nonce456",
                    },
                },
                {
                    "status": 200,
                    "data": {
                        "accessToken": "token",
                        "refreshToken": "refresh",
                        "expiresIn": 3600,
                        "userExchangeId": "user-2",
                    },
                },
            ]
        )

        result = await auth._authenticate_siwe(session)

        self.assertTrue(result)
        signup_payload = session.calls[1]["json"]
        self.assertIn("nonce456", signup_payload["message"])
        self.assertIn(self.wallet_address, signup_payload["message"])
        self.assertIn("Issued At", signup_payload["message"])

    async def test_authenticate_siwe_without_private_key_fails(self):
        auth = EvedexPerpetualAuth(
            api_key=None,
            api_secret=None,
            wallet_address=self.wallet_address,
            auth_base_url=self.base_url,
        )

        session = MockSession(responses=[])

        result = await auth._authenticate_siwe(session)

        self.assertFalse(result)
        self.assertEqual(len(session.calls), 0)
