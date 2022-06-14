#!/usr/bin/env python

"""
Functions for storing encrypted wallets and decrypting stored wallets.
"""

import json
from os import listdir
from os.path import isfile, join
from typing import Dict, List

import base58
from eth_account import Account

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import DEFAULT_KEY_FILE_PATH, KEYFILE_POSTFIX, KEYFILE_PREFIX

from .solana.keypair import Keypair


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


def import_and_save_sol_wallet(password: str, secret_key: str) -> Keypair:
    """
    Create an keypair from a 64-byte secret key, then encrypt the private key and store it in the path from get_key_file_path()
    """
    acct: Keypair = Keypair.from_secret_key(base58.b58decode(secret_key))
    return save_sol_wallet(acct, password)


def save_sol_wallet(acct: Keypair, password: str) -> Keypair:
    """
    For a given account and password, encrypt the account address and store it in the path from get_key_file_path()
    """
    encrypted: Dict = Account.encrypt(acct.seed, password)
    file_path: str = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, acct.public_key.to_base58().decode('ascii'), KEYFILE_POSTFIX)
    with open(file_path, 'w+') as f:
        f.write(json.dumps(encrypted))
    return acct


def unlock_wallet(wallet_address: str, password: str) -> str:
    """
    Search get_key_file_path() by a public key for an account file, then decrypt the private key from the file with the
    provided password
    """
    file_path: str = "%s%s%s%s" % (get_key_file_path(), KEYFILE_PREFIX, wallet_address, KEYFILE_POSTFIX)
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
