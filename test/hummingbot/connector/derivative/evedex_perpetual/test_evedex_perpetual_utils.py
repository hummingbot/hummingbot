from unittest import TestCase

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_utils import (
    EvedexPerpetualConfigMap,
    EvedexPerpetualTestnetConfigMap,
    validate_auth_mode,
    validate_bool,
)


class EvedexPerpetualUtilsTests(TestCase):
    def test_validate_auth_mode_succeed(self):
        """Test valid auth modes are accepted."""
        allowed = ("wallet", "api_key")
        validations = [validate_auth_mode(value) for value in allowed]

        for index, validation in enumerate(validations):
            self.assertEqual(validation, allowed[index])

    def test_validate_auth_mode_fails(self):
        """Test invalid auth mode raises ValueError."""
        wrong_value = "invalid_mode"
        allowed = ("wallet", "api_key")

        with self.assertRaises(ValueError) as context:
            validate_auth_mode(wrong_value)

        self.assertIn("Invalid auth mode", str(context.exception))

    def test_cls_validate_auth_mode_succeed(self):
        """Test config map validates auth modes correctly."""
        allowed = ("wallet", "api_key")
        validations = [EvedexPerpetualConfigMap.validate_mode(value) for value in allowed]

        for validation in validations:
            self.assertIn(validation, allowed)

    def test_cls_validate_auth_mode_fails(self):
        """Test config map raises on invalid auth mode."""
        wrong_value = "invalid_mode"

        with self.assertRaises(ValueError) as context:
            EvedexPerpetualConfigMap.validate_mode(wrong_value)

        self.assertIn("Invalid auth mode", str(context.exception))

    def test_validate_bool_truthy(self):
        """Test truthy values are correctly validated."""
        truthy = {"yes", "y", "true", "1"}
        for value in truthy:
            self.assertTrue(validate_bool(value))

    def test_validate_bool_falsy(self):
        """Test falsy values are correctly validated."""
        falsy = {"no", "n", "false", "0"}
        for value in falsy:
            self.assertFalse(validate_bool(value))

    def test_validate_bool_invalid(self):
        """Test invalid bool value raises ValueError."""
        with self.assertRaises(ValueError):
            validate_bool("maybe")

    def test_validate_bool_with_spaces(self):
        """Test bool validation handles whitespace."""
        self.assertTrue(validate_bool("  YES  "))
        self.assertFalse(validate_bool("  No  "))

    def test_validate_bool_boolean_passthrough(self):
        """Test actual booleans pass through."""
        self.assertTrue(validate_bool(True))
        self.assertFalse(validate_bool(False))

    def test_testnet_config_map_validate_mode_succeed(self):
        """Test testnet config map validates auth modes correctly."""
        allowed = ("wallet", "api_key")
        validations = [EvedexPerpetualTestnetConfigMap.validate_mode(value) for value in allowed]

        for validation in validations:
            self.assertIn(validation, allowed)

    def test_testnet_config_map_validate_mode_fails(self):
        """Test testnet config map raises on invalid auth mode."""
        wrong_value = "invalid_mode"

        with self.assertRaises(ValueError) as context:
            EvedexPerpetualTestnetConfigMap.validate_mode(wrong_value)

        self.assertIn("Invalid auth mode", str(context.exception))

    def test_validate_auth_mode_case_insensitive(self):
        """Test auth mode validation is case insensitive."""
        self.assertEqual(validate_auth_mode("WALLET"), "wallet")
        self.assertEqual(validate_auth_mode("API_KEY"), "api_key")
        self.assertEqual(validate_auth_mode("Wallet"), "wallet")
