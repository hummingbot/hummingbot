from hummingbot.client.config.config_crypt import (
    list_encrypted_file_paths,
    decrypt_file,
    secure_config_key,
    encrypted_file_exists,
    encrypt_n_save_config_value,
    encrypted_file_path
)
from hummingbot.core.utils.wallet_setup import (
    list_wallets,
    unlock_wallet
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
import asyncio
from os import unlink


class Security:
    __instance = None
    password = None
    _secure_configs = {}
    wallets = {}
    _decryption_done = asyncio.Event()

    @staticmethod
    def new_password_required():
        encrypted_files = list_encrypted_file_paths()
        wallets = list_wallets()
        return len(encrypted_files) == 0 and len(wallets) == 0

    @staticmethod
    def any_encryped_files():
        encrypted_files = list_encrypted_file_paths()
        return len(encrypted_files) > 0

    @staticmethod
    def encrypted_file_exists(config_key):
        return encrypted_file_exists(config_key)

    @classmethod
    def login(cls, password):
        encrypted_files = list_encrypted_file_paths()
        wallets = list_wallets()
        if encrypted_files:
            try:
                decrypt_file(encrypted_files[0], password)
            except ValueError as err:
                if str(err) == "MAC mismatch":
                    return False
                raise err
        elif wallets:
            try:
                unlock_wallet(wallets[0], password)
            except ValueError as err:
                if str(err) == "MAC mismatch":
                    return False
                raise err
        Security.password = password
        coro = AsyncCallScheduler.shared_instance().call_async(cls.decrypt_all, timeout_seconds=30)
        safe_ensure_future(coro)
        return True

    @classmethod
    def decrypt_file(cls, file_path):
        key_name = secure_config_key(file_path)
        cls._secure_configs[key_name] = decrypt_file(file_path, Security.password)

    @classmethod
    def unlock_wallet(cls, public_key):
        cls.wallets[public_key] = unlock_wallet(public_key=public_key, password=Security.password)

    @classmethod
    def decrypt_all(cls):
        cls._secure_configs.clear()
        cls.wallets.clear()
        cls._decryption_done.clear()
        encrypted_files = list_encrypted_file_paths()
        for file in encrypted_files:
            cls.decrypt_file(file)
        wallets = list_wallets()
        for wallet in wallets:
            cls.unlock_wallet(wallet)
        cls._decryption_done.set()

    @classmethod
    def update_secure_config(cls, key, new_value):
        if new_value is None:
            return
        if encrypted_file_exists(key):
            unlink(encrypted_file_path(key))
        encrypt_n_save_config_value(key, new_value, cls.password)
        cls._secure_configs[key] = new_value

    @classmethod
    def is_decryption_done(cls):
        return cls._decryption_done.is_set()

    @classmethod
    def decrypted_value(cls, key):
        return cls._secure_configs.get(key, None)

    @classmethod
    def all_decrypted_values(cls):
        return cls._secure_configs.copy()

    @classmethod
    async def wait_til_decryption_done(cls):
        await cls._decryption_done.wait()
