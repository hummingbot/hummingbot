import asyncio
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock

from bidict import bidict

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import (
    GRVTPerpetualDerivative,
    PRICE_MULTIPLIER,
    _InstrumentInfo,
)
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType


class TestGRVTPerpetualDerivative(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.api_secret = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
        self.sub_account_id = "12345"

        self.exchange = GRVTPerpetualDerivative(
            grvt_perpetual_api_key=self.api_key,
            grvt_perpetual_api_secret=self.api_secret,
            grvt_perpetual_sub_account_id=self.sub_account_id,
            trading_pairs=["BTC-USDT"],
        )

        # Seed symbol mapping + instrument cache so _place_order does not do network IO
        self.exchange._set_trading_pair_symbol_map(bidict({"BTC_USDT_Perp": "BTC-USDT"}))
        self.exchange._instrument_by_exchange_symbol["BTC_USDT_Perp"] = _InstrumentInfo(
            instrument="BTC_USDT_Perp",
            instrument_hash="0x123",
            base="BTC",
            quote="USDT",
            base_decimals=8,
            tick_size=Decimal("0.1"),
            min_size=Decimal("0.001"),
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.MARKET, supported_types)

    def test_supported_position_modes(self):
        supported_modes = self.exchange.supported_position_modes()
        self.assertEqual(1, len(supported_modes))
        self.assertIn(PositionMode.ONEWAY, supported_modes)

    def test_client_order_id_prefix(self):
        self.assertEqual("HBOT", self.exchange.client_order_id_prefix)

    def test_place_order_builds_schema_payload_and_signing_ints(self):
        captured = {}

        async def _api_post_patch(path_url, data, is_auth_required, limit_id, **kwargs):
            captured["path_url"] = path_url
            captured["data"] = data
            captured["is_auth_required"] = is_auth_required
            captured["limit_id"] = limit_id
            return {"result": {"order_id": "abc123"}}

        # Prevent EIP-712 dependency from affecting test; verify we pass correct signable data via side effects.
        sign_calls = {}

        def sign_order_payload_patch(message_data):
            sign_calls["message_data"] = message_data
            return {"r": "0x01", "s": "0x02", "v": 27, "signer": "0xdeadbeef"}

        self.exchange._api_post = _api_post_patch
        self.exchange._auth.sign_order_payload = sign_order_payload_patch
        # TimeIterator.current_timestamp is read-only; use helper
        self.exchange._set_current_timestamp(1_700_000_000.0)

        ex_order_id, ts = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="HBOT-1",
                trading_pair="BTC-USDT",
                amount=Decimal("1.5"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("101.3"),
            )
        )

        self.assertEqual("abc123", ex_order_id)
        self.assertEqual(1_700_000_000.0, ts)

        # Verify signable ints follow SDK rules: contractSize = amount * 10**base_decimals, limitPrice = price * 1e9
        msg = sign_calls["message_data"]
        self.assertEqual(int("0x123", 16), msg["legs"][0]["assetID"])
        self.assertEqual(int(Decimal("1.5") * (Decimal(10) ** 8)), msg["legs"][0]["contractSize"])
        self.assertEqual(int(Decimal("101.3") * Decimal(PRICE_MULTIPLIER)), msg["legs"][0]["limitPrice"])

        # Verify REST payload uses official snake_case schema with nested signature + metadata
        req = captured["data"]
        self.assertIn("order", req)
        order = req["order"]
        self.assertEqual(self.sub_account_id, order["sub_account_id"])
        self.assertEqual("GOOD_TILL_TIME", order["time_in_force"])
        self.assertEqual("HBOT-1", order["metadata"]["client_order_id"])
        self.assertIn("signature", order)
        self.assertEqual("0xdeadbeef", order["signature"]["signer"])
