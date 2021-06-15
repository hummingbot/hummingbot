"""
Unit tests for hummingbot.core.utils.wallet_setup
"""

from eth_account import Account
from hummingbot.client.settings import DEFAULT_KEY_FILE_PATH, KEYFILE_PREFIX, KEYFILE_POSTFIX
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.wallet_setup import get_key_file_path, list_wallets, import_and_save_wallet, save_wallet
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
        # account isn't our code but it gets tested indirectly in test_import_and_save_wallet
        private_key = "0x8da4ef21b864d2cc526dbdb2a120bd2874c36c9d0a1fb7f8c63d7f7a8b41de8f"
        acct = Account.privateKeyToAccount(private_key)

        # there is no check on the format of the password in save_wallet
        save_wallet(acct, "topsecret")
        file_path = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, acct.address, KEYFILE_POSTFIX)
        self.assertEqual(os.path.exists(file_path), True)

    def test_import_and_save_wallet(self):
        """
        test import_and_save_wallet
        this is almost the same as test_save_wallet, but good to have in case the functions diverge and we want to be
        notified if the behavior changes unexpectedly
        """

        temp_dir = tempfile.gettempdir()
        global_config_map["key_file_path"].value = temp_dir + "/"
        password = "topsecret"

        ill_formed_private_key1 = "not_hex"
        self.assertRaisesRegex(ValueError, "^when sending a str, it must be a hex string", import_and_save_wallet, password, ill_formed_private_key1)

        ill_formed_private_key2 = "0x123123123"  # not the expected length
        self.assertRaisesRegex(ValueError, "^The private key must be exactly 32 bytes long", import_and_save_wallet, password, ill_formed_private_key2)

        # this private key must be in the correct format or it will fail
        private_key = "0x8da4ef21b864d2cc526dbdb2a120bd2874c36c9d0a1fb7f8c63d7f7a8b41de8f"
        password = "topsecret"
        acct = import_and_save_wallet(password, private_key)
        file_path = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, acct.address, KEYFILE_POSTFIX)
        self.assertEqual(os.path.exists(file_path), True)

    def test_list_wallets(self):
        """
        test list_wallets
        """
        # remove any wallets we might have created in other tests
        temp_dir = tempfile.gettempdir()
        for f in os.listdir(temp_dir):
            if f.startswith(KEYFILE_PREFIX) and f.endswith(KEYFILE_POSTFIX):
                os.remove(os.path.join(temp_dir, f))

        # there should be no wallets
        self.assertEqual(list_wallets(), [])

        # make one wallet
        private_key = "0x8da4ef21b864d2cc526dbdb2a120bd2874c36c9d0a1fb7f8c63d7f7a8b41de8f"
        password = "topsecret"
        import_and_save_wallet(password, private_key)

        self.assertEqual(len(list_wallets()), 1)

        # reimporting an existing wallet should not change the count
        import_and_save_wallet(password, private_key)

        self.assertEqual(len(list_wallets()), 1)

        # make a second wallet
        private_key2 = "0xaaaaaf21b864d2cc526dbdb2a120bd2874c36c9d0a1fb7f8c63d7f7a8b41eeee"
        password2 = "topsecrettopsecret"
        import_and_save_wallet(password2, private_key2)

        self.assertEqual(len(list_wallets()), 2)
