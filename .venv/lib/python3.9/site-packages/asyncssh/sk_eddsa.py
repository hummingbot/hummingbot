# Copyright (c) 2019-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""U2F EdDSA public key encryption handler"""

from hashlib import sha256
from typing import Optional, Tuple, cast

from .crypto import EdDSAPublicKey, ed25519_available
from .packet import Byte, String, UInt32, SSHPacket
from .public_key import KeyExportError, SSHKey, SSHOpenSSHCertificateV01
from .public_key import register_public_key_alg, register_certificate_alg
from .public_key import register_sk_alg
from .sk import SSH_SK_ED25519, SSH_SK_USER_PRESENCE_REQD, sk_enroll, sk_sign


_PrivateKeyArgs = Tuple[bytes, str, int, bytes, bytes]
_PublicKeyArgs = Tuple[bytes, str]


class _SKEd25519Key(SSHKey):
    """Handler for U2F Ed25519 public key encryption"""

    _key: EdDSAPublicKey

    algorithm = b'sk-ssh-ed25519@openssh.com'
    sig_algorithms = (algorithm,)
    all_sig_algorithms = set(sig_algorithms)
    use_executor = True

    def __init__(self, public_value: bytes, application: str,
                 flags: int = 0, key_handle: Optional[bytes] = None,
                 reserved: bytes = b''):
        super().__init__(EdDSAPublicKey.construct(b'ed25519', public_value))

        self._application = application
        self._app_hash = sha256(application.encode('utf-8')).digest()
        self._flags = flags
        self._key_handle = key_handle
        self._reserved = reserved

    def __eq__(self, other: object) -> bool:
        # This isn't protected access - both objects are _SKEd25519Key instances
        # pylint: disable=protected-access

        return (isinstance(other, type(self)) and
                self._key.public_value == other._key.public_value and
                self._application == other._application and
                self._flags == other._flags and
                self._key_handle == other._key_handle and
                self._reserved == other._reserved)

    def __hash__(self) -> int:
        return hash((self._key.public_value, self._application, self._flags,
                     self._key_handle, self._reserved))

    @classmethod
    def generate(cls, algorithm: bytes, *, # type: ignore
                 application: str = 'ssh:', user: str = 'AsyncSSH',
                 pin: Optional[str] = None, resident: bool = False,
                 touch_required: bool = True) -> '_SKEd25519Key':
        """Generate a new U2F Ed25519 private key"""

        # pylint: disable=arguments-differ

        flags = SSH_SK_USER_PRESENCE_REQD if touch_required else 0

        public_value, key_handle = sk_enroll(SSH_SK_ED25519, application,
                                             user, pin, resident)

        return cls(public_value, application, flags, key_handle, b'')

    @classmethod
    def make_private(cls, key_params: object) -> SSHKey:
        """Construct a U2F Ed25519 private key"""

        public_value, application, flags, key_handle, reserved = \
            cast(_PrivateKeyArgs, key_params)

        return cls(public_value, application, flags, key_handle, reserved)

    @classmethod
    def make_public(cls, key_params: object) -> SSHKey:
        """Construct a U2F Ed25519 public key"""

        public_value, application = cast(_PublicKeyArgs, key_params)

        return cls(public_value, application)

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> _PrivateKeyArgs:
        """Decode an SSH format U2F Ed25519 private key"""

        public_value = packet.get_string()
        application = packet.get_string().decode('utf-8')
        flags = packet.get_byte()
        key_handle = packet.get_string()
        reserved = packet.get_string()

        return public_value, application, flags, key_handle, reserved

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> _PublicKeyArgs:
        """Decode an SSH format U2F Ed25519 public key"""

        public_value = packet.get_string()
        application = packet.get_string().decode('utf-8')

        return public_value, application

    def encode_ssh_private(self) -> bytes:
        """Encode an SSH format U2F Ed25519 private key"""

        if self._key_handle is None:
            raise KeyExportError('Key is not private')

        return b''.join((String(self._key.public_value),
                         String(self._application), Byte(self._flags),
                         String(self._key_handle), String(self._reserved)))

    def encode_ssh_public(self) -> bytes:
        """Encode an SSH format U2F Ed25519 public key"""

        return b''.join((String(self._key.public_value),
                         String(self._application)))

    def encode_agent_cert_private(self) -> bytes:
        """Encode U2F Ed25519 certificate private key data for agent"""

        return self.encode_ssh_private()

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Compute an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        if self._key_handle is None:
            raise ValueError('Key handle needed for signing')

        flags, counter, sig, _ = sk_sign(data, self._application,
                                         self._key_handle, self._flags)

        return String(sig) + Byte(flags) + UInt32(counter)

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Verify an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        sig = packet.get_string()
        flags = packet.get_byte()
        counter = packet.get_uint32()
        packet.check_end()

        if self._touch_required and not flags & SSH_SK_USER_PRESENCE_REQD:
            return False

        return self._key.verify(self._app_hash + Byte(flags) +
                                UInt32(counter) + sha256(data).digest(), sig)


if ed25519_available: # pragma: no branch
    register_sk_alg(SSH_SK_ED25519, _SKEd25519Key)

    register_public_key_alg(b'sk-ssh-ed25519@openssh.com', _SKEd25519Key, True)

    register_certificate_alg(1, b'sk-ssh-ed25519@openssh.com',
                             b'sk-ssh-ed25519-cert-v01@openssh.com',
                             _SKEd25519Key, SSHOpenSSHCertificateV01, True)
