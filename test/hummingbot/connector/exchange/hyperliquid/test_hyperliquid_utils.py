from unittest import TestCase

from hummingbot.connector.exchange.hyperliquid.hyperliquid_utils import (
    HyperliquidConfigMap,
    HyperliquidTestnetConfigMap,
    validate_bool,
)


class HyperliquidUtilsTests(TestCase):
    pass

    def test_validate_bool_succeed(self):
        valid_values = ['true', 'yes', 'y', 'false', 'no', 'n']

        validations = [validate_bool(value) for value in valid_values]
        for validation in validations:
            self.assertIsNone(validation)

    def test_validate_bool_fails(self):
        wrong_value = "ye"
        valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')

        validation_error = validate_bool(wrong_value)
        self.assertEqual(validation_error, f"Invalid value, please choose value from {valid_values}")

    def test_cls_validate_bool_succeed(self):
        valid_values = ['true', 'yes', 'y', 'false', 'no', 'n']

        validations = [HyperliquidConfigMap.validate_bool(value) for value in valid_values]
        for validation in validations:
            self.assertTrue(validation)

    def test_cls_validate_bool_fails(self):
        wrong_value = "ye"
        valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
        with self.assertRaises(ValueError) as exception_context:
            HyperliquidConfigMap.validate_bool(wrong_value)
        self.assertEqual(str(exception_context.exception), f"Invalid value, please choose value from {valid_values}")

    def test_cls_testnet_validate_bool_succeed(self):
        valid_values = ['true', 'yes', 'y', 'false', 'no', 'n']

        validations = [HyperliquidTestnetConfigMap.validate_bool(value) for value in valid_values]
        for validation in validations:
            self.assertTrue(validation)

    def test_cls_testnet_validate_bool_fails(self):
        wrong_value = "ye"
        valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
        with self.assertRaises(ValueError) as exception_context:
            HyperliquidTestnetConfigMap.validate_bool(wrong_value)
        self.assertEqual(str(exception_context.exception), f"Invalid value, please choose value from {valid_values}")
