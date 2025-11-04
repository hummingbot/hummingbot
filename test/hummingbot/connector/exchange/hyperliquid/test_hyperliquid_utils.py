from unittest import TestCase

from hummingbot.connector.exchange.hyperliquid.hyperliquid_utils import (
    HyperliquidConfigMap,
    HyperliquidTestnetConfigMap,
    validate_mode,
)


class HyperliquidUtilsTests(TestCase):
    def test_validate_connection_mode_succeed(self):
        allowed = ('wallet', 'vault', 'api_wallet')
        validations = [validate_mode(value) for value in allowed]

        for validation in validations:
            self.assertIsNone(validation)

    def test_validate_connection_mode_fails(self):
        wrong_value = "api_vault"
        allowed = ('wallet', 'vault', 'api_wallet')
        validation_error = validate_mode(wrong_value)

        self.assertEqual(validation_error, f"Invalid mode '{wrong_value}', choose from: {allowed}")

    def test_cls_validate_connection_mode_succeed(self):
        allowed = ('wallet', 'vault', 'api_wallet')
        validations = [HyperliquidConfigMap.validate_hyperliquid_mode(value) for value in allowed]

        for validation in validations:
            self.assertTrue(validation)

    def test_cls_validate_connection_mode_fails(self):
        wrong_value = "api_vault"
        allowed = ('wallet', 'vault', 'api_wallet')

        with self.assertRaises(ValueError) as exception_context:
            HyperliquidConfigMap.validate_hyperliquid_mode(wrong_value)
        self.assertEqual(str(exception_context.exception), f"Invalid mode '{wrong_value}', choose from: {allowed}")

    def test_cls_testnet_validate_bool_succeed(self):
        allowed = ('wallet', 'vault', 'api_wallet')
        validations = [HyperliquidTestnetConfigMap.validate_hyperliquid_mode(value) for value in allowed]

        for validation in validations:
            self.assertTrue(validation)

    def test_cls_testnet_validate_bool_fails(self):
        wrong_value = "api_vault"
        allowed = ('wallet', 'vault', 'api_wallet')

        with self.assertRaises(ValueError) as exception_context:
            HyperliquidTestnetConfigMap.validate_hyperliquid_mode(wrong_value)
        self.assertEqual(str(exception_context.exception), f"Invalid mode '{wrong_value}', choose from: {allowed}")
