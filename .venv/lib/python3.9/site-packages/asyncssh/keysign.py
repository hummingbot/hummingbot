# Copyright (c) 2018-2021 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH keysign client"""

import asyncio
from pathlib import Path
import subprocess
from typing import Iterable, Sequence, Union, cast

from .misc import FilePath
from .packet import Byte, String, UInt32, PacketDecodeError, SSHPacket
from .public_key import SSHKey, SSHKeyPair, SSHCertificate


_KeySignKey = Union[SSHKey, SSHCertificate]
KeySignPath = Union[None, bool, FilePath]


KEYSIGN_VERSION = 2

_DEFAULT_KEYSIGN_DIRS = ('/opt/local/libexec', '/usr/local/libexec',
                         '/usr/libexec', '/usr/libexec/openssh',
                         '/usr/lib/openssh')


class SSHKeySignKeyPair(SSHKeyPair):
    """Surrogate for a key where signing is done via ssh-keysign"""

    def __init__(self, keysign_path: str, sock_fd: int,
                 key_or_cert: _KeySignKey):
        algorithm = key_or_cert.algorithm
        sig_algorithms = key_or_cert.sig_algorithms[:1]
        public_data = key_or_cert.public_data
        comment = key_or_cert.get_comment_bytes()

        super().__init__(algorithm, algorithm, sig_algorithms, sig_algorithms,
                         public_data, comment)

        self._keysign_path = keysign_path
        self._sock_fd = sock_fd

    async def sign_async(self, data: bytes) -> bytes:
        """Use ssh-keysign to sign a block of data with this key"""

        proc = await asyncio.create_subprocess_exec(
            self._keysign_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, pass_fds=[self._sock_fd])

        request = String(Byte(KEYSIGN_VERSION) + UInt32(self._sock_fd) +
                         String(data))
        stdout, stderr = await proc.communicate(request)

        if stderr:
            error = stderr.decode().strip()
            raise ValueError(error)

        try:
            packet = SSHPacket(stdout)
            resp = packet.get_string()
            packet.check_end()

            packet = SSHPacket(resp)
            version = packet.get_byte()
            sig = packet.get_string()
            packet.check_end()

            if version != KEYSIGN_VERSION:
                raise ValueError('unexpected version')

            return sig
        except PacketDecodeError:
            raise ValueError('invalid response') from None


def find_keysign(path: KeySignPath) -> str:
    """Return path to ssh-keysign executable"""

    if path is True:
        for keysign_dir in _DEFAULT_KEYSIGN_DIRS:
            path = Path(keysign_dir, 'ssh-keysign')
            if path.exists():
                break
        else:
            raise ValueError('Keysign not found')
    else:
        if not path or not Path(cast(FilePath, path)).exists():
            raise ValueError('Keysign not found')

    return str(path)


def get_keysign_keys(keysign_path: str, sock_fd: int,
                     keys: Iterable[_KeySignKey]) -> \
        Sequence[SSHKeySignKeyPair]:
    """Return keypair objects which invoke ssh-keysign"""

    return [SSHKeySignKeyPair(keysign_path, sock_fd, key) for key in keys]
