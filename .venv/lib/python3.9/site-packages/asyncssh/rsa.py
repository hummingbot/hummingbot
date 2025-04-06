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

"""RSA public key encryption handler"""

from typing import Optional, Tuple, Union, cast

from .asn1 import ASN1DecodeError, ObjectIdentifier, der_encode, der_decode
from .crypto import RSAPrivateKey, RSAPublicKey
from .misc import all_ints
from .packet import MPInt, String, SSHPacket
from .public_key import SSHKey, SSHOpenSSHCertificateV01, KeyExportError
from .public_key import register_public_key_alg, register_certificate_alg
from .public_key import register_x509_certificate_alg


_hash_algs = {b'ssh-rsa':                'sha1',
              b'rsa-sha2-256':           'sha256',
              b'rsa-sha2-512':           'sha512',
              b'ssh-rsa-sha224@ssh.com': 'sha224',
              b'ssh-rsa-sha256@ssh.com': 'sha256',
              b'ssh-rsa-sha384@ssh.com': 'sha384',
              b'ssh-rsa-sha512@ssh.com': 'sha512',
              b'rsa1024-sha1':           'sha1',
              b'rsa2048-sha256':         'sha256'}


_PrivateKeyArgs = Tuple[int, int, int, int, int, int, int, int]
_PrivateKeyConstructArgs = Tuple[int, int, int, int, int, int, int, int, bool]
_PublicKeyArgs = Tuple[int, int]


_default_skip_rsa_key_validation = False


def set_default_skip_rsa_key_validation(skip_validation: bool) -> None:
    """Set whether to disable RSA key validation in OpenSSL

       OpenSSL 3.x does additional validation when loading RSA keys
       as an added security measure. However, the result is that
       loading a key can take significantly longer than it did before.

       If all your RSA keys are coming from a trusted source, you can
       call this function with a value of `True` to default to skipping
       these checks on RSA keys, reducing the cost back down to what it
       was in earlier releases.

       This can also be set on a case by case basis by using the new
       `unsafe_skip_rsa_key_validation` argument on the functions used
       to load keys. This will only affect loading keys of type RSA.

       .. note:: The extra cost only applies to loading existing keys, and
                 not to generating new keys. Also, in cases where a key is
                 used repeatedly, it can be loaded once into an `SSHKey`
                 object and reused without having to pay the cost each time.
                 So, this call should not be needed in most applications.

                 If an application does need this, it is strongly
                 recommended that the `unsafe_skip_rsa_key_validation`
                 argument be used rather than using this function to
                 change the default behavior for all load operations.

    """

    # pylint: disable=global-statement

    global _default_skip_rsa_key_validation

    _default_skip_rsa_key_validation = skip_validation


class RSAKey(SSHKey):
    """Handler for RSA public key encryption"""

    _key: Union[RSAPrivateKey, RSAPublicKey]

    algorithm = b'ssh-rsa'
    default_x509_hash = 'sha256'
    pem_name = b'RSA'
    pkcs8_oid = ObjectIdentifier('1.2.840.113549.1.1.1')
    sig_algorithms = (b'rsa-sha2-256', b'rsa-sha2-512',
                      b'ssh-rsa-sha224@ssh.com', b'ssh-rsa-sha256@ssh.com',
                      b'ssh-rsa-sha384@ssh.com', b'ssh-rsa-sha512@ssh.com',
                      b'ssh-rsa')
    cert_sig_algorithms = (b'rsa-sha2-256', b'rsa-sha2-512', b'ssh-rsa')
    cert_algorithms = tuple(alg + b'-cert-v01@openssh.com'
                            for alg in cert_sig_algorithms)
    x509_sig_algorithms = (b'rsa2048-sha256', b'ssh-rsa')
    x509_algorithms = tuple(b'x509v3-' + alg for alg in x509_sig_algorithms)
    all_sig_algorithms = set(x509_sig_algorithms + sig_algorithms)

    def __eq__(self, other: object) -> bool:
        # This isn't protected access - both objects are RSAKey instances
        # pylint: disable=protected-access

        if not isinstance(other, RSAKey):
            return NotImplemented

        return (self._key.n == other._key.n and
                self._key.e == other._key.e and
                self._key.d == other._key.d)

    def __hash__(self) -> int:
        return hash((self._key.n, self._key.e, self._key.d,
                     self._key.p, self._key.q))

    @classmethod
    def generate(cls, algorithm: bytes, *, # type: ignore
                 key_size: int = 2048, exponent: int = 65537) -> 'RSAKey':
        """Generate a new RSA private key"""

        # pylint: disable=arguments-differ,unused-argument

        return cls(RSAPrivateKey.generate(key_size, exponent))

    @classmethod
    def make_private(cls, key_params: object) -> SSHKey:
        """Construct an RSA private key"""

        n, e, d, p, q, dmp1, dmq1, iqmp, unsafe_skip_rsa_key_validation = \
            cast(_PrivateKeyConstructArgs, key_params)

        if unsafe_skip_rsa_key_validation is None:
            unsafe_skip_rsa_key_validation = _default_skip_rsa_key_validation

        return cls(RSAPrivateKey.construct(n, e, d, p, q, dmp1, dmq1, iqmp,
                                           unsafe_skip_rsa_key_validation))

    @classmethod
    def make_public(cls, key_params: object) -> SSHKey:
        """Construct an RSA public key"""

        n, e = cast(_PublicKeyArgs, key_params)

        return cls(RSAPublicKey.construct(n, e))

    @classmethod
    def decode_pkcs1_private(cls, key_data: object) -> \
            Optional[_PrivateKeyArgs]:
        """Decode a PKCS#1 format RSA private key"""

        if (isinstance(key_data, tuple) and all_ints(key_data) and
                len(key_data) >= 9):
            return cast(_PrivateKeyArgs, key_data[1:9])
        else:
            return None

    @classmethod
    def decode_pkcs1_public(cls, key_data: object) -> \
            Optional[_PublicKeyArgs]:
        """Decode a PKCS#1 format RSA public key"""

        if (isinstance(key_data, tuple) and all_ints(key_data) and
                len(key_data) == 2):
            return cast(_PublicKeyArgs, key_data)
        else:
            return None

    @classmethod
    def decode_pkcs8_private(cls, alg_params: object,
                             data: bytes) -> Optional[_PrivateKeyArgs]:
        """Decode a PKCS#8 format RSA private key"""

        if alg_params is not None:
            return None

        try:
            key_data = der_decode(data)
        except ASN1DecodeError:
            return None

        return cls.decode_pkcs1_private(key_data)

    @classmethod
    def decode_pkcs8_public(cls, alg_params: object,
                            data: bytes) -> Optional[_PublicKeyArgs]:
        """Decode a PKCS#8 format RSA public key"""

        if alg_params is not None:
            return None

        try:
            key_data = der_decode(data)
        except ASN1DecodeError:
            return None

        return cls.decode_pkcs1_public(key_data)

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> _PrivateKeyArgs:
        """Decode an SSH format RSA private key"""

        n = packet.get_mpint()
        e = packet.get_mpint()
        d = packet.get_mpint()
        iqmp = packet.get_mpint()
        p = packet.get_mpint()
        q = packet.get_mpint()

        return n, e, d, p, q, d % (p-1), d % (q-1), iqmp

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> _PublicKeyArgs:
        """Decode an SSH format RSA public key"""

        e = packet.get_mpint()
        n = packet.get_mpint()

        return n, e

    def encode_pkcs1_private(self) -> object:
        """Encode a PKCS#1 format RSA private key"""

        if not self._key.d:
            raise KeyExportError('Key is not private')

        return (0, self._key.n, self._key.e, self._key.d, self._key.p,
                self._key.q, self._key.dmp1, self._key.dmq1, self._key.iqmp)

    def encode_pkcs1_public(self) -> object:
        """Encode a PKCS#1 format RSA public key"""

        return self._key.n, self._key.e

    def encode_pkcs8_private(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format RSA private key"""

        return None, der_encode(self.encode_pkcs1_private())

    def encode_pkcs8_public(self) -> Tuple[object, object]:
        """Encode a PKCS#8 format RSA public key"""

        return None, der_encode(self.encode_pkcs1_public())

    def encode_ssh_private(self) -> bytes:
        """Encode an SSH format RSA private key"""

        if not self._key.d:
            raise KeyExportError('Key is not private')

        assert self._key.iqmp is not None
        assert self._key.p is not None
        assert self._key.q is not None

        return b''.join((MPInt(self._key.n), MPInt(self._key.e),
                         MPInt(self._key.d), MPInt(self._key.iqmp),
                         MPInt(self._key.p), MPInt(self._key.q)))

    def encode_ssh_public(self) -> bytes:
        """Encode an SSH format RSA public key"""

        return b''.join((MPInt(self._key.e), MPInt(self._key.n)))

    def encode_agent_cert_private(self) -> bytes:
        """Encode RSA certificate private key data for agent"""

        if not self._key.d:
            raise KeyExportError('Key is not private')

        assert self._key.iqmp is not None
        assert self._key.p is not None
        assert self._key.q is not None

        return b''.join((MPInt(self._key.d), MPInt(self._key.iqmp),
                         MPInt(self._key.p), MPInt(self._key.q)))

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Compute an SSH-encoded signature of the specified data"""

        if not self._key.d:
            raise ValueError('Private key needed for signing')

        return String(self._key.sign(data, _hash_algs[sig_algorithm]))

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Verify an SSH-encoded signature of the specified data"""

        sig = packet.get_string()
        packet.check_end()

        return self._key.verify(data, sig, _hash_algs[sig_algorithm])

    def encrypt(self, data: bytes, algorithm: bytes) -> Optional[bytes]:
        """Encrypt a block of data with this key"""

        pub_key = cast(RSAPublicKey, self._key)
        return pub_key.encrypt(data, _hash_algs[algorithm])

    def decrypt(self, data: bytes, algorithm: bytes) -> Optional[bytes]:
        """Decrypt a block of data with this key"""

        priv_key = cast(RSAPrivateKey, self._key)
        return priv_key.decrypt(data, _hash_algs[algorithm])


register_public_key_alg(b'ssh-rsa', RSAKey, True)

for _alg in RSAKey.cert_sig_algorithms:
    register_certificate_alg(1, _alg, _alg + b'-cert-v01@openssh.com',
                             RSAKey, SSHOpenSSHCertificateV01, True)

for _alg in RSAKey.x509_algorithms:
    register_x509_certificate_alg(_alg, True)
