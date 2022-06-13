import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Awaitable

from hummingbot.client.config import config_crypt, config_helpers, security
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger, store_password_verification, validate_password
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    api_keys_from_connector_config_map,
    get_connector_config_yml_path,
    save_to_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.connector.exchange.binance.binance_utils import BinanceConfigMap


class SecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.new_conf_dir_path = TemporaryDirectory()
        self.default_pswrd_verification_path = security.PASSWORD_VERIFICATION_PATH
        self.default_connectors_conf_dir_path = config_helpers.CONNECTORS_CONF_DIR_PATH
        mock_conf_dir = Path(self.new_conf_dir_path.name) / "conf"
        mock_conf_dir.mkdir(parents=True, exist_ok=True)
        config_crypt.PASSWORD_VERIFICATION_PATH = mock_conf_dir / ".password_verification"

        security.PASSWORD_VERIFICATION_PATH = config_crypt.PASSWORD_VERIFICATION_PATH
        config_helpers.CONNECTORS_CONF_DIR_PATH = (
            Path(self.new_conf_dir_path.name) / "connectors"
        )
        config_helpers.CONNECTORS_CONF_DIR_PATH.mkdir(parents=True, exist_ok=True)
        self.connector = "binance"
        self.api_key = "someApiKey"
        self.api_secret = "someSecret"

    def tearDown(self) -> None:
        config_crypt.PASSWORD_VERIFICATION_PATH = self.default_pswrd_verification_path
        security.PASSWORD_VERIFICATION_PATH = config_crypt.PASSWORD_VERIFICATION_PATH
        config_helpers.CONNECTORS_CONF_DIR_PATH = self.default_connectors_conf_dir_path
        self.new_conf_dir_path.cleanup()
        self.reset_security()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def store_binance_config(self) -> ClientConfigAdapter:
        config_map = ClientConfigAdapter(
            BinanceConfigMap(binance_api_key=self.api_key, binance_api_secret=self.api_secret)
        )
        file_path = get_connector_config_yml_path(self.connector)
        save_to_yml(file_path, config_map)
        return config_map

    @staticmethod
    def reset_security():
        Security.__instance = None
        Security.secrets_manager = None
        Security._secure_configs = {}
        Security._decryption_done = asyncio.Event()

    def test_password_process(self):
        self.assertTrue(Security.new_password_required())

        password = "som-password"
        secrets_manager = ETHKeyFileSecretManger(password)
        store_password_verification(secrets_manager)

        self.assertFalse(Security.new_password_required())
        self.assertTrue(validate_password(secrets_manager))

        another_secrets_manager = ETHKeyFileSecretManger("another-password")

        self.assertFalse(validate_password(another_secrets_manager))

    def test_login(self):
        password = "som-password"
        secrets_manager = ETHKeyFileSecretManger(password)
        store_password_verification(secrets_manager)

        Security.login(secrets_manager)
        config_map = self.store_binance_config()
        self.async_run_with_timeout(Security.wait_til_decryption_done(), timeout=2)

        self.assertTrue(Security.is_decryption_done())
        self.assertTrue(Security.any_secure_configs())
        self.assertTrue(Security.connector_config_file_exists(self.connector))

        api_keys = Security.api_keys(self.connector)
        expected_keys = api_keys_from_connector_config_map(config_map)

        self.assertEqual(expected_keys, api_keys)

    def test_update_secure_config(self):
        password = "som-password"
        secrets_manager = ETHKeyFileSecretManger(password)
        store_password_verification(secrets_manager)
        Security.login(secrets_manager)
        binance_config = ClientConfigAdapter(
            BinanceConfigMap(binance_api_key=self.api_key, binance_api_secret=self.api_secret)
        )
        self.async_run_with_timeout(Security.wait_til_decryption_done())

        Security.update_secure_config(binance_config)
        self.reset_security()

        Security.login(secrets_manager)
        self.async_run_with_timeout(Security.wait_til_decryption_done(), timeout=2)
        binance_loaded_config = Security.decrypted_value(binance_config.connector)

        self.assertEqual(binance_config, binance_loaded_config)

        binance_config.binance_api_key = "someOtherApiKey"
        Security.update_secure_config(binance_config)
        self.reset_security()

        Security.login(secrets_manager)
        self.async_run_with_timeout(Security.wait_til_decryption_done(), timeout=2)
        binance_loaded_config = Security.decrypted_value(binance_config.connector)

        self.assertEqual(binance_config, binance_loaded_config)
