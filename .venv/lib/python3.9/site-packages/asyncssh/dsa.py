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

"""DSA public key encryption handler"""

from typing import Optional, Tuple, Union, cast

from .asn1 import ASN1DecodeError, ObjectIdentifier, der_encode, der_decode
from .crypto import DSAPrivateKey, DSAPublicKey
from .misc import all_ints
from .packet import MPInt, String, SSHPacket
from .public_key import SSHKey, SSHOpenSSHCertificateV01, KeyExportError
from .public_key import register_public_key_alg, register_certificate_alg
from .public_key import register_x509_certificate_alg


_PrivateKeyArgs = Tuple[int, int, int, int, int]
_PublicKeyArgs = Tuple[int, int, int, int]


class _DSAKey(SSHKey):
    """Handler for DSA public key encryption"""

    _key: Union[DSAPrivateKey, DSAPublicKey]

    algorithm = b'ssh-dss'
    default_x509_hash = 'sha256'
    pem_name = b'DSA'
    pkcs8_oid = ObjectIdentifier('1.2.840.10040.4.1')
    sig_algorithms = (algorithm,)
    x509_algorithms = (b'x509v3-' + algorithm,)
    all_sig_algorithms = set(sig_algorithms)

    def __eq__(self, other: object) -> bool:
        # This isn't protected access - both objects are _DSAKey instances
        # pylint: disable=protected-access

        return (isinstance(other, type(self)) and
                self._key.p == other._key.p and
                self._key.q == other._key.q and
                self._key.g == other._key.g and
                self._key.y == other._key.y and
                self._key.x == other._key.x)

    def __hash__(self) -> int:
        return hash((self._key.p, self._key.q, self._key.g,
                     self._key.y, self._key.x))

    @classmethod
    def generate(cls, algorithm: bytes) -> '_DSAKey': # type: ignore
        """Generate a new DSA private key"""

        # pylint: disable=arguments-differ,unused-argument

        return cls(DSAPrivateKey.generate(key_size=1024))

    @classmethod
    def make_private(cls, key_params: object) -> SSHKey:
        """Construct a DSA private key"""

        p, q, g, y, x = cast(_PrivateKeyArgs, key_params)

        return cls(DSAPrivateKey.construct(p, q, g, y, x))

    @classmethod
    def make_public(cls, key_params: object) -> SSHKey:
        """Construct a DSA public key"""

        p, q, g, y = cast(_PublicKeyArgs, key_params)

        return cls(DSAPublicKey.construct(p, q, g, y))

    @classmethod
    def decode_pkcs1_private(cls, key_data: object) -> \
            Optional[_PrivateKeyArgs]:
        """Decode a PKCS#1 format DSA private key"""

        if (isinstance(key_data, tuple) and len(key_data) == 6 and
                all_ints(key_data) and key_data[0] == 0):
            return cast(_PrivateKeyArgs, key_data[1:])
        else:
            return None

    @classmethod
    def decode_pkcs1_public(cls, key_data: object) -> \
            Optional[_PublicKeyArgs]:
        """Decode a PKCS#1 format DSA public key"""

        if (isinstance(key_data, tuple) and len(key_data) == 4 and
                all_ints(key_data)):
            y, p, q, g = key_data
            return p, q, g, y
        else:
            return None

    @classmethod
    def decode_pkcs8_private(cls, alg_params: object,
                             data: bytes) -> Optional[_PrivateKeyArgs]:
        """Decode a PKCS#8 format DSA private key"""

        try:
            x = der_decode(data)
        except ASN1DecodeError:
            return None

        if (isinstance(alg_params, tuple) and len(alg_params) == 3 and
                all_ints(alg_params) and isinstance(x, int)):
            p, q, g = alg_params
            y: int = pow(g, x, p)
            return p, q, g, y, x
        else:
            return None

    @classmethod
    def decode_pkcs8_public(cls, alg_params: object,
                            data: bytes) -> Optional[_PublicKeyArgs]:
        """Decode a PKCS#8 format DSA public key"""

        try:
            y = der_decode(data)
        except ASN1DecodeError:
            return None

        if (isinstance(alg_params, tuple) and len(alg_params) == 3 and
                all_ints(alg_params) and isinstance(y, int)):
            p, q, g = alg_params
            return p, q, g, y
        else:
            return None

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> _PrivateKeyArgs:
        """Decode an SSH format DSA private key"""

        p = packet.get_mpint()
        q = packet.get_mpint()
        g = packet.get_mpint()
        y = packet.get_mpint()
        x = packet.get_mpint()

        return p, q, g, y, x

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> _PublicKeyArgs:
        """Decode an SSH format DSA public key"""

        p = packet.get_mpint()
        q = packet.get_mpint()
        g = packet.get_mpint()
        y = packet.get_mpint()

        return p, q, g, y

    def encode_pkcs1_private(self) -> object:
        """Encode a PKCS#1 format DSA private key"""

        if not self._key.x:
            raise KeyExportError('Key is not private')

        return (0, self._key.p, self._key.q, self._key.g,
                self._key.y, self._key.x)

    def encode_pkcs1_public(self) -> object:
        """Encode a PKCS#1 format DSA public key"""

        return (self._key.y, self._key.p, self._key.q, self._key.g)

    def encode_pkcs8_private(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format DSA private key"""

        if not self._key.x:
            raise KeyExportError('Key is not private')

        return (self._key.p, self._key.q, self._key.g), der_encode(self._key.x)

    def encode_pkcs8_public(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format DSA public key"""

        return (self._key.p, self._key.q, self._key.g), der_encode(self._key.y)

    def encode_ssh_private(self) -> bytes:
        """Encode an SSH format DSA private key"""

        if not self._key.x:
            raise KeyExportError('Key is not private')

        return b''.join((MPInt(self._key.p), MPInt(self._key.q),
                         MPInt(self._key.g), MPInt(self._key.y),
                         MPInt(self._key.x)))

    def encode_ssh_public(self) -> bytes:
        """Encode an SSH format DSA public key"""

        return b''.join((MPInt(self._key.p), MPInt(self._key.q),
                         MPInt(self._key.g), MPInt(self._key.y)))

    def encode_agent_cert_private(self) -> bytes:
        """Encode DSA certificate private key data for agent"""

        if not self._key.x:
            raise KeyExportError('Key is not private')

        return MPInt(self._key.x)

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Compute an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        if not self._key.x:
            raise ValueError('Private key needed for signing')

        sig = der_decode(self._key.sign(data, 'sha1'))
        r, s = cast(Tuple[int, int], sig)
        return String(r.to_bytes(20, 'big') + s.to_bytes(20, 'big'))

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Verify an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        sig = packet.get_string()
        packet.check_end()

        if len(sig) != 40:
            return False

        r = int.from_bytes(sig[:20], 'big')
        s = int.from_bytes(sig[20:], 'big')

        return self._key.verify(data, der_encode((r, s)), 'sha1')


register_public_key_alg(b'ssh-dss', _DSAKey, False)

register_certificate_alg(1, b'ssh-dss', b'ssh-dss-cert-v01@openssh.com',
                         _DSAKey, SSHOpenSSHCertificateV01, False)

for alg in _DSAKey.x509_algorithms:
    register_x509_certificate_alg(alg, False)
