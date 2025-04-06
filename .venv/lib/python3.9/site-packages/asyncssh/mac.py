# Copyright (c) 2013-2021 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH message authentication handlers"""

from hashlib import md5, sha1, sha224, sha256, sha384, sha512
import hmac
from typing import Dict, Callable, List, Tuple

from .packet import UInt32, UInt64

try:
    from .crypto import umac64, umac128
    _umac_available = True
except ImportError: # pragma: no cover
    _umac_available = False


_MACAlgsArgs = Tuple[bytes, int, int, bool, Callable, Tuple, bool]
_MACHandler = Tuple[Callable, int, Tuple]
_MACParams = Tuple[int, int, bool]


_OPENSSH = b'@openssh.com'
_ETM = b'-etm' + _OPENSSH

_mac_algs: List[bytes] = []
_default_mac_algs: List[bytes] = []
_mac_handler: Dict[bytes, _MACHandler] = {}
_mac_params: Dict[bytes, _MACParams] = {}


class MAC:
    """Parent class for SSH message authentication handlers"""

    def __init__(self, key: bytes, hash_size: int):
        self._key = key
        self._hash_size = hash_size

    def sign(self, seq: int, packet: bytes) -> bytes:
        """Compute a signature for a message"""

        raise NotImplementedError

    def verify(self, seq: int, packet: bytes, sig: bytes) -> bool:
        """Verify the signature of a message"""

        raise NotImplementedError


class _NullMAC(MAC):
    """Null message authentication handler"""

    def sign(self, seq: int, packet: bytes) -> bytes:
        """Compute a signature for a message"""

        return b''

    def verify(self, seq: int, packet: bytes, sig: bytes) -> bool:
        """Verify the signature of a message"""

        return sig == b''


class _HMAC(MAC):
    """HMAC-based message authentication handler"""

    def __init__(self, key: bytes, hash_size: int, hash_alg: Callable):
        super().__init__(key, hash_size)
        self._hash_alg = hash_alg

    def sign(self, seq: int, packet: bytes) -> bytes:
        """Compute a signature for a message"""

        data = UInt32(seq) + packet
        sig = hmac.new(self._key, data, self._hash_alg).digest()
        return sig[:self._hash_size]

    def verify(self, seq: int, packet: bytes, sig: bytes) -> bool:
        """Verify the signature of a message"""

        return hmac.compare_digest(self.sign(seq, packet), sig)


class _UMAC(MAC):
    """UMAC-based message authentication handler"""

    def __init__(self, key: bytes, hash_size: int, umac_alg: Callable):
        super().__init__(key, hash_size)
        self._umac_alg = umac_alg

    def sign(self, seq: int, packet: bytes) -> bytes:
        """Compute a signature for a message"""

        return self._umac_alg(self._key, packet, UInt64(seq)).digest()

    def verify(self, seq: int, packet: bytes, sig: bytes) -> bool:
        """Verify the signature of a message"""

        return hmac.compare_digest(self.sign(seq, packet), sig)


def register_mac_alg(mac_alg: bytes, key_size: int, hash_size: int,
                     etm: bool, handler: Callable, args: Tuple,
                     default: bool) -> None:
    """Register a MAC algorithm"""

    if mac_alg:
        _mac_algs.append(mac_alg)

        if default:
            _default_mac_algs.append(mac_alg)

    _mac_handler[mac_alg] = (handler, hash_size, args)
    _mac_params[mac_alg] = (key_size, hash_size, etm)


def get_mac_algs() -> List[bytes]:
    """Return supported MAC algorithms"""

    return _mac_algs


def get_default_mac_algs() -> List[bytes]:
    """Return default MAC algorithms"""

    return _default_mac_algs


def get_mac_params(mac_alg: bytes) -> _MACParams:
    """Get parameters of a MAC algorithm

       This function returns the key and hash sizes of a MAC algorithm and
       whether or not to compute the MAC before or after encryption.

    """

    return _mac_params[mac_alg]


def get_mac(mac_alg: bytes, key: bytes) -> MAC:
    """Return a MAC handler

       This function returns a MAC object initialized with the specified
       key that can be used for data signing and verification.

    """

    handler, hash_size, args = _mac_handler[mac_alg]
    return handler(key, hash_size, *args)


_mac_algs_list: Tuple[_MACAlgsArgs, ...] = (
    (b'',                         0,  0, False, _NullMAC, (),         True),
)

if _umac_available: # pragma: no branch
    _mac_algs_list += (
        (b'umac-64' + _ETM,      16,  8, True,  _UMAC,    (umac64,),  True),
        (b'umac-128' + _ETM,     16, 16, True,  _UMAC,    (umac128,), True))

_mac_algs_list += (
    (b'hmac-sha2-256' + _ETM,    32, 32, True,  _HMAC,    (sha256,),  True),
    (b'hmac-sha2-512' + _ETM,    64, 64, True,  _HMAC,    (sha512,),  True),
    (b'hmac-sha1' + _ETM,        20, 20, True,  _HMAC,    (sha1,),    True),
    (b'hmac-md5' + _ETM,         16, 16, True,  _HMAC,    (md5,),     False),
    (b'hmac-sha2-256-96' + _ETM, 32, 12, True,  _HMAC,    (sha256,),  False),
    (b'hmac-sha2-512-96' + _ETM, 64, 12, True,  _HMAC,    (sha512,),  False),
    (b'hmac-sha1-96' + _ETM,     20, 12, True,  _HMAC,    (sha1,),    False),
    (b'hmac-md5-96' + _ETM,      16, 12, True,  _HMAC,    (md5,),     False))

if _umac_available: # pragma: no branch
    _mac_algs_list += (
        (b'umac-64' + _OPENSSH,  16,  8, False, _UMAC,    (umac64,),  True),
        (b'umac-128' + _OPENSSH, 16, 16, False, _UMAC,    (umac128,), True))

_mac_algs_list += (
    (b'hmac-sha2-256',           32, 32, False, _HMAC,    (sha256,),  True),
    (b'hmac-sha2-512',           64, 64, False, _HMAC,    (sha512,),  True),
    (b'hmac-sha1',               20, 20, False, _HMAC,    (sha1,),    True),
    (b'hmac-sha256-2@ssh.com',   32, 32, False, _HMAC,    (sha256,),  True),
    (b'hmac-sha224@ssh.com',     28, 28, False, _HMAC,    (sha224,),  True),
    (b'hmac-sha256@ssh.com',     16, 32, False, _HMAC,    (sha256,),  True),
    (b'hmac-sha384@ssh.com',     48, 48, False, _HMAC,    (sha384,),  True),
    (b'hmac-sha512@ssh.com',     64, 64, False, _HMAC,    (sha512,),  True),
    (b'hmac-md5',                16, 16, False, _HMAC,    (md5,),     False),
    (b'hmac-sha2-256-96',        32, 12, False, _HMAC,    (sha256,),  False),
    (b'hmac-sha2-512-96',        64, 12, False, _HMAC,    (sha512,),  False),
    (b'hmac-sha1-96',            20, 12, False, _HMAC,    (sha1,),    False),
    (b'hmac-md5-96',             16, 12, False, _HMAC,    (md5,),     False))

for _alg, _key_size, _hash_size, _etm, \
        _mac_alg, _args, _default in _mac_algs_list:
    register_mac_alg(_alg, _key_size, _hash_size, _etm,
                     _mac_alg, _args, _default)
