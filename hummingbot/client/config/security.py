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
    unlock_wallet,
    import_and_save_wallet
)
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
import asyncio
from os import unlink


class Security:
    __instance = None
    password = None
    _secure_configs = {}
    _private_keys = {}
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
    def any_wallets():
        return len(list_wallets()) > 0

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
        if public_key not in cls._private_keys:
            cls._private_keys[public_key] = unlock_wallet(public_key=public_key, password=Security.password)
        return cls._private_keys[public_key]

    @classmethod
    def decrypt_all(cls):
        cls._secure_configs.clear()
        cls._private_keys.clear()
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
    def add_private_key(cls, private_key) -> str:
        # Add private key and return public key
        account = import_and_save_wallet(cls.password, private_key)
        cls._private_keys[account.address] = account.privateKey
        return account.address

    @classmethod
    def update_config_map(cls, config_map):
        for config in config_map.values():
            if config.is_secure and config.value is None:
                config.value = cls.decrypted_value(config.key)

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
    def private_keys(cls):
        return cls._private_keys.copy()

    @classmethod
    async def wait_til_decryption_done(cls):
        await cls._decryption_done.wait()

    @classmethod
    async def api_keys(cls, exchange):
        await cls.wait_til_decryption_done()
        exchange_configs = [c for c in global_config_map.values()
                            if c.key in AllConnectorSettings.get_connector_settings()[exchange].config_keys
                            and c.key in cls._secure_configs]
        return {c.key: cls.decrypted_value(c.key) for c in exchange_configs}
