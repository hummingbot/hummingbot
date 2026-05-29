import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import hummingbot.connector.exchange.hyperliquid.hyperliquid_constants as CONSTANTS
from hummingbot.connector.exchange.hyperliquid.hyperliquid_auth import HyperliquidAuth
from hummingbot.connector.exchange.hyperliquid.hyperliquid_exchange import HyperliquidExchange
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HyperliquidBuilderCodeTests(TestCase):
    """Unit tests for builder-code support (HGP-87) on the Hyperliquid spot connector."""

    builder_address = "0xAbC0000000000000000000000000000000000001"

    def setUp(self) -> None:
        super().setUp()
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _build_connector(self, domain: str = CONSTANTS.DOMAIN, use_vault: bool = False):
        return HyperliquidExchange(
            hyperliquid_secret_key=self.api_secret,
            hyperliquid_address="0x1111111111111111111111111111111111111111",
            use_vault=use_vault,
            trading_pairs=["HFUN-USDC"],
            trading_required=False,
            domain=domain,
        )

    # ----- builder field injection -----

    def test_builder_field_built_with_foundation_defaults(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address
        connector._builder_fee_tenths_bps = 0

        self.assertEqual({"b": self.builder_address.lower(), "f": 0}, connector._build_builder_field())

    def test_builder_address_is_lowercased(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address

        self.assertEqual(self.builder_address.lower(), connector._build_builder_field()["b"])

    def test_builder_field_omitted_when_no_address_configured(self):
        connector = self._build_connector()
        connector._builder_address = None
        self.assertIsNone(connector._build_builder_field())

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
        self.assertIsNone(connector._build_builder_field())

    def test_builder_field_included_on_mainnet(self):
        connector = self._build_connector()
        connector._builder_address = self.builder_address
        self.assertTrue(connector._should_inject_builder())
        self.assertIsNotNone(connector._build_builder_field())

    # ----- override validation (spot cap is 100 bps) -----

    def test_override_within_spot_cap_applied(self):
        connector = self._build_connector()
        connector._load_builder_override({"builder": {"address": self.builder_address, "fee_bps": 100}})
        self.assertEqual(self.builder_address.lower(), connector._builder_address)
        self.assertEqual(1000, connector._builder_fee_tenths_bps)

    def test_override_exceeding_spot_cap_raises(self):
        connector = self._build_connector()
        with self.assertRaises(ValueError):
            connector._load_builder_override({"builder": {"address": self.builder_address, "fee_bps": 101}})

    # ----- /builder-info handler -----

    def test_builder_info_unsupported_on_testnet(self):
        connector = self._build_connector(domain=CONSTANTS.TESTNET_DOMAIN)
        connector._builder_address = self.builder_address
        self.assertEqual({"supported": False}, self.async_run_with_timeout(connector.get_builder_info()))

    def test_builder_info_unsupported_on_vault(self):
        connector = self._build_connector(use_vault=True)
        connector._builder_address = self.builder_address
        self.assertEqual({"supported": False}, self.async_run_with_timeout(connector.get_builder_info()))

    @patch.object(HyperliquidExchange, "_api_post", new_callable=AsyncMock)
    def test_builder_info_supported_at_zero_bps_is_approved(self, api_post_mock: AsyncMock):
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


class HyperliquidAuthBuilderTests(TestCase):
    """Verifies the builder field is part of the signed order action for the spot connector."""

    def setUp(self) -> None:
        super().setUp()
        self.api_address = "0x1111111111111111111111111111111111111111"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.auth = HyperliquidAuth(
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
                "asset": 10004,
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

        action = json.loads(request.data)["action"]
        self.assertIn("builder", action)
        self.assertEqual({"b": "0xabc0000000000000000000000000000000000001", "f": 0}, action["builder"])

    def test_builder_field_changes_signature(self):
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

        self.assertNotEqual(
            json.loads(request_without.data)["signature"],
            json.loads(request_with.data)["signature"],
        )
        self.assertNotIn("builder", json.loads(request_without.data)["action"])
