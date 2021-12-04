
import unittest

import hummingbot.client.config.config_validators as config_validators

from hummingbot.client.settings import AllConnectorSettings


class TimestampValidationTests(unittest.TestCase):
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
