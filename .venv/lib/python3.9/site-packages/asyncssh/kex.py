# Copyright (c) 2013-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH key exchange handlers"""

import binascii
from hashlib import md5
from typing import TYPE_CHECKING, Dict, List, Sequence, Tuple, Type

from .logging import SSHLogger
from .misc import HashType
from .packet import SSHPacketHandler


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .connection import SSHConnection


_KexAlgList = List[bytes]
_KexAlgMap = Dict[bytes, Tuple[Type['Kex'], HashType, object]]


_kex_algs: _KexAlgList = []
_default_kex_algs:_KexAlgList = []
_kex_handlers: _KexAlgMap = {}

_gss_kex_algs: _KexAlgList = []
_default_gss_kex_algs: _KexAlgList = []
_gss_kex_handlers: _KexAlgMap = {}


class Kex(SSHPacketHandler):
    """Parent class for key exchange handlers"""

    def __init__(self, alg: bytes, conn: 'SSHConnection', hash_alg: HashType):
        self.algorithm = alg

        self._conn = conn
        self._logger = conn.logger
        self._hash_alg = hash_alg


    async def start(self) -> None:
        """Start key exchange"""

        raise NotImplementedError

    def send_packet(self, pkttype: int, *args: bytes) -> None:
        """Send a kex packet"""

        self._conn.send_packet(pkttype, *args, handler=self)

    @property
    def logger(self) -> SSHLogger:
        """A logger associated with this connection"""

        return self._logger

    def compute_key(self, k: bytes, h: bytes, x: bytes,
                    session_id: bytes, keylen: int) -> bytes:
        """Compute keys from output of key exchange"""

        key = b''
        while len(key) < keylen:
            hash_obj = self._hash_alg()
            hash_obj.update(k)
            hash_obj.update(h)
            hash_obj.update(key if key else x + session_id)
            key += hash_obj.digest()

        return key[:keylen]


def register_kex_alg(alg: bytes, handler: Type[Kex], hash_alg: HashType,
                     args: Tuple, default: bool) -> None:
    """Register a key exchange algorithm"""

    _kex_algs.append(alg)

    if default:
        _default_kex_algs.append(alg)

    _kex_handlers[alg] = (handler, hash_alg, args)


def register_gss_kex_alg(alg: bytes, handler: Type[Kex], hash_alg: HashType,
                         args: Tuple, default: bool) -> None:
    """Register a GSSAPI key exchange algorithm"""

    _gss_kex_algs.append(alg)

    if default:
        _default_gss_kex_algs.append(alg)

    _gss_kex_handlers[alg] = (handler, hash_alg, args)


def get_kex_algs() -> List[bytes]:
    """Return supported key exchange algorithms"""

    return _gss_kex_algs + _kex_algs


def get_default_kex_algs() -> List[bytes]:
    """Return default key exchange algorithms"""

    return _default_gss_kex_algs + _default_kex_algs


def expand_kex_algs(kex_algs: Sequence[bytes], mechs: Sequence[bytes],
                    host_key_available: bool) -> List[bytes]:
    """Add mechanisms to GSS entries in key exchange algorithm list"""

    expanded_kex_algs: List[bytes] = []

    for alg in kex_algs:
        if alg.startswith(b'gss-'):
            for mech in mechs:
                suffix = b'-' + binascii.b2a_base64(md5(mech).digest())[:-1]
                expanded_kex_algs.append(alg + suffix)
        elif host_key_available:
            expanded_kex_algs.append(alg)

    return expanded_kex_algs


def get_kex(conn: 'SSHConnection', alg: bytes) -> Kex:
    """Return a key exchange handler

       The function looks up a key exchange algorithm and returns a
       handler which can perform that type of key exchange.

    """

    if alg.startswith(b'gss-'):
        alg = alg.rsplit(b'-', 1)[0]
        handler, hash_alg, args = _gss_kex_handlers[alg]
    else:
        handler, hash_alg, args = _kex_handlers[alg]

    return handler(alg, conn, hash_alg, *args)
