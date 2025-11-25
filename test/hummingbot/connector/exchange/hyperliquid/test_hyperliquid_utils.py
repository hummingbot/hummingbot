from unittest import TestCase

from hummingbot.connector.exchange.hyperliquid.hyperliquid_utils import (
    HyperliquidConfigMap,
    HyperliquidTestnetConfigMap,
    validate_bool,
    validate_wallet_mode,
)


class HyperliquidUtilsTests(TestCase):
    def test_validate_connection_mode_succeed(self):
        allowed = ('arb_wallet', 'api_wallet')
        validations = [validate_wallet_mode(value) for value in allowed]

        for index, validation in enumerate(validations):
            self.assertEqual(validation, allowed[index])

    def test_validate_connection_mode_fails(self):
        wrong_value = "api_vault"
        allowed = ('arb_wallet', 'api_wallet')

        with self.assertRaises(ValueError) as context:
            validate_wallet_mode(wrong_value)

        self.assertEqual(f"Invalid wallet mode '{wrong_value}', choose from: {allowed}", str(context.exception))

    def test_cls_validate_connection_mode_succeed(self):
        allowed = ('arb_wallet', 'api_wallet')
        validations = [HyperliquidConfigMap.validate_mode(value) for value in allowed]

        for validation in validations:
            self.assertTrue(validation)

    def test_cls_validate_use_vault_succeed(self):
        truthy = {"yes", "y", "true", "1"}
        falsy = {"no", "n", "false", "0"}
        true_validations = [validate_bool(value) for value in truthy]
        false_validations = [validate_bool(value) for value in falsy]

        for validation in true_validations:
            self.assertTrue(validation)

        for validation in false_validations:
            self.assertFalse(validation)

    def test_cls_validate_connection_mode_fails(self):
        wrong_value = "api_vault"
        allowed = ('arb_wallet', 'api_wallet')

        with self.assertRaises(ValueError) as context:
            HyperliquidConfigMap.validate_mode(wrong_value)

        self.assertEqual(f"Invalid wallet mode '{wrong_value}', choose from: {allowed}", str(context.exception))

    def test_cls_testnet_validate_bool_succeed(self):
        allowed = ('arb_wallet', 'api_wallet')
        validations = [HyperliquidTestnetConfigMap.validate_mode(value) for value in allowed]

        for validation in validations:
            self.assertTrue(validation)

    def test_cls_testnet_validate_bool_fails(self):
        wrong_value = "api_vault"
        allowed = ('arb_wallet', 'api_wallet')

        with self.assertRaises(ValueError) as context:
            HyperliquidTestnetConfigMap.validate_mode(wrong_value)

        self.assertEqual(f"Invalid wallet mode '{wrong_value}', choose from: {allowed}", str(context.exception))

    def test_validate_bool_invalid(self):
        with self.assertRaises(ValueError):
            validate_bool("maybe")

    def test_validate_bool_with_spaces(self):
        self.assertTrue(validate_bool("  YES  "))
        self.assertFalse(validate_bool("  No  "))

    def test_validate_bool_boolean_passthrough(self):
        self.assertTrue(validate_bool(True))
        self.assertFalse(validate_bool(False))

    def test_hyperliquid_address_strips_hl_prefix(self):
        corrected_address = HyperliquidConfigMap.validate_address("HL:abcdef123")

        self.assertEqual(corrected_address, "abcdef123")

    def test_hyperliquid_testnet_address_strips_hl_prefix(self):
        corrected_address = HyperliquidTestnetConfigMap.validate_address("HL:zzz8z8z")

        self.assertEqual(corrected_address, "zzz8z8z")
