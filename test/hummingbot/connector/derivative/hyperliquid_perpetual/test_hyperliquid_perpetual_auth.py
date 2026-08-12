import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import HyperliquidPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HyperliquidPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        # Address derived from api_secret below; required since the auth class now
        # validates that the supplied address matches the address derived from the
        # private key when use_vault is False (see issue #7866).
        self.api_address = "0x836eE2b55d173245832995082a8600709c38D099"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.connection_mode = "arb_wallet"
        self.use_vault = False
        self.trading_required = True  # noqa: mock
        self.auth = HyperliquidPerpetualAuth(
            api_address=self.api_address,
            api_secret=self.api_secret,
            use_vault=self.use_vault
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return 1678974447.926

    @patch(
        "hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth.HyperliquidPerpetualAuth._get_timestamp")
    def test_sign_order_params_post_request(self, ts_mock: MagicMock):
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
            }
        }
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(params),
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        # raw_signature = f'/linear/v1/orders&one=1&timestamp={int(self._get_timestamp() * 1e3)}'
        # expected_signature = hmac.new(bytes(self.secret_key.encode("utf-8")),
        #                               raw_signature.encode("utf-8"),
        #                               hashlib.sha256).hexdigest()

        params = json.loads(request.data)
        self.assertEqual(4, len(params))
        self.assertEqual(None, params.get("vaultAddress"))
        self.assertEqual("order", params.get("action")["type"])

    def test_sign_order_params_preserves_single_order_action(self):
        order = {
            "asset": 4, "isBuy": True, "limitPx": 1201, "sz": 0.01, "reduceOnly": False,
            "orderType": {"limit": {"tif": "Gtc"}}, "cloid": "0x000000000000000000000000000ee056",
        }
        with patch.object(self.auth, "sign_l1_action", return_value={"signature": "test"}):
            payload = self.auth._sign_order_params(
                {"orders": order, "grouping": "na"}, "https://test.url/exchange", 123)

        self.assertEqual(payload["action"], {
            "type": "order",
            "orders": [{
                "a": 4, "b": True, "p": "1201", "s": "0.01", "r": False,
                "t": {"limit": {"tif": "Gtc"}}, "c": "0x000000000000000000000000000ee056",
            }],
            "grouping": "na",
        })

    def test_sign_order_params_signs_order_list_with_grouping_and_builder(self):
        orders = [
            {
                "asset": 4, "isBuy": False, "limitPx": 1100, "sz": 0.01, "reduceOnly": True,
                "orderType": {"trigger": {"triggerPx": 1100, "tpsl": "tp", "isMarket": True}},
                "cloid": "0x00000000000000000000000000000001",
            },
            {
                "asset": 4, "isBuy": False, "limitPx": 900, "sz": 0.01, "reduceOnly": True,
                "orderType": {"trigger": {"triggerPx": 900, "tpsl": "sl", "isMarket": True}},
                "cloid": "0x00000000000000000000000000000002",
            },
        ]
        builder = {"b": "0x0000000000000000000000000000000000000001", "f": 1}
        with patch.object(self.auth, "sign_l1_action", return_value={"signature": "test"}):
            payload = self.auth._sign_order_params(
                {"orders": orders, "grouping": "positionTpsl", "builder": builder},
                "https://test.url/exchange", 123)

        action = payload["action"]
        self.assertEqual("positionTpsl", action["grouping"])
        self.assertEqual(builder, action["builder"])
        self.assertEqual(2, len(action["orders"]))
        self.assertEqual("tp", action["orders"][0]["t"]["trigger"]["tpsl"])
        self.assertEqual("sl", action["orders"][1]["t"]["trigger"]["tpsl"])
        self.assertEqual(
            ["isMarket", "triggerPx", "tpsl"],
            list(action["orders"][0]["t"]["trigger"]),
            "Trigger wire field order is part of Hyperliquid's msgpack signature hash.",
        )

    def test_trigger_order_signing_preserves_vault_and_testnet_rules(self):
        order = {
            "asset": 4, "isBuy": False, "limitPx": 900, "sz": 0.01, "reduceOnly": True,
            "orderType": {"trigger": {"triggerPx": 950, "tpsl": "sl", "isMarket": True}},
            "cloid": "0x00000000000000000000000000000001",
        }
        vault_auth = HyperliquidPerpetualAuth(
            api_address="0x0000000000000000000000000000000000000001",
            api_secret=self.api_secret,
            use_vault=True,
        )
        with patch.object(vault_auth, "sign_l1_action", return_value={"signature": "test"}) as sign_mock:
            vault_payload = vault_auth._sign_order_params(
                {"orders": order, "grouping": "na"}, "https://api.hyperliquid.xyz/exchange", 123)

        self.assertEqual(vault_auth._vault_address, vault_payload["vaultAddress"])
        self.assertTrue(sign_mock.call_args.args[-1])
        self.assertEqual("sl", vault_payload["action"]["orders"][0]["t"]["trigger"]["tpsl"])

        with patch.object(self.auth, "sign_l1_action", return_value={"signature": "test"}) as sign_mock:
            testnet_payload = self.auth._sign_order_params(
                {"orders": order, "grouping": "na"},
                "https://api.hyperliquid-testnet.xyz/exchange", 123)

        self.assertIsNone(testnet_payload["vaultAddress"])
        self.assertFalse(sign_mock.call_args.args[-1])
        self.assertNotIn("builder", testnet_payload["action"])

    def test_sign_cancel_params_uses_oid_action_for_activated_trigger_child(self):
        with patch.object(self.auth, "sign_l1_action", return_value={"signature": "test"}):
            payload = self.auth._sign_cancel_params(
                {"cancels": {"asset": 4, "oid": 202}}, "https://test.url/exchange", 123)

        self.assertEqual({
            "type": "cancel",
            "cancels": [{"a": 4, "o": 202}],
        }, payload["action"])


class HyperliquidPerpetualAuthValidationTests(TestCase):
    """Construction-time validation of api_address and api_secret (issue #7866)."""

    VALID_KEY = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
    DERIVED_ADDRESS = "0x836eE2b55d173245832995082a8600709c38D099"
    UNRELATED_ADDRESS = "0x000000000000000000000000000000000000dEaD"

    def test_invalid_private_key_format_raises(self):
        with self.assertRaises(ValueError) as ctx:
            HyperliquidPerpetualAuth(
                api_address=self.DERIVED_ADDRESS,
                api_secret="not-a-valid-hex-key",
                use_vault=False,
            )
        self.assertIn("private key", str(ctx.exception).lower())

    def test_invalid_address_format_raises(self):
        with self.assertRaises(ValueError) as ctx:
            HyperliquidPerpetualAuth(
                api_address="not_an_address",
                api_secret=self.VALID_KEY,
                use_vault=False,
            )
        self.assertIn("address", str(ctx.exception).lower())

    def test_address_does_not_match_key_raises(self):
        with self.assertRaises(ValueError) as ctx:
            HyperliquidPerpetualAuth(
                api_address=self.UNRELATED_ADDRESS,
                api_secret=self.VALID_KEY,
                use_vault=False,
            )
        message = str(ctx.exception).lower()
        self.assertIn("does not derive", message)
        self.assertIn(self.DERIVED_ADDRESS.lower(), message)

    def test_vault_mode_bypasses_address_match_check(self):
        # In vault mode, the supplied address is the vault, not the wallet derived
        # from the private key, so the derive-and-compare check must be skipped.
        auth = HyperliquidPerpetualAuth(
            api_address=self.UNRELATED_ADDRESS,
            api_secret=self.VALID_KEY,
            use_vault=True,
        )
        self.assertEqual(self.UNRELATED_ADDRESS, auth._vault_address)

    def test_api_wallet_mode_bypasses_address_match_check(self):
        # In api_wallet mode the private key is a Hyperliquid API/agent wallet
        # key, which by design does not derive to the user's trading address.
        # The derive-and-compare check must be skipped so the documented
        # api_wallet flow is not rejected (see #7866).
        auth = HyperliquidPerpetualAuth(
            api_address=self.UNRELATED_ADDRESS,
            api_secret=self.VALID_KEY,
            use_vault=False,
            connection_mode="api_wallet",
        )
        self.assertEqual(self.UNRELATED_ADDRESS, auth._api_address)
        self.assertIsNone(auth._vault_address)
        # The agent key is still parsed into a usable signing wallet even though
        # it does not match the supplied trading address.
        self.assertEqual(self.DERIVED_ADDRESS.lower(), auth.wallet.address.lower())

    def test_empty_inputs_raise(self):
        with self.assertRaises(ValueError):
            HyperliquidPerpetualAuth(api_address="", api_secret=self.VALID_KEY, use_vault=False)
        with self.assertRaises(ValueError):
            HyperliquidPerpetualAuth(api_address=self.DERIVED_ADDRESS, api_secret="", use_vault=False)

    # --- is_key_authorized: the mode-agnostic connect-time authority check (#7866, api_wallet gap) ---

    OTHER_AGENT = "0x0000000000000000000000000000000000000001"

    def test_is_key_authorized_owner_key(self):
        # arb_wallet: the key's address IS the account -> authorised with no agent list.
        self.assertTrue(
            HyperliquidPerpetualAuth.is_key_authorized(self.DERIVED_ADDRESS, self.DERIVED_ADDRESS, []))

    def test_is_key_authorized_approved_agent(self):
        # api_wallet: the key's address is an approved agent of the (different) account.
        agents = [{"address": self.DERIVED_ADDRESS, "name": "hb", "validUntil": 0}]
        self.assertTrue(
            HyperliquidPerpetualAuth.is_key_authorized(self.DERIVED_ADDRESS, self.UNRELATED_ADDRESS, agents))

    def test_is_key_authorized_unapproved_agent(self):
        agents = [{"address": self.OTHER_AGENT, "name": "someone-else", "validUntil": 0}]
        self.assertFalse(
            HyperliquidPerpetualAuth.is_key_authorized(self.DERIVED_ADDRESS, self.UNRELATED_ADDRESS, agents))

    def test_is_key_authorized_empty_agents_non_owner(self):
        # account has no approved agents and the key is not the owner -> cannot trade.
        self.assertFalse(
            HyperliquidPerpetualAuth.is_key_authorized(self.DERIVED_ADDRESS, self.UNRELATED_ADDRESS, []))

    def test_is_key_authorized_is_checksum_insensitive(self):
        agents = [{"address": self.DERIVED_ADDRESS.lower()}]
        self.assertTrue(
            HyperliquidPerpetualAuth.is_key_authorized(
                self.DERIVED_ADDRESS.lower(), self.UNRELATED_ADDRESS.lower(), agents))
