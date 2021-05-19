from hummingbot.client.settings import DEFAULT_KEY_FILE_PATH
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.wallet_setup import get_key_file_path
import unittest.mock


class WalletSetupTest(unittest.TestCase):
    def test_get_key_file_path(self):
        global_config_map["key_file_path"].value = "/my_wallets"
        self.assertEqual(get_key_file_path(), global_config_map["key_file_path"].value)

        global_config_map["key_file_path"].value = None
        self.assertEqual(get_key_file_path(), DEFAULT_KEY_FILE_PATH)
