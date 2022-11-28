import json
import unittest

from mock.mock import MagicMock, patch
from pydantic import SecretStr, ValidationError, validate_model

from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.connector.exchange.lbank.lbank_utils import LbankConfigMap


class LbankUtilsTest(unittest.TestCase):

    @patch("hummingbot.connector.exchange.lbank.lbank_utils.RSA")
    def test_lbank_config_map_configuration(self, rsa_mock: MagicMock):
        api_key = "someAPIKey"
        secret_key = "someSecretKey"
        LbankConfigMap(
            lbank_api_key=api_key,
            lbank_secret_key=secret_key,
            lbank_auth_method="HmacSHA256",
        )
        LbankConfigMap(
            lbank_api_key=api_key,
            lbank_secret_key=secret_key,
            lbank_auth_method="RSA",
        )

        rsa_key_str = LbankAuth.RSA_KEY_FORMAT.format(secret_key)
        rsa_mock.importKey.assert_called_once_with(rsa_key_str)

        with self.assertRaises(ValidationError):
            LbankConfigMap(
                # lbank_api_key=api_key,
                lbank_secret_key=secret_key,
                lbank_auth_method="HmacSHA256",
            )

        with self.assertRaises(ValidationError):
            LbankConfigMap(
                lbank_api_key=api_key,
                # lbank_secret_key=secret_key,
                lbank_auth_method="HmacSHA256",
            )

        with self.assertRaises(ValidationError):
            LbankConfigMap(
                lbank_api_key=api_key,
                lbank_secret_key=secret_key,
                # lbank_auth_method="HmacSHA256",
            )

    def test_lbank_config_map_incremental_configuration(self):
        config = LbankConfigMap.construct()
        config.lbank_api_key = "someAPIKey"
        config.lbank_secret_key = "someSecretKey"
        config.lbank_auth_method = "HmacSHA256"

        results = validate_model(type(config), json.loads(config.json()))

        self.assertIsNone(results[2])

    def test_validate_auth_method(self):

        result = LbankConfigMap.validate_auth_method(value="RSA")
        self.assertEqual(result, "RSA")

        result = LbankConfigMap.validate_auth_method(value="HmacSHA256")
        self.assertEqual(result, "HmacSHA256")

        with self.assertRaises(ValueError) as exception_context:
            LbankConfigMap.validate_auth_method(value="invalid_method")

        self.assertEqual(
            "Authentication Method: invalid_method not supported. Supported methods are RSA/HmacSHA256",
            str(exception_context.exception))

    @patch("hummingbot.connector.exchange.lbank.lbank_utils.RSA")
    def test_post_validation_does_not_fail_with_valid_RSA_key(self, rsa_mock):

        configs = {
            "lbank_auth_method": "RSA",
            "lbank_secret_key": SecretStr(value="secret_key")
        }

        result = LbankConfigMap.post_validations(values=configs)

        self.assertEqual(configs, result)

    @patch("hummingbot.connector.exchange.lbank.lbank_utils.RSA")
    def test_post_validation_fails_with_invalid_RSA_key(self, rsa_mock):
        rsa_mock.importKey.side_effect = ValueError("Test Error")

        configs = {
            "lbank_auth_method": "RSA",
            "lbank_secret_key": SecretStr(value="secret_key")
        }

        with self.assertRaises(ValueError) as exception_context:
            LbankConfigMap.post_validations(values=configs)

        self.assertEqual(
            "Unable to import RSA keys. Error: Test Error",
            str(exception_context.exception)
        )
