# Copyright (c) 2013-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""Symmetric key encryption handlers"""

from typing import Dict, List, Optional, Tuple, Type

from .crypto import BasicCipher, GCMCipher, ChachaCipher, get_cipher_params
from .mac import MAC, get_mac_params, get_mac
from .packet import UInt64


_EncParams = Tuple[int, int, int, int, int, bool]
_EncParamsMap = Dict[bytes, Tuple[Type['Encryption'], str]]


_enc_algs: List[bytes] = []
_default_enc_algs: List[bytes] = []
_enc_params: _EncParamsMap = {}


class Encryption:
    """Parent class for SSH packet encryption objects"""

    @classmethod
    def new(cls, cipher_name: str, key: bytes, iv: bytes, mac_alg: bytes = b'',
            mac_key: bytes = b'', etm: bool = False) -> 'Encryption':
        """Construct a new SSH packet encryption object"""

        raise NotImplementedError

    @classmethod
    def get_mac_params(cls, mac_alg: bytes) -> Tuple[int, int, bool]:
        """Get parameters of the MAC algorithm used with this encryption"""

        return get_mac_params(mac_alg)

    def encrypt_packet(self, seq: int, header: bytes,
                       packet: bytes) -> Tuple[bytes, bytes]:
        """Encrypt and sign an SSH packet"""

        raise NotImplementedError

    def decrypt_header(self, seq: int, first_block: bytes,
                       header_len: int) -> Tuple[bytes, bytes]:
        """Decrypt an SSH packet header"""

        raise NotImplementedError

    def decrypt_packet(self, seq: int, first: bytes, rest: bytes,
                       header_len: int, mac: bytes) -> Optional[bytes]:
        """Verify the signature of and decrypt an SSH packet"""

        raise NotImplementedError


class BasicEncryption(Encryption):
    """Shim for basic encryption"""

    def __init__(self, cipher: BasicCipher, mac: MAC):
        self._cipher = cipher
        self._mac = mac

    @classmethod
    def new(cls, cipher_name: str, key: bytes, iv: bytes, mac_alg: bytes = b'',
            mac_key: bytes = b'', etm: bool = False) -> 'BasicEncryption':
        """Construct a new SSH packet encryption object for basic ciphers"""

        cipher = BasicCipher(cipher_name, key, iv)
        mac = get_mac(mac_alg, mac_key)

        if etm:
            return ETMEncryption(cipher, mac)
        else:
            return cls(cipher, mac)

    def encrypt_packet(self, seq: int, header: bytes,
                       packet: bytes) -> Tuple[bytes, bytes]:
        """Encrypt and sign an SSH packet"""

        packet = header + packet
        mac = self._mac.sign(seq, packet) if self._mac else b''

        return self._cipher.encrypt(packet), mac

    def decrypt_header(self, seq: int, first_block: bytes,
                       header_len: int) -> Tuple[bytes, bytes]:
        """Decrypt an SSH packet header"""

        first_block = self._cipher.decrypt(first_block)

        return first_block, first_block[:header_len]

    def decrypt_packet(self, seq: int, first: bytes, rest: bytes,
                       header_len: int, mac: bytes) -> Optional[bytes]:
        """Verify the signature of and decrypt an SSH packet"""

        packet = first + self._cipher.decrypt(rest)

        if self._mac.verify(seq, packet, mac):
            return packet[header_len:]
        else:
            return None


class ETMEncryption(BasicEncryption):
    """Shim for encrypt-then-mac encryption"""

    def encrypt_packet(self, seq: int, header: bytes,
                       packet: bytes) -> Tuple[bytes, bytes]:
        """Encrypt and sign an SSH packet"""

        packet = header + self._cipher.encrypt(packet)
        return packet, self._mac.sign(seq, packet)

    def decrypt_header(self, seq: int, first_block: bytes,
                       header_len: int) -> Tuple[bytes, bytes]:
        """Decrypt an SSH packet header"""

        return first_block, first_block[:header_len]

    def decrypt_packet(self, seq: int, first: bytes, rest: bytes,
                       header_len: int, mac: bytes) -> Optional[bytes]:
        """Verify the signature of and decrypt an SSH packet"""

        packet = first + rest

        if self._mac.verify(seq, packet, mac):
            return self._cipher.decrypt(packet[header_len:])
        else:
            return None


class GCMEncryption(Encryption):
    """Shim for GCM encryption"""

    def __init__(self, cipher: GCMCipher):
        self._cipher = cipher

    @classmethod
    def new(cls, cipher_name: str, key: bytes, iv: bytes, mac_alg: bytes = b'',
            mac_key: bytes = b'', etm: bool = False) -> 'GCMEncryption':
        """Construct a new SSH packet encryption object for GCM ciphers"""

        return cls(GCMCipher(cipher_name, key, iv))

    @classmethod
    def get_mac_params(cls, mac_alg: bytes) -> Tuple[int, int, bool]:
        """Get parameters of the MAC algorithm used with this encryption"""

        return 0, 16, True

    def encrypt_packet(self, seq: int, header: bytes,
                       packet: bytes) -> Tuple[bytes, bytes]:
        """Encrypt and sign an SSH packet"""

        return self._cipher.encrypt_and_sign(header, packet)

    def decrypt_header(self, seq: int, first_block: bytes,
                       header_len: int) -> Tuple[bytes, bytes]:
        """Decrypt an SSH packet header"""

        return first_block, first_block[:header_len]

    def decrypt_packet(self, seq: int, first: bytes, rest: bytes,
                       header_len: int, mac: bytes) -> Optional[bytes]:
        """Verify the signature of and decrypt an SSH packet"""

        return self._cipher.verify_and_decrypt(first[:header_len],
                                               first[header_len:] + rest, mac)


class ChachaEncryption(Encryption):
    """Shim for chacha20-poly1305 encryption"""

    def __init__(self, cipher: ChachaCipher):
        self._cipher = cipher

    @classmethod
    def new(cls, cipher_name: str, key: bytes, iv: bytes, mac_alg: bytes = b'',
            mac_key: bytes = b'', etm: bool = False) -> 'ChachaEncryption':
        """Construct a new SSH packet encryption object for Chacha ciphers"""

        return cls(ChachaCipher(key))

    @classmethod
    def get_mac_params(cls, mac_alg: bytes) -> Tuple[int, int, bool]:
        """Get parameters of the MAC algorithm used with this encryption"""

        return 0, 16, True

    def encrypt_packet(self, seq: int, header: bytes,
                       packet: bytes) -> Tuple[bytes, bytes]:
        """Encrypt and sign an SSH packet"""

        return self._cipher.encrypt_and_sign(header, packet, UInt64(seq))

    def decrypt_header(self, seq: int, first_block: bytes,
                       header_len: int) -> Tuple[bytes, bytes]:
        """Decrypt an SSH packet header"""

        return (first_block,
                self._cipher.decrypt_header(first_block[:header_len],
                                            UInt64(seq)))

    def decrypt_packet(self, seq: int, first: bytes, rest: bytes,
                       header_len: int, mac: bytes) -> Optional[bytes]:
        """Verify the signature of and decrypt an SSH packet"""

        return self._cipher.verify_and_decrypt(first[:header_len],
                                               first[header_len:] + rest,
                                               UInt64(seq), mac)


def register_encryption_alg(enc_alg: bytes, encryption: Type[Encryption],
                            cipher_name: str, default: bool) -> None:
    """Register an encryption algorithm"""

    try:
        get_cipher_params(cipher_name)
    except KeyError:
        pass
    else:
        _enc_algs.append(enc_alg)

        if default:
            _default_enc_algs.append(enc_alg)

        _enc_params[enc_alg] = (encryption, cipher_name)


def get_encryption_algs() -> List[bytes]:
    """Return supported encryption algorithms"""

    return _enc_algs


def get_default_encryption_algs() -> List[bytes]:
    """Return default encryption algorithms"""

    return _default_enc_algs


def get_encryption_params(enc_alg: bytes,
                          mac_alg: bytes = b'') -> _EncParams:
    """Get parameters of an encryption and MAC algorithm"""

    encryption, cipher_name = _enc_params[enc_alg]
    enc_keysize, enc_ivsize, enc_blocksize = get_cipher_params(cipher_name)
    mac_keysize, mac_hashsize, etm = encryption.get_mac_params(mac_alg)

    return (enc_keysize, enc_ivsize, enc_blocksize,
            mac_keysize, mac_hashsize, etm)


def get_encryption(enc_alg: bytes, key: bytes, iv: bytes, mac_alg: bytes = b'',
                   mac_key: bytes = b'', etm: bool = False) -> Encryption:
    """Return an object which can encrypt and decrypt SSH packets"""

    encryption, cipher_name = _enc_params[enc_alg]

    return encryption.new(cipher_name, key, iv, mac_alg, mac_key, etm)


_enc_alg_list = (
    (b'chacha20-poly1305@openssh.com', ChachaEncryption,
     'chacha20-poly1305', True),
    (b'aes256-gcm@openssh.com',        GCMEncryption,
     'aes256-gcm',        True),
    (b'aes128-gcm@openssh.com',        GCMEncryption,
     'aes128-gcm',        True),
    (b'aes256-ctr',                    BasicEncryption,
     'aes256-ctr',        True),
    (b'aes192-ctr',                    BasicEncryption,
     'aes192-ctr',        True),
    (b'aes128-ctr',                    BasicEncryption,
     'aes128-ctr',        True),
    (b'aes256-cbc',                    BasicEncryption,
     'aes256-cbc',        False),
    (b'aes192-cbc',                    BasicEncryption,
     'aes192-cbc',        False),
    (b'aes128-cbc',                    BasicEncryption,
     'aes128-cbc',        False),
    (b'3des-cbc',                      BasicEncryption,
     'des3-cbc',          False),
    (b'blowfish-cbc',                  BasicEncryption,
     'blowfish-cbc',      False),
    (b'cast128-cbc',                   BasicEncryption,
     'cast128-cbc',       False),
    (b'seed-cbc@ssh.com',              BasicEncryption,
     'seed-cbc',          False),
    (b'arcfour256',                    BasicEncryption,
     'arcfour256',        False),
    (b'arcfour128',                    BasicEncryption,
     'arcfour128',        False),
    (b'arcfour',                       BasicEncryption,
     'arcfour',           False)
)

for _enc_alg_args in _enc_alg_list:
    register_encryption_alg(*_enc_alg_args)
