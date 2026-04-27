import json
from unittest import TestCase

from pydantic import ValidationError

from hummingbot.connector.exchange.lighter.lighter_utils import (
    LighterConfigMap,
    LighterTestnetConfigMap,
    is_exchange_information_valid,
)


class LighterUtilsTests(TestCase):
    @staticmethod
    def _encrypted_secret_payload_hex() -> str:
        payload = {"crypto": {}, "version": 3, "alias": ""}
        return json.dumps(payload).encode("utf-8").hex()

    def test_config_map_title(self):
        self.assertEqual("lighter", LighterConfigMap.model_config.get("title"))

    def test_testnet_config_map_title(self):
        self.assertEqual("lighter_testnet", LighterTestnetConfigMap.model_config.get("title"))

    def test_connect_flow_prompts_for_api_key_instead_of_private_key(self):
        mainnet_api_key = LighterConfigMap.model_fields["lighter_api_key_private_key"].json_schema_extra
        testnet_api_key = LighterTestnetConfigMap.model_fields["lighter_testnet_api_key_private_key"].json_schema_extra

        self.assertTrue(mainnet_api_key["prompt_on_new"])
        self.assertIn("private key", mainnet_api_key["prompt"].lower())

        self.assertTrue(testnet_api_key["prompt_on_new"])
        self.assertIn("private key", testnet_api_key["prompt"].lower())

        # Verify no (now-removed) EOA private key field is present
        self.assertNotIn("lighter_private_key", LighterConfigMap.model_fields)
        self.assertNotIn("lighter_testnet_private_key", LighterTestnetConfigMap.model_fields)

    def test_is_exchange_information_valid(self):
        self.assertTrue(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "perp", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": "halted"}))
        self.assertFalse(is_exchange_information_valid({"market_type": "spot", "status": "active"}))

    def test_mainnet_config_validates_integer_indexes(self):
        cfg = LighterConfigMap(
            lighter_api_key="0x" + ("a" * 64),
            lighter_api_secret=" 123 ",
            lighter_account_index=" 456 ",
        )

        self.assertEqual("123", cfg.lighter_api_key_index.get_secret_value())
        self.assertEqual("456", cfg.lighter_account_index.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterConfigMap(
                lighter_api_key="0x" + ("a" * 64),
                lighter_api_secret="not-an-int",
                lighter_account_index="456",
            )

        cfg_empty = LighterConfigMap(
            lighter_api_key="0x" + ("a" * 64),
            lighter_api_secret="",
            lighter_account_index="",
        )
        self.assertEqual("", cfg_empty.lighter_api_key_index.get_secret_value())
        self.assertEqual("", cfg_empty.lighter_account_index.get_secret_value())

    def test_testnet_config_validates_integer_indexes(self):
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key="0x" + ("a" * 64),
            lighter_testnet_api_secret=" 7 ",
            lighter_testnet_account_index=" 890 ",
        )

        self.assertEqual("7", cfg.lighter_testnet_api_key_index.get_secret_value())
        self.assertEqual("890", cfg.lighter_testnet_account_index.get_secret_value())

        cfg_empty = LighterTestnetConfigMap(
            lighter_testnet_api_key="0x" + ("a" * 64),
            lighter_testnet_api_secret="",
            lighter_testnet_account_index="",
        )
        self.assertEqual("", cfg_empty.lighter_testnet_api_key_index.get_secret_value())
        self.assertEqual("", cfg_empty.lighter_testnet_account_index.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterTestnetConfigMap(
                lighter_testnet_api_key="0x" + ("a" * 64),
                lighter_testnet_api_secret="7",
                lighter_testnet_account_index="abc",
            )

    def test_mainnet_config_validates_hex_api_key(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterConfigMap(
            lighter_api_secret="123",
            lighter_account_index="456",
            lighter_api_key=hex_key,
        )
        self.assertEqual(hex_key, cfg.lighter_api_key_private_key.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterConfigMap(
                lighter_api_secret="123",
                lighter_account_index="456",
                lighter_api_key="not-hex",
            )

    def test_testnet_config_validates_hex_api_key(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key=hex_key,
            lighter_testnet_api_secret="7",
            lighter_testnet_account_index="890",
        )
        self.assertEqual(hex_key, cfg.lighter_testnet_api_key_private_key.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterTestnetConfigMap(
                lighter_testnet_api_key="not-hex",
                lighter_testnet_api_secret="7",
                lighter_testnet_account_index="890",
            )

    def test_mainnet_config_accepts_encrypted_index_values_before_decrypt(self):
        encrypted = self._encrypted_secret_payload_hex()
        cfg = LighterConfigMap(
            lighter_api_key=encrypted,
            lighter_api_secret=encrypted,
            lighter_account_index=encrypted,
        )

        self.assertEqual(encrypted, cfg.lighter_api_key_index.get_secret_value())
        self.assertEqual(encrypted, cfg.lighter_account_index.get_secret_value())

    def test_testnet_config_accepts_encrypted_index_values_before_decrypt(self):
        encrypted = self._encrypted_secret_payload_hex()
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key="0x" + ("a" * 64),
            lighter_testnet_api_secret=encrypted,
            lighter_testnet_account_index=encrypted,
        )

        self.assertEqual(encrypted, cfg.lighter_testnet_api_key_index.get_secret_value())
        self.assertEqual(encrypted, cfg.lighter_testnet_account_index.get_secret_value())

    # ------------------------------------------------------------------ #
    # Migration else-branch coverage                                       #
    # ------------------------------------------------------------------ #

    def test_mainnet_migrate_new_names_directly_no_legacy_fields(self):
        """Using new field names directly should still work (triggers else-branches in migration)."""
        hex_key = "0x" + ("a" * 64)
        cfg = LighterConfigMap(
            lighter_api_key_index="42",
            lighter_account_index="999",
            lighter_api_key_private_key=hex_key,
        )
        self.assertEqual("42", cfg.lighter_api_key_index.get_secret_value())
        self.assertEqual("999", cfg.lighter_account_index.get_secret_value())
        self.assertEqual(hex_key, cfg.lighter_api_key_private_key.get_secret_value())

    def test_mainnet_migrate_discards_old_fields_when_new_fields_also_present(self):
        """When both old and new field names present, new wins and old is discarded (else-branch)."""
        hex_key = "0x" + ("a" * 64)
        cfg = LighterConfigMap(
            lighter_api_key_index="5",
            lighter_api_secret="99",           # old name present but new also present → discarded
            lighter_account_index="200",
            lighter_api_key_private_key=hex_key,
            lighter_api_key="0x" + ("b" * 64),  # old name present but new also present → discarded
        )
        self.assertEqual("5", cfg.lighter_api_key_index.get_secret_value())
        self.assertEqual("200", cfg.lighter_account_index.get_secret_value())
        self.assertEqual(hex_key, cfg.lighter_api_key_private_key.get_secret_value())

    def test_mainnet_migrate_discards_lighter_private_key_and_public_key(self):
        """lighter_private_key and lighter_api_key_public_key from old configs are silently removed."""
        hex_key = "0x" + ("a" * 64)
        cfg = LighterConfigMap(
            lighter_api_key_index="3",
            lighter_account_index="100",
            lighter_api_key_private_key=hex_key,
            lighter_private_key="0xold_l1_key",       # should be discarded
            lighter_api_key_public_key="0xold_pub",   # should be discarded
        )
        self.assertEqual("3", cfg.lighter_api_key_index.get_secret_value())
        self.assertFalse(hasattr(cfg, "lighter_private_key"))
        self.assertFalse(hasattr(cfg, "lighter_api_key_public_key"))

    def test_testnet_migrate_new_names_directly_no_legacy_fields(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key_index="8",
            lighter_testnet_account_index="888",
            lighter_testnet_api_key_private_key=hex_key,
        )
        self.assertEqual("8", cfg.lighter_testnet_api_key_index.get_secret_value())
        self.assertEqual("888", cfg.lighter_testnet_account_index.get_secret_value())

    def test_testnet_migrate_discards_old_fields_when_new_fields_also_present(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key_index="11",
            lighter_testnet_api_secret="55",            # old → discarded
            lighter_testnet_account_index="300",
            lighter_testnet_api_key_private_key=hex_key,
            lighter_testnet_api_key="0x" + ("c" * 64),  # old → discarded
        )
        self.assertEqual("11", cfg.lighter_testnet_api_key_index.get_secret_value())
        self.assertEqual("300", cfg.lighter_testnet_account_index.get_secret_value())
        self.assertEqual(hex_key, cfg.lighter_testnet_api_key_private_key.get_secret_value())

    def test_testnet_migrate_discards_legacy_key_fields(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key_index="1",
            lighter_testnet_account_index="50",
            lighter_testnet_api_key_private_key=hex_key,
            lighter_testnet_private_key="0xold_l1",           # discarded
            lighter_testnet_api_key_public_key="0xold_pub",   # discarded
        )
        self.assertEqual("1", cfg.lighter_testnet_api_key_index.get_secret_value())
        self.assertFalse(hasattr(cfg, "lighter_testnet_private_key"))
        self.assertFalse(hasattr(cfg, "lighter_testnet_api_key_public_key"))

    # ------------------------------------------------------------------ #
    # Empty private key must raise (unlike index fields where "" is OK)   #
    # ------------------------------------------------------------------ #

    def test_mainnet_empty_private_key_raises(self):
        with self.assertRaises(Exception) as ctx:
            LighterConfigMap(
                lighter_api_key_index="4",
                lighter_account_index="100",
                lighter_api_key_private_key="",
            )
        self.assertIn("hex string", str(ctx.exception).lower())

    def test_testnet_empty_private_key_raises(self):
        with self.assertRaises(Exception) as ctx:
            LighterTestnetConfigMap(
                lighter_testnet_api_key_index="4",
                lighter_testnet_account_index="100",
                lighter_testnet_api_key_private_key="",
            )
        self.assertIn("hex string", str(ctx.exception).lower())

    # ------------------------------------------------------------------ #
    # Additional is_exchange_information_valid branches                   #
    # ------------------------------------------------------------------ #

    def test_is_exchange_information_valid_inactive_statuses(self):
        for bad_status in ("inactive", "disabled", "suspended", "delisted"):
            with self.subTest(status=bad_status):
                self.assertFalse(
                    is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": bad_status})
                )

    def test_is_exchange_information_valid_empty_market_type_passes_through(self):
        """market_type absent or empty → not rejected by market-type check, falls through to status/symbol checks."""
        self.assertTrue(is_exchange_information_valid({"symbol": "ETH/USDC", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"status": "active"}))  # missing symbol

    # ------------------------------------------------------------------ #
    # Async helper functions tested via asyncio.run                       #
    # ------------------------------------------------------------------ #

    def test_fetch_lighter_public_key_returns_key_on_success(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.exchange.lighter.lighter_utils import fetch_lighter_public_key

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": [{"public_key": "0xdeadbeef"}]})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.run(fetch_lighter_public_key("lighter", "100", "4"))

        self.assertEqual("0xdeadbeef", result)

    def test_fetch_lighter_public_key_returns_none_when_no_api_keys(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.exchange.lighter.lighter_utils import fetch_lighter_public_key

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.run(fetch_lighter_public_key("lighter", "100", "4"))

        self.assertIsNone(result)

    def test_fetch_lighter_public_key_returns_none_on_http_error(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.exchange.lighter.lighter_utils import fetch_lighter_public_key

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.run(fetch_lighter_public_key("lighter", "100", "4"))

        self.assertIsNone(result)

    def test_fetch_lighter_public_key_returns_none_on_network_exception(self):
        import asyncio
        from unittest.mock import patch

        from hummingbot.connector.exchange.lighter.lighter_utils import fetch_lighter_public_key

        with patch("aiohttp.ClientSession", side_effect=Exception("connection refused")):
            result = asyncio.run(fetch_lighter_public_key("lighter", "100", "4"))

        self.assertIsNone(result)

    def test_fetch_lighter_public_key_uses_testnet_url_for_testnet_connector(self):
        """Uses TESTNET_REST_URL when connector_name is lighter_testnet."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.exchange.lighter.lighter_utils import fetch_lighter_public_key

        captured_url = []

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        def capture_get(url, **kwargs):
            captured_url.append(url)
            return mock_response

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=capture_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        from hummingbot.connector.exchange.lighter import lighter_constants as lc

        with patch("aiohttp.ClientSession", return_value=mock_session):
            asyncio.run(fetch_lighter_public_key("lighter_testnet", "100", "4"))

        self.assertIn(lc.TESTNET_REST_URL, captured_url[0])

    def test_fetch_lighter_public_key_uses_testnet_url_for_perpetual_testnet_connector(self):
        """Uses TESTNET_REST_URL when connector_name is lighter_perpetual_testnet."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as lpc
        from hummingbot.connector.exchange.lighter.lighter_utils import fetch_lighter_public_key

        captured_url = []

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        def capture_get(url, **kwargs):
            captured_url.append(url)
            return mock_response

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=capture_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            asyncio.run(fetch_lighter_public_key("lighter_perpetual_testnet", "100", "4"))

        self.assertIn(lpc.TESTNET_REST_URL, captured_url[0])

    def test_validate_lighter_api_key_index_returns_none_when_key_found(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.exchange.lighter.lighter_utils import validate_lighter_api_key_index

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": [{"public_key": "0xabc"}]})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.run(validate_lighter_api_key_index("lighter", "100", "4"))

        self.assertIsNone(result)

    def test_validate_lighter_api_key_index_returns_error_when_key_not_found(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from hummingbot.connector.exchange.lighter.lighter_utils import validate_lighter_api_key_index

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"api_keys": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = asyncio.run(validate_lighter_api_key_index("lighter", "100", "4"))

        self.assertIsNotNone(result)
        self.assertIn("4", result)

    def test_validate_lighter_api_key_index_returns_none_on_exception(self):
        import asyncio
        from unittest.mock import patch

        from hummingbot.connector.exchange.lighter.lighter_utils import validate_lighter_api_key_index

        with patch("aiohttp.ClientSession", side_effect=Exception("timeout")):
            result = asyncio.run(validate_lighter_api_key_index("lighter", "100", "4"))

        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # Additional branch coverage for missing lines                         #
    # ------------------------------------------------------------------ #

    def test_mainnet_account_index_validates_non_integer_raises(self):
        """lighter_account_index='not-an-int' must raise ValidationError (covers line 130)."""
        with self.assertRaises(ValidationError):
            LighterConfigMap(
                lighter_api_key_private_key="0x" + ("a" * 64),
                lighter_api_key_index="5",
                lighter_account_index="not-an-int",
            )

    def test_testnet_api_key_index_validates_non_integer_raises(self):
        """lighter_testnet_api_key_index='not-an-int' must raise ValidationError (covers line 229)."""
        with self.assertRaises(ValidationError):
            LighterTestnetConfigMap(
                lighter_testnet_api_key_private_key="0x" + ("a" * 64),
                lighter_testnet_api_key_index="not-an-int",
                lighter_testnet_account_index="890",
            )

    def test_testnet_api_key_private_key_accepts_encrypted_blob(self):
        """Encrypted blob as testnet private key must pass through (covers line 253)."""
        encrypted = self._encrypted_secret_payload_hex()
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key_private_key=encrypted,
            lighter_testnet_api_key_index="0",
            lighter_testnet_account_index="0",
        )
        self.assertEqual(encrypted, cfg.lighter_testnet_api_key_private_key.get_secret_value())

    def test_mainnet_migrate_legacy_fields_with_non_dict_is_returned_unchanged(self):
        """migrate_legacy_fields must return non-dict data unchanged (covers line 90)."""
        result = LighterConfigMap.migrate_legacy_fields("not-a-dict")
        self.assertEqual("not-a-dict", result)

    def test_testnet_migrate_legacy_fields_with_non_dict_is_returned_unchanged(self):
        """testnet migrate_legacy_fields must return non-dict data unchanged (covers line 202)."""
        result = LighterTestnetConfigMap.migrate_legacy_fields("not-a-dict")
        self.assertEqual("not-a-dict", result)
