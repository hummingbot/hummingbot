# Copyright (c) 2014-2024 by Ron Frederick <ronf@timeheart.net> and others.
#
# This program and the accompanying materials are made available under
# the terms of the Eclipse Public License v2.0 which accompanies this
# distribution and is available at:
#
#     http://www.eclipse.org/legal/epl-2.0/
#
# This program may also be made available under the following secondary
# licenses when the conditions for such availability set forth in the
# Eclipse Public License v2.0 are satisfied:
#
#    GNU General Public License, Version 2.0, or any later versions of
#    that license
#
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later
#
# Contributors:
#     Ron Frederick - initial implementation, API, and documentation

"""A shim around PyCA for accessing symmetric ciphers needed by AsyncSSH"""

from types import ModuleType
from typing import Any, MutableMapping, Optional, Tuple
import warnings

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, CipherContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers.modes import CBC, CTR

import cryptography.hazmat.primitives.ciphers.algorithms as _algs

_decrepit_algs: Optional[ModuleType]

try:
    import cryptography.hazmat.decrepit.ciphers.algorithms as _decrepit_algs
except ImportError: # pragma: no cover
    _decrepit_algs = None


_CipherAlgs = Tuple[Any, Any, int]
_CipherParams = Tuple[int, int, int]


_GCM_MAC_SIZE = 16

_cipher_algs: MutableMapping[str, _CipherAlgs] = {}
_cipher_params: MutableMapping[str, _CipherParams] = {}


class BasicCipher:
    """Shim for basic ciphers"""

    def __init__(self, cipher_name: str, key: bytes, iv: bytes):
        cipher, mode, initial_bytes = _cipher_algs[cipher_name]

        self._cipher = Cipher(cipher(key), mode(iv) if mode else None)
        self._initial_bytes = initial_bytes
        self._encryptor: Optional[CipherContext] = None
        self._decryptor: Optional[CipherContext] = None

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt a block of data"""

        if not self._encryptor:
            self._encryptor = self._cipher.encryptor()

            if self._initial_bytes:
                assert self._encryptor is not None
                self._encryptor.update(self._initial_bytes * b'\0')

        assert self._encryptor is not None
        return self._encryptor.update(data)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt a block of data"""

        if not self._decryptor:
            self._decryptor = self._cipher.decryptor()

            if self._initial_bytes:
                assert self._decryptor is not None
                self._decryptor.update(self._initial_bytes * b'\0')

        assert self._decryptor is not None
        return self._decryptor.update(data)


class GCMCipher:
    """Shim for GCM ciphers"""

    def __init__(self, cipher_name: str, key: bytes, iv: bytes):
        self._cipher = _cipher_algs[cipher_name][0]
        self._key = key
        self._iv = iv

    def _update_iv(self) -> None:
        """Update the IV after each encrypt/decrypt operation"""

        invocation = int.from_bytes(self._iv[4:], 'big')
        invocation = (invocation + 1) & 0xffffffffffffffff
        self._iv = self._iv[:4] + invocation.to_bytes(8, 'big')

    def encrypt_and_sign(self, header: bytes,
                         data: bytes) -> Tuple[bytes, bytes]:
        """Encrypt and sign a block of data"""

        data = AESGCM(self._key).encrypt(self._iv, data, header)

        self._update_iv()

        return header + data[:-_GCM_MAC_SIZE], data[-_GCM_MAC_SIZE:]

    def verify_and_decrypt(self, header: bytes, data: bytes,
                           mac: bytes) -> Optional[bytes]:
        """Verify the signature of and decrypt a block of data"""

        try:
            decrypted_data: Optional[bytes] = \
                AESGCM(self._key).decrypt(self._iv, data + mac, header)
        except InvalidTag:
            decrypted_data = None

        self._update_iv()

        return decrypted_data


def register_cipher(cipher_name: str, key_size: int,
                    iv_size: int, block_size: int) -> None:
    """Register a symmetric cipher"""

    _cipher_params[cipher_name] = (key_size, iv_size, block_size)


def get_cipher_params(cipher_name: str) -> _CipherParams:
    """Get parameters of a symmetric cipher"""

    return _cipher_params[cipher_name]


_cipher_alg_list = (
    ('aes128-cbc',   'AES',       CBC,     0, 16, 16, 16),
    ('aes192-cbc',   'AES',       CBC,     0, 24, 16, 16),
    ('aes256-cbc',   'AES',       CBC,     0, 32, 16, 16),
    ('aes128-ctr',   'AES',       CTR,     0, 16, 16, 16),
    ('aes192-ctr',   'AES',       CTR,     0, 24, 16, 16),
    ('aes256-ctr',   'AES',       CTR,     0, 32, 16, 16),
    ('aes128-gcm',   None,        None,    0, 16, 12, 16),
    ('aes256-gcm',   None,        None,    0, 32, 12, 16),
    ('arcfour',      'ARC4',      None,    0, 16,  1,  1),
    ('arcfour40',    'ARC4',      None,    0,  5,  1,  1),
    ('arcfour128',   'ARC4',      None, 1536, 16,  1,  1),
    ('arcfour256',   'ARC4',      None, 1536, 32,  1,  1),
    ('blowfish-cbc', 'Blowfish',  CBC,     0, 16,  8,  8),
    ('cast128-cbc',  'CAST5',     CBC,     0, 16,  8,  8),
    ('des-cbc',      'TripleDES', CBC,     0,  8,  8,  8),
    ('des2-cbc',     'TripleDES', CBC,     0, 16,  8,  8),
    ('des3-cbc',     'TripleDES', CBC,     0, 24,  8,  8),
    ('seed-cbc',     'SEED',      CBC,     0, 16, 16, 16)
)

with warnings.catch_warnings():
    warnings.simplefilter('ignore')

    for _cipher_name, _alg, _mode, _initial_bytes, \
            _key_size, _iv_size, _block_size in _cipher_alg_list:
        if _alg:
            try:
                _cipher = getattr(_algs, _alg)
            except AttributeError as exc: # pragma: no cover
                if _decrepit_algs:
                    try:
                        _cipher = getattr(_decrepit_algs, _alg)
                    except AttributeError:
                        raise exc from None
                else:
                    raise
        else:
            _cipher = None

        _cipher_algs[_cipher_name] = (_cipher, _mode, _initial_bytes)
        register_cipher(_cipher_name, _key_size, _iv_size, _block_size)
