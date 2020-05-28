from eth_account import Account
from hummingbot.core.utils.wallet_setup import get_key_file_path
import json
import os
from eth_keyfile.keyfile import (
    Random,
    get_default_work_factor_for_kdf,
    _pbkdf2_hash,
    DKLEN,
    encode_hex_no_prefix,
    _scrypt_hash,
    SCRYPT_R,
    SCRYPT_P,
    big_endian_to_int,
    encrypt_aes_ctr,
    keccak,
    int_to_big_endian
)
from hummingbot.client.settings import ENCYPTED_CONF_PREFIX, ENCYPTED_CONF_POSTFIX


def list_encrypted_file_paths():
    file_paths = []
    for f in sorted(os.listdir(get_key_file_path())):
        f_path = os.path.join(get_key_file_path(), f)
        if os.path.isfile(f_path) and f.startswith(ENCYPTED_CONF_PREFIX) and f.endswith(ENCYPTED_CONF_POSTFIX):
            file_paths.append(f_path)
    return file_paths


def encrypted_file_path(config_key: str):
    return "%s%s%s%s" % (get_key_file_path(), ENCYPTED_CONF_PREFIX, config_key, ENCYPTED_CONF_POSTFIX)


def secure_config_key(encrypted_file_path: str):
    _, file_name = os.path.split(encrypted_file_path)
    return file_name[file_name.find(ENCYPTED_CONF_PREFIX) + len(ENCYPTED_CONF_PREFIX):
                     file_name.find(ENCYPTED_CONF_POSTFIX)]


def encrypted_file_exists(config_key: str):
    return os.path.exists(encrypted_file_path(config_key))


def encrypt_n_save_config_value(config_key, config_value, password):
    """
    encrypt configuration value and store in a file, file name is derived from config_var key (in conf folder)
    """
    password_bytes = password.encode()
    message = config_value.encode()
    encrypted = _create_v3_keyfile_json(message, password_bytes)
    file_path = encrypted_file_path(config_key)
    with open(file_path, 'w+') as f:
        f.write(json.dumps(encrypted))


def decrypt_config_value(config_key, password):
    if not encrypted_file_exists(config_key):
        return None
    file_path = encrypted_file_path(config_key)
    return decrypt_file(file_path, password)


def decrypt_file(file_path, password):
    with open(file_path, 'r') as f:
        encrypted = f.read()
    secured_value = Account.decrypt(encrypted, password)
    return secured_value.decode()


def _create_v3_keyfile_json(message_to_encrypt, password, kdf="pbkdf2", work_factor=None):
    """
    Encrypt message by a given password.
    Most of this code is copied from eth_key_file.key_file, removed address and is from json result.
    """
    salt = Random.get_random_bytes(16)

    if work_factor is None:
        work_factor = get_default_work_factor_for_kdf(kdf)

    if kdf == 'pbkdf2':
        derived_key = _pbkdf2_hash(
            password,
            hash_name='sha256',
            salt=salt,
            iterations=work_factor,
            dklen=DKLEN,
        )
        kdfparams = {
            'c': work_factor,
            'dklen': DKLEN,
            'prf': 'hmac-sha256',
            'salt': encode_hex_no_prefix(salt),
        }
    elif kdf == 'scrypt':
        derived_key = _scrypt_hash(
            password,
            salt=salt,
            buflen=DKLEN,
            r=SCRYPT_R,
            p=SCRYPT_P,
            n=work_factor,
        )
        kdfparams = {
            'dklen': DKLEN,
            'n': work_factor,
            'r': SCRYPT_R,
            'p': SCRYPT_P,
            'salt': encode_hex_no_prefix(salt),
        }
    else:
        raise NotImplementedError("KDF not implemented: {0}".format(kdf))

    iv = big_endian_to_int(Random.get_random_bytes(16))
    encrypt_key = derived_key[:16]
    ciphertext = encrypt_aes_ctr(message_to_encrypt, encrypt_key, iv)
    mac = keccak(derived_key[16:32] + ciphertext)

    return {
        'crypto': {
            'cipher': 'aes-128-ctr',
            'cipherparams': {
                'iv': encode_hex_no_prefix(int_to_big_endian(iv)),
            },
            'ciphertext': encode_hex_no_prefix(ciphertext),
            'kdf': kdf,
            'kdfparams': kdfparams,
            'mac': encode_hex_no_prefix(mac),
        },
        'version': 3,
    }
