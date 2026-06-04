import asyncio
import json
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import HyperliquidPerpetualAuth
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
    HyperliquidPerpetualDerivative,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HyperliquidPerpetualBuilderCodeTests(TestCase):
    """Unit tests for builder-code support (HGP-87) on the Hyperliquid perpetual connector."""

    builder_address = "0xAbC0000000000000000000000000000000000001"

    def setUp(self) -> None:
        super().setUp()
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _build_connector(self, domain: str = CONSTANTS.DOMAIN, use_vault: bool = False):
        return HyperliquidPerpetualDerivative(
            hyperliquid_perpetual_secret_key=self.api_secret,
            hyperliquid_perpetual_address="0x1111111111111111111111111111111111111111",
            use_vault=use_vault,
            trading_pairs=["BTC-USD"],
            trading_required=False,
            domain=domain,
        )

    # ----- builder field injection -----

    def test_builder_field_built_with_foundation_defaults(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address
        connector._builder_fee_tenths_bps = 0

        builder_field = connector._build_builder_field()
        self.assertEqual({"b": self.builder_address.lower(), "f": 0}, builder_field)

    def test_builder_address_is_lowercased_even_when_supplied_mixed_case(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address  # mixed-case

        builder_field = connector._build_builder_field()
        self.assertEqual(self.builder_address.lower(), builder_field["b"])
        self.assertNotEqual(self.builder_address, builder_field["b"])

    def test_builder_field_omitted_when_no_address_configured(self):
        connector = self._build_connector()
        connector._builder_address = None

        self.assertIsNone(connector._build_builder_field())
        self.assertFalse(connector._should_inject_builder())

    def test_default_foundation_address_configured_so_field_injected(self):
        # Foundation onboarding has set the constant, so the default connector attributes orders.
        self.assertIsNotNone(CONSTANTS.FOUNDATION_BUILDER_ADDRESS)
        connector = self._build_connector()
        self.assertEqual(CONSTANTS.FOUNDATION_BUILDER_ADDRESS.lower(), connector._builder_address)
        self.assertEqual(0, connector._builder_fee_tenths_bps)
        self.assertTrue(connector._should_inject_builder())

    def test_builder_field_omitted_when_not_supported(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address
        with patch.object(CONSTANTS, "BUILDER_SUPPORTED", False):
            self.assertFalse(connector._should_inject_builder())

    # ----- omit cases -----

    def test_builder_field_omitted_on_vault(self):
        connector = self._build_connector(use_vault=True)
        connector._builder_address = self.builder_address

        self.assertFalse(connector._should_inject_builder())
        self.assertIsNone(connector._build_builder_field())

    def test_builder_field_omitted_on_testnet(self):
        connector = self._build_connector(domain=CONSTANTS.TESTNET_DOMAIN)
        connector._builder_address = self.builder_address

        self.assertTrue(connector._is_testnet)
        self.assertFalse(connector._should_inject_builder())
        self.assertIsNone(connector._build_builder_field())

    def test_builder_field_included_on_mainnet(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address

        self.assertTrue(connector._should_inject_builder())
        self.assertIsNotNone(connector._build_builder_field())

    # ----- end-to-end order payload (the field actually reaches the order action) -----

    def _capture_order_payload(self, connector) -> dict:
        with patch.object(type(connector), "_api_post", new_callable=AsyncMock) as api_post_mock, \
                patch.object(type(connector), "exchange_symbol_associated_to_pair", new_callable=AsyncMock) as sym_mock:
            sym_mock.return_value = "BTC"
            api_post_mock.return_value = {
                "status": "ok",
                "response": {"data": {"statuses": [{"resting": {"oid": 123}}]}},
            }
            connector.coin_to_asset = {"BTC": 4}
            self.async_run_with_timeout(connector._place_order(
                order_id="0x000000000000000000000000000ee056",
                trading_pair="BTC-USD",
                amount=Decimal("0.01"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("1200"),
            ))
            return api_post_mock.call_args.kwargs["data"]

    def test_order_payload_includes_builder_on_mainnet(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address
        self.assertEqual({"b": self.builder_address.lower(), "f": 0},
                         self._capture_order_payload(connector)["builder"])

    def test_order_payload_omits_builder_on_testnet(self):
        connector = self._build_connector(domain=CONSTANTS.TESTNET_DOMAIN)
        connector._builder_address = self.builder_address
        self.assertNotIn("builder", self._capture_order_payload(connector))

    def test_order_payload_omits_builder_on_vault(self):
        connector = self._build_connector(use_vault=True)
        connector._builder_address = self.builder_address
        self.assertNotIn("builder", self._capture_order_payload(connector))

    def test_order_payload_omits_builder_when_unconfigured(self):
        connector = self._build_connector()
        connector._builder_address = None
        self.assertNotIn("builder", self._capture_order_payload(connector))

    # ----- override validation -----

    def test_override_within_cap_applied(self):
        connector = self._build_connector()
        connector._load_builder_override({"builder": {"address": self.builder_address, "fee_bps": 10}})

        # perp cap is 10 bps -> 100 tenths of a bp
        self.assertEqual(self.builder_address.lower(), connector._builder_address)
        self.assertEqual(100, connector._builder_fee_tenths_bps)

    def test_override_exceeding_cap_raises(self):
        connector = self._build_connector()
        with self.assertRaises(ValueError):
            connector._load_builder_override({"builder": {"address": self.builder_address, "fee_bps": 11}})

    def test_override_absent_is_noop(self):
        connector = self._build_connector()
        original = connector._builder_address
        connector._load_builder_override(None)
        connector._load_builder_override({})
        self.assertEqual(original, connector._builder_address)

    # ----- /builder-info handler -----

    def test_builder_info_unsupported_on_testnet(self):
        connector = self._build_connector(domain=CONSTANTS.TESTNET_DOMAIN)
        connector._builder_address = self.builder_address
        info = self.async_run_with_timeout(connector.get_builder_info())
        self.assertEqual({"supported": False}, info)

    def test_builder_info_unsupported_on_vault(self):
        connector = self._build_connector(use_vault=True)
        connector._builder_address = self.builder_address
        info = self.async_run_with_timeout(connector.get_builder_info())
        self.assertEqual({"supported": False}, info)

    @patch.object(HyperliquidPerpetualDerivative, "_api_post", new_callable=AsyncMock)
    def test_builder_info_supported_at_zero_bps_is_approved(self, api_post_mock: AsyncMock):
        # maxBuilderFee for an unapproved (user, builder) pair returns 0; 0 >= 0 -> approved.
        api_post_mock.return_value = 0
        connector = self._build_connector()
        # The address is stored lowercased (by __init__ / _load_builder_override) in real usage.
        connector._builder_address = self.builder_address.lower()
        connector._builder_fee_tenths_bps = 0

        info = self.async_run_with_timeout(connector.get_builder_info())
        self.assertTrue(info["supported"])
        self.assertEqual(self.builder_address.lower(), info["builder_address"])
        self.assertEqual(0, info["fee_bps"])
        self.assertTrue(info["approved"])
        self.assertIsNone(info["approval_expiry_ms"])

    @patch.object(HyperliquidPerpetualDerivative, "_api_post", new_callable=AsyncMock)
    def test_builder_info_not_approved_when_fee_exceeds_approved_max(self, api_post_mock: AsyncMock):
        api_post_mock.return_value = 0  # user approved 0 tenths of a bp
        connector = self._build_connector()
        connector._builder_address = self.builder_address
        connector._builder_fee_tenths_bps = 10  # wants 1 bp

        info = self.async_run_with_timeout(connector.get_builder_info())
        self.assertTrue(info["supported"])
        self.assertFalse(info["approved"])
        self.assertEqual(1, info["fee_bps"])


class HyperliquidPerpetualAuthBuilderTests(TestCase):
    """Verifies the builder field is part of the signed order action."""

    def setUp(self) -> None:
        super().setUp()
        self.api_address = "0x1111111111111111111111111111111111111111"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.auth = HyperliquidPerpetualAuth(
            api_address=self.api_address,
            api_secret=self.api_secret,
            use_vault=False,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _order_params(self, with_builder: bool):
        params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": 4,
                "isBuy": True,
                "limitPx": 1201,
                "sz": 0.01,
                "reduceOnly": False,
                "orderType": {"limit": {"tif": "Gtc"}},
                "cloid": "0x000000000000000000000000000ee056",
            },
        }
        if with_builder:
            params["builder"] = {"b": "0xabc0000000000000000000000000000000000001", "f": 0}
        return params

    def test_builder_field_is_part_of_signed_action(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(self._order_params(with_builder=True)),
            is_auth_required=True,
        )
        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        payload = json.loads(request.data)
        action = payload["action"]
        self.assertIn("builder", action)
        self.assertEqual({"b": "0xabc0000000000000000000000000000000000001", "f": 0}, action["builder"])

    def test_builder_field_changes_signature(self):
        # The builder field is signed, so its presence must change the resulting signature.
        request_without = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(self._order_params(with_builder=False)),
            is_auth_required=True,
        )
        request_with = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(self._order_params(with_builder=True)),
            is_auth_required=True,
        )
        self.async_run_with_timeout(self.auth.rest_authenticate(request_without))
        self.async_run_with_timeout(self.auth.rest_authenticate(request_with))

        sig_without = json.loads(request_without.data)["signature"]
        sig_with = json.loads(request_with.data)["signature"]
        self.assertNotEqual(sig_without, sig_with)
        self.assertNotIn("builder", json.loads(request_without.data)["action"])
