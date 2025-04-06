# Copyright (c) 2019-2021 by Ron Frederick <ronf@timeheart.net> and others.
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

"""EdDSA public key encryption handler"""

from typing import Optional, Tuple, Union, cast

from .asn1 import ASN1DecodeError, ObjectIdentifier, der_encode, der_decode
from .crypto import EdDSAPrivateKey, EdDSAPublicKey
from .crypto import ed25519_available, ed448_available
from .packet import String, SSHPacket
from .public_key import OMIT, SSHKey, SSHOpenSSHCertificateV01
from .public_key import KeyImportError, KeyExportError
from .public_key import register_public_key_alg, register_certificate_alg
from .public_key import register_x509_certificate_alg


_PrivateKeyArgs = Tuple[bytes]
_PublicKeyArgs = Tuple[bytes]


class _EdKey(SSHKey):
    """Handler for EdDSA public key encryption"""

    _key: Union[EdDSAPrivateKey, EdDSAPublicKey]

    algorithm = b''

    def __eq__(self, other: object) -> bool:
        # This isn't protected access - both objects are _EdKey instances
        # pylint: disable=protected-access

        return (isinstance(other, type(self)) and
                self._key.public_value == other._key.public_value and
                self._key.private_value == other._key.private_value)

    def __hash__(self) -> int:
        return hash((self._key.public_value, self._key.private_value))

    @classmethod
    def generate(cls, algorithm: bytes) -> '_EdKey': # type: ignore
        """Generate a new EdDSA private key"""

        # pylint: disable=arguments-differ

        # Strip 'ssh-' prefix of algorithm to get curve_id
        return cls(EdDSAPrivateKey.generate(algorithm[4:]))

    @classmethod
    def make_private(cls, key_params: object) -> SSHKey:
        """Construct an EdDSA private key"""

        try:
            private_value, = cast(_PrivateKeyArgs, key_params)

            return cls(EdDSAPrivateKey.construct(cls.algorithm[4:],
                                                 private_value))
        except (TypeError, ValueError):
            raise KeyImportError('Invalid EdDSA private key') from None

    @classmethod
    def make_public(cls, key_params: object) -> SSHKey:
        """Construct an EdDSA public key"""

        try:
            public_value, = cast(_PublicKeyArgs, key_params)

            return cls(EdDSAPublicKey.construct(cls.algorithm[4:],
                                                public_value))
        except (TypeError, ValueError):
            raise KeyImportError('Invalid EdDSA public key') from None

    @classmethod
    def decode_pkcs8_private(cls, alg_params: object,
                             data: bytes) -> Optional[_PrivateKeyArgs]:
        """Decode a PKCS#8 format EdDSA private key"""

        # pylint: disable=unused-argument

        try:
            return (cast(bytes, der_decode(data)),)
        except ASN1DecodeError:
            return None

    @classmethod
    def decode_pkcs8_public(cls, alg_params: object,
                            data: bytes) -> Optional[_PublicKeyArgs]:
        """Decode a PKCS#8 format EdDSA public key"""

        # pylint: disable=unused-argument

        return (data,)

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> _PrivateKeyArgs:
        """Decode an SSH format EdDSA private key"""

        public_value = packet.get_string()
        private_value = packet.get_string()

        return (private_value[:-len(public_value)],)

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> _PublicKeyArgs:
        """Decode an SSH format EdDSA public key"""

        public_value = packet.get_string()

        return (public_value,)

    def encode_pkcs8_private(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format EdDSA private key"""

        if not self._key.private_value:
            raise KeyExportError('Key is not private')

        return OMIT, der_encode(self._key.private_value)

    def encode_pkcs8_public(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format EdDSA public key"""

        return OMIT, self._key.public_value

    def encode_ssh_private(self) -> bytes:
        """Encode an SSH format EdDSA private key"""

        if self._key.private_value is None:
            raise KeyExportError('Key is not private')

        return b''.join((String(self._key.public_value),
                         String(self._key.private_value +
                                self._key.public_value)))

    def encode_ssh_public(self) -> bytes:
        """Encode an SSH format EdDSA public key"""

        return String(self._key.public_value)

    def encode_agent_cert_private(self) -> bytes:
        """Encode EdDSA certificate private key data for agent"""

        return self.encode_ssh_private()

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Compute an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        if not self._key.private_value:
            raise ValueError('Private key needed for signing')

        return String(self._key.sign(data))

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Verify an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        sig = packet.get_string()
        packet.check_end()

        return self._key.verify(data, sig)


class _Ed25519Key(_EdKey):
    """Handler for Curve25519 public key encryption"""

    algorithm = b'ssh-ed25519'
    pkcs8_oid = ObjectIdentifier('1.3.101.112')
    sig_algorithms = (algorithm,)
    x509_algorithms = (b'x509v3-' + algorithm,)
    all_sig_algorithms = set(sig_algorithms)


class _Ed448Key(_EdKey):
    """Handler for Curve448 public key encryption"""

    algorithm = b'ssh-ed448'
    pkcs8_oid = ObjectIdentifier('1.3.101.113')
    sig_algorithms = (algorithm,)
    x509_algorithms = (b'x509v3-' + algorithm,)
    all_sig_algorithms = set(sig_algorithms)


if ed25519_available: # pragma: no branch
    register_public_key_alg(b'ssh-ed25519', _Ed25519Key, True)

    register_certificate_alg(1, b'ssh-ed25519',
                             b'ssh-ed25519-cert-v01@openssh.com',
                             _Ed25519Key, SSHOpenSSHCertificateV01, True)

    for alg in _Ed25519Key.x509_algorithms:
        register_x509_certificate_alg(alg, True)

if ed448_available: # pragma: no branch
    register_public_key_alg(b'ssh-ed448', _Ed448Key, True)

    register_certificate_alg(1, b'ssh-ed448', b'ssh-ed448-cert-v01@openssh.com',
                             _Ed448Key, SSHOpenSSHCertificateV01, True)

    for alg in _Ed448Key.x509_algorithms:
        register_x509_certificate_alg(alg, True)
