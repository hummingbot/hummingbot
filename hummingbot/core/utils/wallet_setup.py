#!/usr/bin/env python

"""
Functions for storing encrypted wallets and decrypting stored wallets.
"""

from eth_account import Account
from hummingbot.client.settings import (
    KEYFILE_PREFIX,
    KEYFILE_POSTFIX,
    DEFAULT_KEY_FILE_PATH,
)
from hummingbot.client.config.global_config_map import global_config_map
import json
from os import listdir
from os.path import (
    join,
    isfile
)
from typing import Dict, List


def get_key_file_path() -> str:
    """
    The key file path is where encrypted wallet files are stored.
    Get the key file path from the global config map.
    If it is not defined, then return DEFAULT_KEY_FILE_PATH
    """
    path = global_config_map["key_file_path"].value
    return path if path is not None else DEFAULT_KEY_FILE_PATH


def import_and_save_wallet(password: str, private_key: str) -> Account:
    """
    Create an account for a private key, then encryt the private key and store it in the path from get_key_file_path()
    """
    acct: Account = Account.privateKeyToAccount(private_key)
    return save_wallet(acct, password)


def save_wallet(acct: Account, password: str) -> Account:
    """
    For a given account and password, encrypt the account address and store it in the path from get_key_file_path()
    """
    encrypted: Dict = Account.encrypt(acct.privateKey, password)
    file_path: str = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, acct.address, KEYFILE_POSTFIX)
    with open(file_path, 'w+') as f:
        f.write(json.dumps(encrypted))
    return acct


def unlock_wallet(public_key: str, password: str) -> str:
    """
    Search get_key_file_path() by a public key for an account file, then decrypt the private key from the file with the
    provided password
    """
    file_path: str = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, public_key, KEYFILE_POSTFIX)
    with open(file_path, 'r') as f:
        encrypted = f.read()
    private_key: str = Account.decrypt(encrypted, password)
    return private_key


def list_wallets() -> List[str]:
    """
    Return a list of wallets in get_key_file_path()
    """
    wallets = []
    for f in listdir(get_key_file_path()):
        if isfile(join(get_key_file_path(), f)) and f.startswith(KEYFILE_PREFIX) and f.endswith(KEYFILE_POSTFIX):
            wallets.append(f[len(KEYFILE_PREFIX):-len(KEYFILE_POSTFIX)])
    return wallets
