from unittest import TestCase

import hummingbot.client.config.config_validators as config_validators


class TimestampValidationTests(TestCase):

    def test_validation_does_not_fail_with_valid_timestamp_string(self):
        timestamp_string = "2021-06-23 10:15:20"

        self.assertIsNone(config_validators.validate_timestamp_iso_string(timestamp_string))

    def test_validation_fails_with_valid_timestamp_string(self):
        timestamp_string = "21-6-23 10:15:20"
        validation_error = config_validators.validate_timestamp_iso_string(timestamp_string)
        self.assertEqual(validation_error, "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)")
