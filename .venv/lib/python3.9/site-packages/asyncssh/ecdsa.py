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

"""ECDSA public key encryption handler"""

from typing import Dict, Optional, Tuple, Union, cast

from .asn1 import ASN1DecodeError, BitString, ObjectIdentifier, TaggedDERObject
from .asn1 import der_encode, der_decode
from .crypto import CryptoKey, ECDSAPrivateKey, ECDSAPublicKey
from .crypto import lookup_ec_curve_by_params
from .packet import MPInt, String, SSHPacket
from .public_key import SSHKey, SSHOpenSSHCertificateV01
from .public_key import KeyImportError, KeyExportError
from .public_key import register_public_key_alg, register_certificate_alg
from .public_key import register_x509_certificate_alg


_PrivateKeyArgs = Tuple[bytes, Union[bytes, int], bytes]
_PublicKeyArgs = Tuple[bytes, bytes]


# OID for EC prime fields
PRIME_FIELD = ObjectIdentifier('1.2.840.10045.1.1')

_hash_algs = {b'1.3.132.0.10': 'sha256',
              b'nistp256':     'sha256',
              b'nistp384':     'sha384',
              b'nistp521':     'sha512'}

_alg_oids: Dict[bytes, ObjectIdentifier] = {}
_alg_oid_map: Dict[ObjectIdentifier, bytes] = {}


class _ECKey(SSHKey):
    """Handler for elliptic curve public key encryption"""

    _key: Union[ECDSAPrivateKey, ECDSAPublicKey]

    default_x509_hash = 'sha256'
    pem_name = b'EC'
    pkcs8_oid = ObjectIdentifier('1.2.840.10045.2.1')

    def __init__(self, key: CryptoKey):
        super().__init__(key)

        self.algorithm = b'ecdsa-sha2-' + self._key.curve_id
        self.sig_algorithms = (self.algorithm,)
        self.x509_algorithms = (b'x509v3-' + self.algorithm,)
        self.all_sig_algorithms = set(self.sig_algorithms)

        self._alg_oid = _alg_oids[self._key.curve_id]
        self._hash_alg = _hash_algs[self._key.curve_id]

    def __eq__(self, other: object) -> bool:
        # This isn't protected access - both objects are _ECKey instances
        # pylint: disable=protected-access

        return (isinstance(other, type(self)) and
                self._key.curve_id == other._key.curve_id and
                self._key.x == other._key.x and
                self._key.y == other._key.y and
                self._key.d == other._key.d)

    def __hash__(self) -> int:
        return hash((self._key.curve_id, self._key.x,
                     self._key.y, self._key.d))

    @classmethod
    def _lookup_curve(cls, alg_params: object) -> bytes:
        """Look up an EC curve matching the specified parameters"""

        if isinstance(alg_params, ObjectIdentifier):
            try:
                curve_id = _alg_oid_map[alg_params]
            except KeyError:
                raise KeyImportError('Unknown elliptic curve OID '
                                     f'{alg_params}') from None
        elif (isinstance(alg_params, tuple) and len(alg_params) >= 5 and
              alg_params[0] == 1 and isinstance(alg_params[1], tuple) and
              len(alg_params[1]) == 2 and alg_params[1][0] == PRIME_FIELD and
              isinstance(alg_params[2], tuple) and len(alg_params[2]) >= 2 and
              isinstance(alg_params[3], bytes) and
              isinstance(alg_params[2][0], bytes) and
              isinstance(alg_params[2][1], bytes) and
              isinstance(alg_params[4], int)):
            p = alg_params[1][1]
            a = int.from_bytes(alg_params[2][0], 'big')
            b = int.from_bytes(alg_params[2][1], 'big')
            point = alg_params[3]
            n = alg_params[4]

            try:
                curve_id = lookup_ec_curve_by_params(p, a, b, point, n)
            except ValueError as exc:
                raise KeyImportError(str(exc)) from None
        else:
            raise KeyImportError('Invalid EC curve parameters')

        return curve_id

    @classmethod
    def generate(cls, algorithm: bytes) -> '_ECKey': # type: ignore
        """Generate a new EC private key"""

        # pylint: disable=arguments-differ

        # Strip 'ecdsa-sha2-' prefix of algorithm to get curve_id
        return cls(ECDSAPrivateKey.generate(algorithm[11:]))

    @classmethod
    def make_private(cls, key_params: object) -> SSHKey:
        """Construct an EC private key"""

        curve_id, private_value, public_value = \
            cast(_PrivateKeyArgs, key_params)

        if isinstance(private_value, bytes):
            private_value = int.from_bytes(private_value, 'big')

        return cls(ECDSAPrivateKey.construct(curve_id, public_value,
                                             private_value))

    @classmethod
    def make_public(cls, key_params: object) -> SSHKey:
        """Construct an EC public key"""

        curve_id, public_value = cast(_PublicKeyArgs, key_params)

        return cls(ECDSAPublicKey.construct(curve_id, public_value))

    @classmethod
    def decode_pkcs1_private(cls, key_data: object) -> \
            Optional[_PrivateKeyArgs]:
        """Decode a PKCS#1 format EC private key"""

        if (isinstance(key_data, tuple) and len(key_data) > 2 and
                key_data[0] == 1 and isinstance(key_data[1], bytes) and
                isinstance(key_data[2], TaggedDERObject) and
                key_data[2].tag == 0):
            alg_params = key_data[2].value
            private_key = key_data[1]

            if (len(key_data) > 3 and
                    isinstance(key_data[3], TaggedDERObject) and
                    key_data[3].tag == 1 and
                    isinstance(key_data[3].value, BitString) and
                    key_data[3].value.unused == 0):
                public_key: bytes = key_data[3].value.value
            else:
                public_key = b''

            return cls._lookup_curve(alg_params), private_key, public_key
        else:
            return None

    @classmethod
    def decode_pkcs1_public(cls, key_data: object) -> \
            Optional[_PublicKeyArgs]:
        """Decode a PKCS#1 format EC public key"""

        # pylint: disable=unused-argument

        raise KeyImportError('PKCS#1 not supported for EC public keys')

    @classmethod
    def decode_pkcs8_private(cls, alg_params: object,
                             data: bytes) -> Optional[_PrivateKeyArgs]:
        """Decode a PKCS#8 format EC private key"""

        try:
            key_data = der_decode(data)
        except ASN1DecodeError:
            key_data = None

        if (isinstance(key_data, tuple) and len(key_data) > 1 and
                key_data[0] == 1 and isinstance(key_data[1], bytes)):
            private_key = key_data[1]

            if (len(key_data) > 2 and
                    isinstance(key_data[2], TaggedDERObject) and
                    key_data[2].tag == 1 and
                    isinstance(key_data[2].value, BitString) and
                    key_data[2].value.unused == 0):
                public_key = key_data[2].value.value
            else:
                public_key = b''

            return cls._lookup_curve(alg_params), private_key, public_key
        else:
            return None

    @classmethod
    def decode_pkcs8_public(cls, alg_params: object,
                            data: bytes) -> Optional[_PublicKeyArgs]:
        """Decode a PKCS#8 format EC public key"""

        if isinstance(alg_params, ObjectIdentifier):
            return cls._lookup_curve(alg_params), data
        else:
            return None

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> _PrivateKeyArgs:
        """Decode an SSH format EC private key"""

        curve_id = packet.get_string()
        public_key = packet.get_string()
        private_key = packet.get_mpint()

        return curve_id, private_key, public_key

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> _PublicKeyArgs:
        """Decode an SSH format EC public key"""

        curve_id = packet.get_string()
        public_key = packet.get_string()

        return curve_id, public_key

    def encode_public_tagged(self) -> object:
        """Encode an EC public key blob as a tagged bitstring"""

        return TaggedDERObject(1, BitString(self._key.public_value))

    def encode_pkcs1_private(self) -> object:
        """Encode a PKCS#1 format EC private key"""

        if not self._key.private_value:
            raise KeyExportError('Key is not private')

        return (1, self._key.private_value,
                TaggedDERObject(0, self._alg_oid),
                self.encode_public_tagged())

    def encode_pkcs1_public(self) -> object:
        """Encode a PKCS#1 format EC public key"""

        raise KeyExportError('PKCS#1 is not supported for EC public keys')

    def encode_pkcs8_private(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format EC private key"""

        if not self._key.private_value:
            raise KeyExportError('Key is not private')

        return self._alg_oid, der_encode((1, self._key.private_value,
                                          self.encode_public_tagged()))

    def encode_pkcs8_public(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format EC public key"""

        return self._alg_oid, self._key.public_value

    def encode_ssh_private(self) -> bytes:
        """Encode an SSH format EC private key"""

        if not self._key.d:
            raise KeyExportError('Key is not private')

        return b''.join((String(self._key.curve_id),
                         String(self._key.public_value),
                         MPInt(self._key.d)))

    def encode_ssh_public(self) -> bytes:
        """Encode an SSH format EC public key"""

        return b''.join((String(self._key.curve_id),
                         String(self._key.public_value)))

    def encode_agent_cert_private(self) -> bytes:
        """Encode ECDSA certificate private key data for agent"""

        if not self._key.d:
            raise KeyExportError('Key is not private')

        return MPInt(self._key.d)

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Compute an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        if not self._key.private_value:
            raise ValueError('Private key needed for signing')

        sig = der_decode(self._key.sign(data, self._hash_alg))
        r, s = cast(Tuple[int, int], sig)
        return String(MPInt(r) + MPInt(s))

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Verify an SSH-encoded signature of the specified data"""

        # pylint: disable=unused-argument

        sig = packet.get_string()
        packet.check_end()

        packet = SSHPacket(sig)
        r = packet.get_mpint()
        s = packet.get_mpint()
        packet.check_end()

        return self._key.verify(data, der_encode((r, s)), self._hash_alg)


for _curve_id, _oid_str in ((b'nistp521', '1.3.132.0.35'),
                            (b'nistp384', '1.3.132.0.34'),
                            (b'nistp256', '1.2.840.10045.3.1.7'),
                            (b'1.3.132.0.10', '1.3.132.0.10')):
    _algorithm = b'ecdsa-sha2-' + _curve_id
    _cert_algorithm = _algorithm + b'-cert-v01@openssh.com'
    _x509_algorithm = b'x509v3-' + _algorithm

    _oid = ObjectIdentifier(_oid_str)
    _alg_oids[_curve_id] = _oid
    _alg_oid_map[_oid] = _curve_id

    register_public_key_alg(_algorithm, _ECKey, True, (_algorithm,))
    register_certificate_alg(1, _algorithm, _cert_algorithm,
                             _ECKey, SSHOpenSSHCertificateV01, True)
    register_x509_certificate_alg(_x509_algorithm, True)
