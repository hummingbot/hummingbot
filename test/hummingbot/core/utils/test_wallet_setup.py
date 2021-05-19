"""
Unit tests for hummingbot.core.utils.wallet_setup
"""

from eth_account import Account
from hummingbot.client.settings import DEFAULT_KEY_FILE_PATH, KEYFILE_PREFIX, KEYFILE_POSTFIX
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.wallet_setup import get_key_file_path, save_wallet
import os
import tempfile
import unittest.mock


class WalletSetupTest(unittest.TestCase):
    def test_get_key_file_path(self):
        """
        test get_key_file_path
        """
        global_config_map["key_file_path"].value = "/my_wallets"
        self.assertEqual(get_key_file_path(), global_config_map["key_file_path"].value)

        global_config_map["key_file_path"].value = None
        self.assertEqual(get_key_file_path(), DEFAULT_KEY_FILE_PATH)

    def test_save_wallet(self):
        """
        test save_wallet
        """
        # set the temp_dir as the file that will get returned from get_key_file_path
        temp_dir = tempfile.gettempdir()
        global_config_map["key_file_path"].value = temp_dir + "/"

        # this private key must be in the correct format or it will fail
        private_key = "0x8da4ef21b864d2cc526dbdb2a120bd2874c36c9d0a1fb7f8c63d7f7a8b41de8f"
        acct = Account.privateKeyToAccount(private_key)

        # there is no check on the format of the password in save_wallet
        save_wallet(acct, "topsecret")
        file_path = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, acct.address, KEYFILE_POSTFIX)
        self.assertEqual(os.path.exists(file_path), True)
