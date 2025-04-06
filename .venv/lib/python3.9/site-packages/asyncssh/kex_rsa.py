# Copyright (c) 2018-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""RSA key exchange handler"""

from hashlib import sha1, sha256
from typing import TYPE_CHECKING, Optional, cast

from .kex import Kex, register_kex_alg
from .misc import HashType, KeyExchangeFailed, ProtocolError
from .misc import get_symbol_names, randrange
from .packet import MPInt, String, SSHPacket
from .public_key import KeyImportError, SSHKey
from .public_key import decode_ssh_public_key, generate_private_key
from .rsa import RSAKey


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .connection import SSHConnection, SSHClientConnection
    from .connection import SSHServerConnection


# SSH KEXRSA message values
MSG_KEXRSA_PUBKEY  = 30
MSG_KEXRSA_SECRET  = 31
MSG_KEXRSA_DONE    = 32


class _KexRSA(Kex):
    """Handler for RSA key exchange"""

    _handler_names = get_symbol_names(globals(), 'MSG_KEXRSA')

    def __init__(self, alg: bytes, conn: 'SSHConnection', hash_alg: HashType,
                 key_size: int, hash_size: int):
        super().__init__(alg, conn, hash_alg)

        self._key_size = key_size
        self._k_limit = 1 << (key_size - 2*hash_size - 49)

        self._host_key_data = b''

        self._trans_key: Optional[SSHKey] = None
        self._trans_key_data = b''

        self._k = 0
        self._encrypted_k = b''

    async def start(self) -> None:
        """Start RSA key exchange"""

        if self._conn.is_server():
            server_conn = cast('SSHServerConnection', self._conn)
            host_key = server_conn.get_server_host_key()
            assert host_key is not None
            self._host_key_data = host_key.public_data

            self._trans_key = generate_private_key(
                'ssh-rsa', key_size=self._key_size)
            self._trans_key_data = self._trans_key.public_data

            self.send_packet(MSG_KEXRSA_PUBKEY, String(self._host_key_data),
                             String(self._trans_key_data))

    def _compute_hash(self) -> bytes:
        """Compute a hash of key information associated with the connection"""

        hash_obj = self._hash_alg()
        hash_obj.update(self._conn.get_hash_prefix())
        hash_obj.update(String(self._host_key_data))
        hash_obj.update(String(self._trans_key_data))
        hash_obj.update(String(self._encrypted_k))
        hash_obj.update(MPInt(self._k))
        return hash_obj.digest()

    def _process_pubkey(self, _pkttype: int, _pktid: int,
                        packet: SSHPacket) -> None:
        """Process a KEXRSA pubkey message"""

        if self._conn.is_server():
            raise ProtocolError('Unexpected KEXRSA pubkey msg')

        self._host_key_data = packet.get_string()
        self._trans_key_data = packet.get_string()
        packet.check_end()

        try:
            pubkey = decode_ssh_public_key(self._trans_key_data)
        except KeyImportError:
            raise ProtocolError('Invalid KEXRSA pubkey msg') from None

        trans_key = cast(RSAKey, pubkey)
        self._k = randrange(self._k_limit)
        self._encrypted_k = \
            cast(bytes, trans_key.encrypt(MPInt(self._k), self.algorithm))

        self.send_packet(MSG_KEXRSA_SECRET, String(self._encrypted_k))

    def _process_secret(self, _pkttype: int, _pktid: int,
                        packet: SSHPacket) -> None:
        """Process a KEXRSA secret message"""

        if self._conn.is_client():
            raise ProtocolError('Unexpected KEXRSA secret msg')

        self._encrypted_k = packet.get_string()
        packet.check_end()

        trans_key = cast(RSAKey, self._trans_key)
        decrypted_k = trans_key.decrypt(self._encrypted_k, self.algorithm)
        if not decrypted_k:
            raise KeyExchangeFailed('Key exchange decryption failed')

        packet = SSHPacket(decrypted_k)
        self._k = packet.get_mpint()
        packet.check_end()

        server_conn = cast('SSHServerConnection', self._conn)
        host_key = server_conn.get_server_host_key()
        assert host_key is not None

        h = self._compute_hash()
        sig = host_key.sign(h)

        self.send_packet(MSG_KEXRSA_DONE, String(sig))

        self._conn.send_newkeys(MPInt(self._k), h)

    def _process_done(self, _pkttype: int, _pktid: int,
                      packet: SSHPacket) -> None:
        """Process a KEXRSA done message"""

        if self._conn.is_server():
            raise ProtocolError('Unexpected KEXRSA done msg')

        sig = packet.get_string()
        packet.check_end()

        client_conn = cast('SSHClientConnection', self._conn)
        host_key = client_conn.validate_server_host_key(self._host_key_data)

        h = self._compute_hash()
        if not host_key.verify(h, sig):
            raise KeyExchangeFailed('Key exchange hash mismatch')

        self._conn.send_newkeys(MPInt(self._k), h)

    _packet_handlers = {
        MSG_KEXRSA_PUBKEY: _process_pubkey,
        MSG_KEXRSA_SECRET: _process_secret,
        MSG_KEXRSA_DONE:   _process_done
    }


for _name, _hash_alg, _key_size, _hash_size, _default in (
        (b'rsa2048-sha256', sha256, 2048, 256, True),
        (b'rsa1024-sha1',   sha1,   1024, 160, False)):
    register_kex_alg(_name, _KexRSA, _hash_alg,
                     (_key_size, _hash_size), _default)
