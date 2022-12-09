
import unittest

import hummingbot.client.config.config_validators as config_validators
from hummingbot.client.settings import AllConnectorSettings


class ConfigValidatorsTests(unittest.TestCase):
    def test_validation_does_not_fail_with_valid_timestamp_string(self):
        timestamp_string = "2021-06-23 10:15:20"

        self.assertIsNone(config_validators.validate_datetime_iso_string(timestamp_string))

    def test_validation_fails_with_valid_timestamp_string(self):
        timestamp_string = "21-6-23 10:15:20"
        validation_error = config_validators.validate_datetime_iso_string(timestamp_string)
        self.assertEqual(validation_error, "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)")

    def test_validate_exchange_connector_exist(self):
        exchange = "binance"

        self.assertIsNone(config_validators.validate_exchange(exchange))

    def test_validate_exchange_connector_does_not_exist(self):
        non_existant_exchange = "TEST_NON_EXISTANT_EXCHANGE"

        validation_error = config_validators.validate_exchange(non_existant_exchange)
        self.assertEqual(validation_error, f"Invalid exchange, please choose value from {AllConnectorSettings.get_exchange_names()}")

    def test_validate_derivative_connector_exist(self):
        derivative = "binance_perpetual"

        self.assertIsNone(config_validators.validate_derivative(derivative))

    def test_validate_derivative_connector_does_not_exist(self):
        non_existant_derivative = "TEST_NON_EXISTANT_DERIVATIVE"

        validation_error = config_validators.validate_derivative(non_existant_derivative)
        self.assertEqual(validation_error, f"Invalid derivative, please choose value from {AllConnectorSettings.get_derivative_names()}")

    def test_validate_connector_connector_exist(self):
        connector = "binance"

        self.assertIsNone(config_validators.validate_connector(connector))

    def test_validate_connector_connector_does_not_exist(self):
        non_existant_connector = "TEST_NON_EXISTANT_CONNECTOR"

        validation_error = config_validators.validate_connector(non_existant_connector)
        self.assertEqual(validation_error, f"Invalid connector, please choose value from {AllConnectorSettings.get_connector_settings().keys()}")

    def test_validate_bool_succeed(self):
        valid_values = ['true', 'yes', 'y', 'false', 'no', 'n']

        validations = [config_validators.validate_bool(value) for value in valid_values]
        for validation in validations:
            self.assertIsNone(validation)

    def test_validate_bool_fails(self):
        wrong_value = "ye"
        valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')

        validation_error = config_validators.validate_bool(wrong_value)
        self.assertEqual(validation_error, f"Invalid value, please choose value from {valid_values}")

    def test_validate_int_without_min_and_max_succeed(self):
        value = 1

        validation = config_validators.validate_int(value)
        self.assertIsNone(validation)

    def test_validate_int_wrong_value_fails(self):
        value = "wrong_value"

        validation = config_validators.validate_int(value)
        self.assertEqual(validation, f"{value} is not in integer format.")

    def test_validate_int_with_min_and_max_exclusive_succeed(self):
        value = 1
        min_value = 0
        max_value = 2
        inclusive = False

        validation = config_validators.validate_int(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_int_with_min_and_max_inclusive_succeed(self):
        value = 1
        min_value = 0
        max_value = 1
        inclusive = True

        validation = config_validators.validate_int(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_int_with_min_and_max_exclusive_fails(self):
        value = 1
        min_value = 0
        max_value = 1
        inclusive = False

        validation = config_validators.validate_int(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be between {min_value} and {max_value} (exclusive).")

    def test_validate_int_with_min_and_max_inclusive_fails(self):
        value = 5
        min_value = 0
        max_value = 1
        inclusive = True

        validation = config_validators.validate_int(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be between {min_value} and {max_value}.")

    def test_validate_int_with_min_exclusive_succeed(self):
        value = 1
        min_value = 0
        inclusive = False

        validation = config_validators.validate_int(value, min_value=min_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_int_with_min_inclusive_succeed(self):
        value = 1
        min_value = 0
        inclusive = True

        validation = config_validators.validate_int(value, min_value=min_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_int_with_min_exclusive_fails(self):
        value = 1
        min_value = 1
        inclusive = False

        validation = config_validators.validate_int(value, min_value=min_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be more than {min_value}.")

    def test_validate_int_with_min_inclusive_fails(self):
        value = 1
        min_value = 2
        inclusive = True

        validation = config_validators.validate_int(value, min_value=min_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value cannot be less than {min_value}.")

    def test_validate_int_with_max_exclusive_succeed(self):
        value = 1
        max_value = 2
        inclusive = False

        validation = config_validators.validate_int(value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_int_with_max_inclusive_succeed(self):
        value = 1
        max_value = 1
        inclusive = True

        validation = config_validators.validate_int(value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_int_with_max_exclusive_fails(self):
        value = 1
        max_value = 1
        inclusive = False

        validation = config_validators.validate_int(value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be less than {max_value}.")

    def test_validate_int_with_max_inclusive_fails(self):
        value = 5
        max_value = 1
        inclusive = True

        validation = config_validators.validate_int(value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value cannot be more than {max_value}.")

    def test_validate_float_without_min_and_max_succeed(self):
        value = 1.0

        validation = config_validators.validate_float(value)
        self.assertIsNone(validation)

    def test_validate_float_wrong_value_fails(self):
        value = "wrong_value"

        validation = config_validators.validate_float(value)
        self.assertEqual(validation, f"{value} is not in integer format.")

    def test_validate_float_with_min_and_max_exclusive_succeed(self):
        value = 1.0
        min_value = 0.0
        max_value = 2.0
        inclusive = False

        validation = config_validators.validate_float(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_float_with_min_and_max_inclusive_succeed(self):
        value = 1.0
        min_value = 0.0
        max_value = 1.0
        inclusive = True

        validation = config_validators.validate_float(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_float_with_min_and_max_exclusive_fails(self):
        value = 1.0
        min_value = 0.0
        max_value = 1.0
        inclusive = False

        validation = config_validators.validate_float(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be between {min_value} and {max_value} (exclusive).")

    def test_validate_float_with_min_and_max_inclusive_fails(self):
        value = 5.0
        min_value = 0.0
        max_value = 1.0
        inclusive = True

        validation = config_validators.validate_float(value, min_value=min_value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be between {min_value} and {max_value}.")

    def test_validate_float_with_min_exclusive_succeed(self):
        value = 1.0
        min_value = 0.0
        inclusive = False

        validation = config_validators.validate_float(value, min_value=min_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_float_with_min_inclusive_succeed(self):
        value = 1.0
        min_value = 0.0
        inclusive = True

        validation = config_validators.validate_float(value, min_value=min_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_float_with_min_exclusive_fails(self):
        value = 1.0
        min_value = 1.0
        inclusive = False

        validation = config_validators.validate_float(value, min_value=min_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be more than {min_value}.")

    def test_validate_float_with_min_inclusive_fails(self):
        value = 1.0
        min_value = 2.0
        inclusive = True

        validation = config_validators.validate_float(value, min_value=min_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value cannot be less than {min_value}.")

    def test_validate_float_with_max_exclusive_succeed(self):
        value = 1.0
        max_value = 2.0
        inclusive = False

        validation = config_validators.validate_float(value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_float_with_max_inclusive_succeed(self):
        value = 1.0
        max_value = 1.0
        inclusive = True

        validation = config_validators.validate_float(value, max_value=max_value, inclusive=inclusive)
        self.assertIsNone(validation)

    def test_validate_float_with_max_exclusive_fails(self):
        value = 1.0
        max_value = 1.0
        inclusive = False

        validation = config_validators.validate_float(value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value must be less than {max_value}.")

    def test_validate_float_with_max_inclusive_fails(self):
        value = 5.0
        max_value = 1.0
        inclusive = True

        validation = config_validators.validate_float(value, max_value=max_value, inclusive=inclusive)
        self.assertEqual(validation, f"Value cannot be more than {max_value}.")
