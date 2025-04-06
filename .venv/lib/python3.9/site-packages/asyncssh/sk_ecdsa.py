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

"""U2F ECDSA public key encryption handler"""

from hashlib import sha256
from typing import Optional, Tuple, cast

from .asn1 import der_encode, der_decode
from .crypto import ECDSAPublicKey
from .packet import Byte, MPInt, String, UInt32, SSHPacket
from .public_key import KeyExportError, SSHKey, SSHOpenSSHCertificateV01
from .public_key import register_public_key_alg, register_certificate_alg
from .public_key import register_sk_alg
from .sk import SSH_SK_ECDSA, SSH_SK_USER_PRESENCE_REQD
from .sk import sk_enroll, sk_sign, sk_webauthn_prefix, sk_use_webauthn


_PrivateKeyArgs = Tuple[bytes, bytes, str, int, bytes, bytes]
_PublicKeyArgs = Tuple[bytes, bytes, str]


class _SKECDSAKey(SSHKey):
    """Handler for U2F ECDSA public key encryption"""

    _key: ECDSAPublicKey

    use_executor = True

    def __init__(self, curve_id: bytes, public_value: bytes, application: str,
                 flags: int = 0, key_handle: Optional[bytes] = None,
                 reserved: bytes = b''):
        super().__init__(ECDSAPublicKey.construct(curve_id, public_value))

        self.algorithm = b'sk-ecdsa-sha2-' + curve_id + b'@openssh.com'
        self.sig_algorithms = (self.algorithm, b'webauthn-' + self.algorithm)
        self.all_sig_algorithms = set(self.sig_algorithms)

        self.use_webauthn = sk_use_webauthn

        self._application = application
        self._app_hash = sha256(application.encode('utf-8')).digest()
        self._flags = flags
        self._key_handle = key_handle
        self._reserved = reserved

    def __eq__(self, other: object) -> bool:
        # This isn't protected access - both objects are _SKECDSAKey instances
        # pylint: disable=protected-access

        return (isinstance(other, type(self)) and
                self._key.curve_id == other._key.curve_id and
                self._key.public_value == other._key.public_value and
                self._application == other._application and
                self._flags == other._flags and
                self._key_handle == other._key_handle and
                self._reserved == other._reserved)

    def __hash__(self) -> int:
        return hash((self._key.curve_id, self._key.public_value,
                     self._application, self._flags, self._key_handle,
                     self._reserved))

    @classmethod
    def generate(cls, algorithm: bytes, *, # type: ignore
                 application: str = 'ssh:', user: str = 'AsyncSSH',
                 pin: Optional[str] = None, resident: bool = False,
                 touch_required: bool = True) -> '_SKECDSAKey':
        """Generate a new SK ECDSA private key"""

        # pylint: disable=arguments-differ

        flags = SSH_SK_USER_PRESENCE_REQD if touch_required else 0

        public_value, key_handle = sk_enroll(SSH_SK_ECDSA, application,
                                             user, pin, resident)

        # Strip prefix and suffix of algorithm to get curve_id
        return cls(algorithm[14:-12], public_value, application,
                   flags, key_handle, b'')

    @classmethod
    def make_private(cls, key_params: object) -> SSHKey:
        """Construct a U2F ECDSA private key"""

        curve_id, public_value, application, flags, key_handle, reserved = \
            cast(_PrivateKeyArgs, key_params)

        return cls(curve_id, public_value, application,
                   flags, key_handle, reserved)

    @classmethod
    def make_public(cls, key_params: object) -> SSHKey:
        """Construct a U2F ECDSA public key"""

        curve_id, public_value, application = cast(_PublicKeyArgs, key_params)

        return cls(curve_id, public_value, application)

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> _PrivateKeyArgs:
        """Decode an SSH format SK ECDSA private key"""

        curve_id = packet.get_string()
        public_value = packet.get_string()
        application = packet.get_string().decode('utf-8')
        flags = packet.get_byte()
        key_handle = packet.get_string()
        reserved = packet.get_string()

        return curve_id, public_value, application, flags, key_handle, reserved

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> _PublicKeyArgs:
        """Decode an SSH format SK ECDSA public key"""

        curve_id = packet.get_string()
        public_value = packet.get_string()
        application = packet.get_string().decode('utf-8')

        return curve_id, public_value, application

    def encode_ssh_private(self) -> bytes:
        """Encode an SSH format SK ECDSA private key"""

        if self._key_handle is None:
            raise KeyExportError('Key is not private')

        return b''.join((String(self._key.curve_id),
                         String(self._key.public_value),
                         String(self._application), Byte(self._flags),
                         String(self._key_handle), String(self._reserved)))

    def encode_ssh_public(self) -> bytes:
        """Encode an SSH format SK ECDSA public key"""

        return b''.join((String(self._key.curve_id),
                         String(self._key.public_value),
                         String(self._application)))

    def encode_agent_cert_private(self) -> bytes:
        """Encode U2F ECDSA certificate private key data for agent"""

        if self._key_handle is None:
            raise KeyExportError('Key is not private')

        return b''.join((String(self._application), Byte(self._flags),
                         String(self._key_handle), String(self._reserved)))

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Compute an SSH-encoded signature of the specified data"""

        if self._key_handle is None:
            raise ValueError('Key handle needed for signing')

        is_webauthn = sig_algorithm.startswith(b'webauthn')

        flags, counter, sig, client_data = sk_sign(data, self._application,
                                                   self._key_handle,
                                                   self._flags, is_webauthn)

        r, s = cast(Tuple[int, int], der_decode(sig))

        sig = String(MPInt(r) + MPInt(s)) + Byte(flags) + UInt32(counter)

        if is_webauthn:
            sig += String(self._application) + String(client_data) + String('')

        return sig

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Verify an SSH-encoded signature of the specified data"""

        is_webauthn = sig_algorithm.startswith(b'webauthn')

        sig = packet.get_string()
        flags = packet.get_byte()
        counter = packet.get_uint32()

        if is_webauthn:
            _ = packet.get_string()            # origin
            client_data = packet.get_string()
            _ = packet.get_string()            # extensions

            prefix = sk_webauthn_prefix(data, self._application)

            if not client_data.startswith(prefix):
                return False

            data = client_data

        packet.check_end()

        if self._touch_required and not flags & SSH_SK_USER_PRESENCE_REQD:
            return False

        packet = SSHPacket(sig)
        r = packet.get_mpint()
        s = packet.get_mpint()
        packet.check_end()

        sig = der_encode((r, s))

        return self._key.verify(self._app_hash + Byte(flags) +
                                UInt32(counter) + sha256(data).digest(),
                                sig, 'sha256')


_algorithm = b'sk-ecdsa-sha2-nistp256@openssh.com'
_cert_algorithm = b'sk-ecdsa-sha2-nistp256-cert-v01@openssh.com'

register_sk_alg(SSH_SK_ECDSA, _SKECDSAKey, b'nistp256')

register_public_key_alg(_algorithm, _SKECDSAKey, True,
                        (_algorithm, b'webauthn-' + _algorithm))

register_certificate_alg(1, _algorithm, _cert_algorithm,
                         _SKECDSAKey, SSHOpenSSHCertificateV01, True)
