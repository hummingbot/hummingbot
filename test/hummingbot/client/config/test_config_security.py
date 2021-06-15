#!/usr/bin/env python

import unittest
from hummingbot.client.config.security import Security
from hummingbot.client import settings
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_crypt import encrypt_n_save_config_value
import os
import shutil
import asyncio

temp_folder = "conf_testing_temp/"


class ConfigSecurityNewPasswordUnitTest(unittest.TestCase):
    def setUp(self):
        settings.CONF_FILE_PATH = temp_folder
        global_config_map["key_file_path"].value = temp_folder
        os.makedirs(settings.CONF_FILE_PATH, exist_ok=False)

    def tearDown(self):
        shutil.rmtree(temp_folder)

    def test_new_password_process(self):
        # empty folder, new password is required
        self.assertFalse(Security.any_encryped_files())
        self.assertTrue(Security.new_password_required())
        # login will pass with any password
        result = Security.login("a")
        self.assertTrue(result)
        Security.update_secure_config("new_key", "new_value")
        self.assertTrue(os.path.exists(f"{temp_folder}encrypted_new_key.json"))
        self.assertTrue(Security.encrypted_file_exists("new_key"))


class ConfigSecurityExistingPasswordUnitTest(unittest.TestCase):
    def setUp(self):
        settings.CONF_FILE_PATH = temp_folder
        global_config_map["key_file_path"].value = temp_folder
        os.makedirs(settings.CONF_FILE_PATH, exist_ok=False)
        encrypt_n_save_config_value("test_key_1", "test_value_1", "a")
        encrypt_n_save_config_value("test_key_2", "test_value_2", "a")

    def tearDown(self):
        shutil.rmtree(temp_folder)

    async def _test_existing_password(self):
        # check the 2 encrypted files exist
        self.assertTrue(os.path.exists(f"{temp_folder}encrypted_test_key_1.json"))
        self.assertTrue(os.path.exists(f"{temp_folder}encrypted_test_key_2.json"))
        self.assertTrue(Security.any_encryped_files())
        self.assertFalse(Security.new_password_required())
        # login fails with incorrect password
        result = Security.login("b")
        self.assertFalse(result)
        # login passes with correct password
        result = Security.login("a")
        self.assertTrue(result)
        # right after logging in, the decryption shouldn't finished yet
        self.assertFalse(Security.is_decryption_done())
        await Security.wait_til_decryption_done()
        self.assertEqual(len(Security.all_decrypted_values()), 2)
        config_value = Security.decrypted_value("test_key_1")
        self.assertEqual("test_value_1", config_value)
        Security.update_secure_config("test_key_1", "new_value")
        self.assertEqual("new_value", Security.decrypted_value("test_key_1"))

    def test_existing_password(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._test_existing_password())
