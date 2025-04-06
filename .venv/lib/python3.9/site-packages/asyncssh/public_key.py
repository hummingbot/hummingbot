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

"""SSH asymmetric encryption handlers"""

import asyncio
import binascii
import inspect
import os
import re
import time

from datetime import datetime
from hashlib import md5, sha1, sha256, sha384, sha512
from pathlib import Path, PurePath
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set
from typing import Tuple, Type, Union, cast
from typing_extensions import Protocol

from .crypto import ed25519_available, ed448_available
from .encryption import Encryption
from .sk import sk_available

try:
    # pylint: disable=unused-import
    from .crypto import X509Certificate
    from .crypto import generate_x509_certificate, import_x509_certificate
    _x509_available = True
except ImportError: # pragma: no cover
    _x509_available = False

try:
    import bcrypt
    _bcrypt_available = hasattr(bcrypt, 'kdf')
except ImportError: # pragma: no cover
    _bcrypt_available = False

from .asn1 import ASN1DecodeError, BitString, ObjectIdentifier
from .asn1 import der_encode, der_decode, der_decode_partial
from .crypto import CryptoKey, PyCAKey
from .encryption import get_encryption_params, get_encryption
from .misc import BytesOrStr, DefTuple, FilePath, IPNetwork
from .misc import ip_network, read_file, write_file, parse_time_interval
from .packet import NameList, String, UInt32, UInt64
from .packet import PacketDecodeError, SSHPacket
from .pbe import KeyEncryptionError, pkcs1_encrypt, pkcs8_encrypt
from .pbe import pkcs1_decrypt, pkcs8_decrypt
from .sk import SSH_SK_USER_PRESENCE_REQD, sk_get_resident


_Comment = Optional[BytesOrStr]
_CertPrincipals = Union[str, Sequence[str]]
_Time = Union[int, float, datetime, str]

_PubKeyAlgMap = Dict[bytes, Type['SSHKey']]
_CertAlgMap = Dict[bytes, Tuple[Optional[Type['SSHKey']],
                                Type['SSHCertificate']]]
_CertSigAlgMap = Dict[bytes, bytes]
_CertVersionMap = Dict[Tuple[bytes, int],
                       Tuple[bytes, Type['SSHOpenSSHCertificate']]]

_PEMMap = Dict[bytes, Type['SSHKey']]
_PKCS8OIDMap = Dict[ObjectIdentifier, Type['SSHKey']]
_SKAlgMap = Dict[int, Tuple[Type['SSHKey'], Tuple[object, ...]]]

_OpenSSHCertOptions = Dict[str, object]
_OpenSSHCertParams = Tuple[object, int, int, bytes, bytes,
                           int, int, bytes, bytes]
_OpenSSHCertEncoders = Sequence[Tuple[str, Callable[[object], bytes]]]
_OpenSSHCertDecoders = Dict[bytes, Callable[[SSHPacket], object]]

X509CertPurposes = Union[None, str, Sequence[str]]

_IdentityArg = Union[bytes, FilePath, 'SSHKey', 'SSHCertificate']
IdentityListArg = Union[_IdentityArg, Sequence[_IdentityArg]]
_KeyArg = Union[bytes, FilePath, 'SSHKey']
KeyListArg = Union[FilePath, Sequence[_KeyArg]]
_CertArg = Union[bytes, FilePath, 'SSHCertificate']
CertListArg = Union[_CertArg, Sequence[_CertArg]]
_KeyPairArg = Union['SSHKeyPair', _KeyArg, Tuple[_KeyArg, _CertArg]]
KeyPairListArg = Union[_KeyPairArg, Sequence[_KeyPairArg]]


# Default file names in .ssh directory to read private keys from
_DEFAULT_KEY_FILES = (
    ('id_ed25519_sk', ed25519_available and sk_available),
    ('id_ecdsa_sk', sk_available),
    ('id_ed448', ed448_available),
    ('id_ed25519', ed25519_available),
    ('id_ecdsa', True),
    ('id_rsa', True),
    ('id_dsa', True)
)

# Default directories and file names to read host keys from
_DEFAULT_HOST_KEY_DIRS = ('/opt/local/etc', '/opt/local/etc/ssh',
                          '/usr/local/etc', '/usr/local/etc/ssh',
                          '/etc', '/etc/ssh')
_DEFAULT_HOST_KEY_FILES = ('ssh_host_ed448_key', 'ssh_host_ed25519_key',
                           'ssh_host_ecdsa_key', 'ssh_host_rsa_key',
                           'ssh_host_dsa_key')

_hashes = {'md5': md5, 'sha1': sha1, 'sha256': sha256,
           'sha384': sha384, 'sha512': sha512}

_public_key_algs: List[bytes] = []
_default_public_key_algs: List[bytes] = []

_certificate_algs: List[bytes] = []
_default_certificate_algs: List[bytes] = []

_x509_certificate_algs: List[bytes] = []
_default_x509_certificate_algs: List[bytes] = []

_public_key_alg_map: _PubKeyAlgMap = {}
_certificate_alg_map: _CertAlgMap = {}
_certificate_sig_alg_map: _CertSigAlgMap = {}
_certificate_version_map: _CertVersionMap = {}
_pem_map: _PEMMap = {}
_pkcs8_oid_map: _PKCS8OIDMap = {}
_sk_alg_map: _SKAlgMap = {}

_abs_date_pattern = re.compile(r'\d{8}')
_abs_time_pattern = re.compile(r'\d{14}')

_subject_pattern = re.compile(r'(?:Distinguished[ -_]?Name|Subject|DN)[=:]?\s?',
                              re.IGNORECASE)

# SSH certificate types
CERT_TYPE_USER = 1
CERT_TYPE_HOST = 2

# Flag to omit second argument in alg_params
OMIT = object()

_OPENSSH_KEY_V1 = b'openssh-key-v1\0'
_OPENSSH_SALT_LEN = 16
_OPENSSH_WRAP_LEN = 70


def _parse_time(t: _Time) -> int:
    """Parse a time value"""

    if isinstance(t, int):
        return t
    elif isinstance(t, float):
        return int(t)
    elif isinstance(t, datetime):
        return int(t.timestamp())
    elif isinstance(t, str):
        if t == 'now':
            return int(time.time())

        match = _abs_date_pattern.fullmatch(t)
        if match:
            return int(datetime.strptime(t, '%Y%m%d').timestamp())

        match = _abs_time_pattern.fullmatch(t)
        if match:
            return int(datetime.strptime(t, '%Y%m%d%H%M%S').timestamp())

        try:
            return int(time.time() + parse_time_interval(t))
        except ValueError:
            pass

    raise ValueError('Unrecognized time value')


def _wrap_base64(data: bytes, wrap: int = 64) -> bytes:
    """Break a Base64 value into multiple lines."""

    data = binascii.b2a_base64(data)[:-1]
    return b'\n'.join(data[i:i+wrap]
                      for i in range(0, len(data), wrap)) + b'\n'


class KeyGenerationError(ValueError):
    """Key generation error

       This exception is raised by :func:`generate_private_key`,
       :meth:`generate_user_certificate() <SSHKey.generate_user_certificate>`
       or :meth:`generate_host_certificate()
       <SSHKey.generate_host_certificate>` when the requested parameters are
       unsupported.

    """


class KeyImportError(ValueError):
    """Key import error

       This exception is raised by key import functions when the
       data provided cannot be imported as a valid key.

    """


class KeyExportError(ValueError):
    """Key export error

       This exception is raised by key export functions when the
       requested format is unknown or encryption is requested for a
       format which doesn't support it.

    """


class SigningKey(Protocol):
    """Protocol for signing a block of data"""

    def sign(self, data: bytes) -> bytes:
        """Sign a block of data with a private key"""


class VerifyingKey(Protocol):
    """Protocol for verifying a signature on a block of data"""

    def verify(self, data: bytes, sig: bytes) -> bool:
        """Verify a signature on a block of data with a public key"""


class SSHKey:
    """Parent class which holds an asymmetric encryption key"""

    algorithm: bytes = b''
    sig_algorithms: Sequence[bytes] = ()
    cert_algorithms: Sequence[bytes] = ()
    x509_algorithms: Sequence[bytes] = ()
    all_sig_algorithms: Set[bytes] = set()
    default_x509_hash: str = ''
    pem_name: bytes = b''
    pkcs8_oid: Optional[ObjectIdentifier] = None
    use_executor: bool = False
    use_webauthn: bool = False

    def __init__(self, key: Optional[CryptoKey] = None):
        self._key = key
        self._comment: Optional[bytes] = None
        self._filename: Optional[bytes] = None
        self._touch_required = False

    @classmethod
    def generate(cls, algorithm: bytes, **kwargs) -> 'SSHKey':
        """Generate a new SSH private key"""

        raise NotImplementedError

    @classmethod
    def make_private(cls, key_params: object) -> 'SSHKey':
        """Construct a private key"""

        raise NotImplementedError

    @classmethod
    def make_public(cls, key_params: object) -> 'SSHKey':
        """Construct a public key"""

        raise NotImplementedError

    @classmethod
    def decode_pkcs1_private(cls, key_data: object) -> object:
        """Decode a PKCS#1 format private key"""

    @classmethod
    def decode_pkcs1_public(cls, key_data: object) -> object:
        """Decode a PKCS#1 format public key"""

    @classmethod
    def decode_pkcs8_private(cls, alg_params: object, data: bytes) -> object:
        """Decode a PKCS#8 format private key"""

    @classmethod
    def decode_pkcs8_public(cls, alg_params: object, data: bytes) -> object:
        """Decode a PKCS#8 format public key"""

    @classmethod
    def decode_ssh_private(cls, packet: SSHPacket) -> object:
        """Decode an SSH format private key"""

    @classmethod
    def decode_ssh_public(cls, packet: SSHPacket) -> object:
        """Decode an SSH format public key"""

    @property
    def private_data(self) -> bytes:
        """Return private key data in OpenSSH binary format"""

        return String(self.algorithm) + self.encode_ssh_private()

    @property
    def public_data(self) -> bytes:
        """Return public key data in OpenSSH binary format"""

        return String(self.algorithm) + self.encode_ssh_public()

    @property
    def pyca_key(self) -> PyCAKey:
        """Return PyCA key for use in X.509 module"""

        assert self._key is not None
        return self._key.pyca_key

    def _generate_certificate(self, key: 'SSHKey', version: int, serial: int,
                              cert_type: int, key_id: str,
                              principals: _CertPrincipals,
                              valid_after: _Time, valid_before: _Time,
                              cert_options: _OpenSSHCertOptions,
                              sig_alg_name: DefTuple[str],
                              comment: DefTuple[_Comment]) -> \
            'SSHOpenSSHCertificate':
        """Generate a new SSH certificate"""

        if isinstance(principals, str):
            principals = [p.strip() for p in principals.split(',')]
        else:
            principals = list(principals)

        valid_after = _parse_time(valid_after)
        valid_before = _parse_time(valid_before)

        if valid_before <= valid_after:
            raise ValueError('Valid before time must be later than '
                             'valid after time')

        if sig_alg_name == ():
            sig_alg = self.sig_algorithms[0]
        else:
            sig_alg = cast(str, sig_alg_name).encode()

        if comment == ():
            comment = key.get_comment_bytes()

        comment: _Comment

        try:
            algorithm, cert_handler = _certificate_version_map[key.algorithm,
                                                               version]
        except KeyError:
            raise KeyGenerationError('Unknown certificate version') from None

        return cert_handler.generate(self, algorithm, key, serial, cert_type,
                                     key_id, principals, valid_after,
                                     valid_before, cert_options,
                                     sig_alg, comment)

    def _generate_x509_certificate(self, key: 'SSHKey', subject: str,
                                   issuer: Optional[str],
                                   serial: Optional[int],
                                   valid_after: _Time, valid_before: _Time,
                                   ca: bool, ca_path_len: Optional[int],
                                   purposes: X509CertPurposes,
                                   user_principals: _CertPrincipals,
                                   host_principals: _CertPrincipals,
                                   hash_name: DefTuple[str],
                                   comment: DefTuple[_Comment]) -> \
            'SSHX509Certificate':
        """Generate a new X.509 certificate"""

        if not _x509_available: # pragma: no cover
            raise KeyGenerationError('X.509 certificate generation '
                                     'requires PyOpenSSL')

        if not self.x509_algorithms:
            raise KeyGenerationError('X.509 certificate generation not '
                                     'supported for ' + self.get_algorithm() +
                                     ' keys')

        valid_after = _parse_time(valid_after)
        valid_before = _parse_time(valid_before)

        if valid_before <= valid_after:
            raise ValueError('Valid before time must be later than '
                             'valid after time')

        if hash_name == ():
            hash_name = key.default_x509_hash

        if comment == ():
            comment = key.get_comment_bytes()

        hash_name: str
        comment: _Comment

        return SSHX509Certificate.generate(self, key, subject, issuer,
                                           serial, valid_after, valid_before,
                                           ca, ca_path_len, purposes,
                                           user_principals, host_principals,
                                           hash_name, comment)

    def get_algorithm(self) -> str:
        """Return the algorithm associated with this key"""

        return self.algorithm.decode('ascii')

    def has_comment(self) -> bool:
        """Return whether a comment is set for this key

           :returns: `bool`

        """

        return bool(self._comment)

    def get_comment_bytes(self) -> Optional[bytes]:
        """Return the comment associated with this key as a byte string

           :returns: `bytes` or `None`

        """

        return self._comment or self._filename

    def get_comment(self, encoding: str = 'utf-8',
                    errors: str = 'strict') -> Optional[str]:
        """Return the comment associated with this key as a Unicode string

           :param encoding:
               The encoding to use to decode the comment as a Unicode
               string, defaulting to UTF-8
           :param errors:
               The error handling scheme to use for Unicode decode errors
           :type encoding: `str`
           :type errors: `str`

           :returns: `str` or `None`

           :raises: :exc:`UnicodeDecodeError` if the comment cannot be
                    decoded using the specified encoding

        """

        comment = self.get_comment_bytes()

        return comment.decode(encoding, errors) if comment else None

    def set_comment(self, comment: _Comment, encoding: str = 'utf-8',
                    errors: str = 'strict') -> None:
        """Set the comment associated with this key

           :param comment:
               The new comment to associate with this key
           :param encoding:
               The Unicode encoding to use to encode the comment,
               defaulting to UTF-8
           :param errors:
               The error handling scheme to use for Unicode encode errors
           :type comment: `str`, `bytes`, or `None`
           :type encoding: `str`
           :type errors: `str`

           :raises: :exc:`UnicodeEncodeError` if the comment cannot be
                    encoded using the specified encoding

        """

        if isinstance(comment, str):
            comment = comment.encode(encoding, errors)

        self._comment = comment or None

    def get_filename(self) -> Optional[bytes]:
        """Return the filename associated with this key

           :returns: `bytes` or `None`

        """

        return self._filename

    def set_filename(self, filename: Union[None, bytes, FilePath]) -> None:
        """Set the filename associated with this key

           :param filename:
               The new filename to associate with this key
           :type filename: `PurePath`, `str`, `bytes`, or `None`

        """

        if isinstance(filename, PurePath):
            filename = str(filename)

        if isinstance(filename, str):
            filename = filename.encode('utf-8')

        self._filename = filename or None

    def get_fingerprint(self, hash_name: str = 'sha256') -> str:
        """Get the fingerprint of this key

           Available hashes include:

               md5, sha1, sha256, sha384, sha512

           :param hash_name: (optional)
               The hash algorithm to use to construct the fingerprint.
           :type hash_name: `str`

           :returns: `str`

           :raises: :exc:`ValueError` if the hash name is invalid

        """

        try:
            hash_alg = _hashes[hash_name]
        except KeyError:
            raise ValueError('Unknown hash algorithm') from None

        h = hash_alg(self.public_data)

        if hash_name == 'md5':
            fp = h.hexdigest()
            fp_text = ':'.join(fp[i:i+2] for i in range(0, len(fp), 2))
        else:
            fpb = h.digest()
            fp_text = binascii.b2a_base64(fpb).decode('ascii')[:-1].strip('=')

        return hash_name.upper() + ':' + fp_text

    def set_touch_required(self, touch_required: bool) -> None:
        """Set whether touch is required when using a security key"""

        self._touch_required = touch_required

    def sign_raw(self, data: bytes, hash_name: str) -> bytes:
        """Return a raw signature of the specified data"""

        assert self._key is not None
        return self._key.sign(data, hash_name)

    def sign_ssh(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Abstract method to compute an SSH-encoded signature"""

        raise NotImplementedError

    def verify_ssh(self, data: bytes, sig_algorithm: bytes,
                   packet: SSHPacket) -> bool:
        """Abstract method to verify an SSH-encoded signature"""

        raise NotImplementedError

    def sign(self, data: bytes, sig_algorithm: bytes) -> bytes:
        """Return an SSH-encoded signature of the specified data"""

        if sig_algorithm.startswith(b'x509v3-'):
            sig_algorithm = sig_algorithm[7:]

        if sig_algorithm not in self.all_sig_algorithms:
            raise ValueError('Unrecognized signature algorithm')

        return b''.join((String(sig_algorithm),
                         self.sign_ssh(data, sig_algorithm)))

    def verify(self, data: bytes, sig: bytes) -> bool:
        """Verify an SSH signature of the specified data using this key"""

        try:
            packet = SSHPacket(sig)
            sig_algorithm = packet.get_string()

            if sig_algorithm not in self.all_sig_algorithms:
                return False

            return self.verify_ssh(data, sig_algorithm, packet)
        except PacketDecodeError:
            return False

    def encode_pkcs1_private(self) -> object:
        """Export parameters associated with a PKCS#1 private key"""

        # pylint: disable=no-self-use
        raise KeyExportError('PKCS#1 private key export not supported')

    def encode_pkcs1_public(self) -> object:
        """Export parameters associated with a PKCS#1 public key"""

        # pylint: disable=no-self-use
        raise KeyExportError('PKCS#1 public key export not supported')

    def encode_pkcs8_private(self) -> Tuple[object, object]:
        """Export parameters associated with a PKCS#8 private key"""

        # pylint: disable=no-self-use
        raise KeyExportError('PKCS#8 private key export not supported')

    def encode_pkcs8_public(self) -> Tuple[object, object]:
        """Export parameters associated with a PKCS#8 public key"""

        # pylint: disable=no-self-use
        raise KeyExportError('PKCS#8 public key export not supported')

    def encode_ssh_private(self) -> bytes:
        """Export parameters associated with an OpenSSH private key"""

        # pylint: disable=no-self-use
        raise KeyExportError('OpenSSH private key export not supported')

    def encode_ssh_public(self) -> bytes:
        """Export parameters associated with an OpenSSH public key"""

        # pylint: disable=no-self-use
        raise KeyExportError('OpenSSH public key export not supported')

    def encode_agent_cert_private(self) -> bytes:
        """Encode certificate private key data for agent"""

        raise NotImplementedError

    def convert_to_public(self) -> 'SSHKey':
        """Return public key corresponding to this key

           This method converts an :class:`SSHKey` object which contains
           a private key into one which contains only the corresponding
           public key. If it is called on something which is already
           a public key, it has no effect.

        """

        result = decode_ssh_public_key(self.public_data)
        result.set_comment(self._comment)
        result.set_filename(self._filename)
        return result

    def generate_user_certificate(
            self, user_key: 'SSHKey', key_id: str, version: int = 1,
            serial: int = 0, principals: _CertPrincipals = (),
            valid_after: _Time = 0, valid_before: _Time = 0xffffffffffffffff,
            force_command: Optional[str] = None,
            source_address: Optional[Sequence[str]] = None,
            permit_x11_forwarding: bool = True,
            permit_agent_forwarding: bool = True,
            permit_port_forwarding: bool = True, permit_pty: bool = True,
            permit_user_rc: bool = True, touch_required: bool = True,
            sig_alg: DefTuple[str] = (),
            comment: DefTuple[_Comment] = ()) -> 'SSHOpenSSHCertificate':
        """Generate a new SSH user certificate

           This method returns an SSH user certificate with the requested
           attributes signed by this private key.

           :param user_key:
               The user's public key.
           :param key_id:
               The key identifier associated with this certificate.
           :param version: (optional)
               The version of certificate to create, defaulting to 1.
           :param serial: (optional)
               The serial number of the certificate, defaulting to 0.
           :param principals: (optional)
               The user names this certificate is valid for. By default,
               it can be used with any user name.
           :param valid_after: (optional)
               The earliest time the certificate is valid for, defaulting to
               no restriction on when the certificate starts being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param valid_before: (optional)
               The latest time the certificate is valid for, defaulting to
               no restriction on when the certificate stops being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param force_command: (optional)
               The command (if any) to force a session to run when this
               certificate is used.
           :param source_address: (optional)
               A list of source addresses and networks for which the
               certificate is valid, defaulting to all addresses.
           :param permit_x11_forwarding: (optional)
               Whether or not to allow this user to use X11 forwarding,
               defaulting to `True`.
           :param permit_agent_forwarding: (optional)
               Whether or not to allow this user to use agent forwarding,
               defaulting to `True`.
           :param permit_port_forwarding: (optional)
               Whether or not to allow this user to use port forwarding,
               defaulting to `True`.
           :param permit_pty: (optional)
               Whether or not to allow this user to allocate a
               pseudo-terminal, defaulting to `True`.
           :param permit_user_rc: (optional)
               Whether or not to run the user rc file when this certificate
               is used, defaulting to `True`.
           :param touch_required: (optional)
               Whether or not to require the user to touch the security key
               when authenticating with it, defaulting to `True`.
           :param sig_alg: (optional)
               The algorithm to use when signing the new certificate.
           :param comment:
               The comment to associate with this certificate. By default,
               the comment will be set to the comment currently set on
               user_key.
           :type user_key: :class:`SSHKey`
           :type key_id: `str`
           :type version: `int`
           :type serial: `int`
           :type principals: `str` or `list` of `str`
           :type force_command: `str` or `None`
           :type source_address: list of ip_address and ip_network values
           :type permit_x11_forwarding: `bool`
           :type permit_agent_forwarding: `bool`
           :type permit_port_forwarding: `bool`
           :type permit_pty: `bool`
           :type permit_user_rc: `bool`
           :type touch_required: `bool`
           :type sig_alg: `str`
           :type comment: `str`, `bytes`, or `None`

           :returns: :class:`SSHCertificate`

           :raises: | :exc:`ValueError` if the validity times are invalid
                    | :exc:`KeyGenerationError` if the requested certificate
                      parameters are unsupported

        """

        cert_options: _OpenSSHCertOptions = {}

        if force_command:
            cert_options['force-command'] = force_command

        if source_address:
            cert_options['source-address'] = [ip_network(addr)
                                              for addr in source_address]

        if permit_x11_forwarding:
            cert_options['permit-X11-forwarding'] = True

        if permit_agent_forwarding:
            cert_options['permit-agent-forwarding'] = True

        if permit_port_forwarding:
            cert_options['permit-port-forwarding'] = True

        if permit_pty:
            cert_options['permit-pty'] = True

        if permit_user_rc:
            cert_options['permit-user-rc'] = True

        if not touch_required:
            cert_options['no-touch-required'] = True

        return self._generate_certificate(user_key, version, serial,
                                          CERT_TYPE_USER, key_id,
                                          principals, valid_after,
                                          valid_before, cert_options,
                                          sig_alg, comment)

    def generate_host_certificate(self, host_key: 'SSHKey', key_id: str,
                                  version: int = 1, serial: int = 0,
                                  principals: _CertPrincipals = (),
                                  valid_after: _Time = 0,
                                  valid_before: _Time = 0xffffffffffffffff,
                                  sig_alg: DefTuple[str] = (),
                                  comment: DefTuple[_Comment] = ()) -> \
            'SSHOpenSSHCertificate':
        """Generate a new SSH host certificate

           This method returns an SSH host certificate with the requested
           attributes signed by this private key.

           :param host_key:
               The host's public key.
           :param key_id:
               The key identifier associated with this certificate.
           :param version: (optional)
               The version of certificate to create, defaulting to 1.
           :param serial: (optional)
               The serial number of the certificate, defaulting to 0.
           :param principals: (optional)
               The host names this certificate is valid for. By default,
               it can be used with any host name.
           :param valid_after: (optional)
               The earliest time the certificate is valid for, defaulting to
               no restriction on when the certificate starts being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param valid_before: (optional)
               The latest time the certificate is valid for, defaulting to
               no restriction on when the certificate stops being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param sig_alg: (optional)
               The algorithm to use when signing the new certificate.
           :param comment:
               The comment to associate with this certificate. By default,
               the comment will be set to the comment currently set on
               host_key.
           :type host_key: :class:`SSHKey`
           :type key_id: `str`
           :type version: `int`
           :type serial: `int`
           :type principals: `str` or `list` of `str`
           :type sig_alg: `str`
           :type comment: `str`, `bytes`, or `None`

           :returns: :class:`SSHCertificate`

           :raises: | :exc:`ValueError` if the validity times are invalid
                    | :exc:`KeyGenerationError` if the requested certificate
                      parameters are unsupported
        """

        if comment == ():
            comment = host_key.get_comment_bytes()

        return self._generate_certificate(host_key, version, serial,
                                          CERT_TYPE_HOST, key_id,
                                          principals, valid_after,
                                          valid_before, {}, sig_alg, comment)

    def generate_x509_user_certificate(
            self, user_key: 'SSHKey', subject: str,
            issuer: Optional[str] = None, serial: Optional[int] = None,
            principals: _CertPrincipals = (), valid_after: _Time = 0,
            valid_before: _Time = 0xffffffffffffffff,
            purposes: X509CertPurposes = 'secureShellClient',
            hash_alg: DefTuple[str] = (),
            comment: DefTuple[_Comment] = ()) -> 'SSHX509Certificate':
        """Generate a new X.509 user certificate

           This method returns an X.509 user certificate with the requested
           attributes signed by this private key.

           :param user_key:
               The user's public key.
           :param subject:
               The subject name in the certificate, expresed as a
               comma-separated list of X.509 `name=value` pairs.
           :param issuer: (optional)
               The issuer name in the certificate, expresed as a
               comma-separated list of X.509 `name=value` pairs. If
               not specified, the subject name will be used, creating
               a self-signed certificate.
           :param serial: (optional)
               The serial number of the certificate, defaulting to a random
               64-bit value.
           :param principals: (optional)
               The user names this certificate is valid for. By default,
               it can be used with any user name.
           :param valid_after: (optional)
               The earliest time the certificate is valid for, defaulting to
               no restriction on when the certificate starts being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param valid_before: (optional)
               The latest time the certificate is valid for, defaulting to
               no restriction on when the certificate stops being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param purposes: (optional)
               The allowed purposes for this certificate or `None` to
               not restrict the certificate's purpose, defaulting to
               'secureShellClient'
           :param hash_alg: (optional)
               The hash algorithm to use when signing the new certificate,
               defaulting to SHA256.
           :param comment: (optional)
               The comment to associate with this certificate. By default,
               the comment will be set to the comment currently set on
               user_key.
           :type user_key: :class:`SSHKey`
           :type subject: `str`
           :type issuer: `str`
           :type serial: `int`
           :type principals: `str` or `list` of `str`
           :type purposes: `str`, `list` of `str`, or `None`
           :type hash_alg: `str`
           :type comment: `str`, `bytes`, or `None`

           :returns: :class:`SSHCertificate`

           :raises: | :exc:`ValueError` if the validity times are invalid
                    | :exc:`KeyGenerationError` if the requested certificate
                      parameters are unsupported

        """

        return self._generate_x509_certificate(user_key, subject, issuer,
                                               serial, valid_after,
                                               valid_before, False, None,
                                               purposes, principals, (),
                                               hash_alg, comment)

    def generate_x509_host_certificate(
            self, host_key: 'SSHKey', subject: str,
            issuer: Optional[str] = None, serial: Optional[int] = None,
            principals: _CertPrincipals = (), valid_after: _Time = 0,
            valid_before: _Time = 0xffffffffffffffff,
            purposes: X509CertPurposes = 'secureShellServer',
            hash_alg: DefTuple[str] = (),
            comment: DefTuple[_Comment] = ()) -> 'SSHX509Certificate':
        """Generate a new X.509 host certificate

           This method returns an X.509 host certificate with the requested
           attributes signed by this private key.

           :param host_key:
               The host's public key.
           :param subject:
               The subject name in the certificate, expresed as a
               comma-separated list of X.509 `name=value` pairs.
           :param issuer: (optional)
               The issuer name in the certificate, expresed as a
               comma-separated list of X.509 `name=value` pairs. If
               not specified, the subject name will be used, creating
               a self-signed certificate.
           :param serial: (optional)
               The serial number of the certificate, defaulting to a random
               64-bit value.
           :param principals: (optional)
               The host names this certificate is valid for. By default,
               it can be used with any host name.
           :param valid_after: (optional)
               The earliest time the certificate is valid for, defaulting to
               no restriction on when the certificate starts being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param valid_before: (optional)
               The latest time the certificate is valid for, defaulting to
               no restriction on when the certificate stops being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param purposes: (optional)
               The allowed purposes for this certificate or `None` to
               not restrict the certificate's purpose, defaulting to
               'secureShellServer'
           :param hash_alg: (optional)
               The hash algorithm to use when signing the new certificate,
               defaulting to SHA256.
           :param comment: (optional)
               The comment to associate with this certificate. By default,
               the comment will be set to the comment currently set on
               host_key.
           :type host_key: :class:`SSHKey`
           :type subject: `str`
           :type issuer: `str`
           :type serial: `int`
           :type principals: `str` or `list` of `str`
           :type purposes: `str`, `list` of `str`, or `None`
           :type hash_alg: `str`
           :type comment: `str`, `bytes`, or `None`

           :returns: :class:`SSHCertificate`

           :raises: | :exc:`ValueError` if the validity times are invalid
                    | :exc:`KeyGenerationError` if the requested certificate
                      parameters are unsupported
        """

        return self._generate_x509_certificate(host_key, subject, issuer,
                                               serial, valid_after,
                                               valid_before, False, None,
                                               purposes, (), principals,
                                               hash_alg, comment)

    def generate_x509_ca_certificate(self, ca_key: 'SSHKey', subject: str,
                                     issuer: Optional[str] = None,
                                     serial: Optional[int] = None,
                                     valid_after: _Time = 0,
                                     valid_before: _Time = 0xffffffffffffffff,
                                     ca_path_len: Optional[int] = None,
                                     hash_alg: DefTuple[str] = (),
                                     comment: DefTuple[_Comment] = ()) -> \
            'SSHX509Certificate':
        """Generate a new X.509 CA certificate

           This method returns an X.509 CA certificate with the requested
           attributes signed by this private key.

           :param ca_key:
               The new CA's public key.
           :param subject:
               The subject name in the certificate, expresed as a
               comma-separated list of X.509 `name=value` pairs.
           :param issuer: (optional)
               The issuer name in the certificate, expresed as a
               comma-separated list of X.509 `name=value` pairs. If
               not specified, the subject name will be used, creating
               a self-signed certificate.
           :param serial: (optional)
               The serial number of the certificate, defaulting to a random
               64-bit value.
           :param valid_after: (optional)
               The earliest time the certificate is valid for, defaulting to
               no restriction on when the certificate starts being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param valid_before: (optional)
               The latest time the certificate is valid for, defaulting to
               no restriction on when the certificate stops being valid.
               See :ref:`SpecifyingTimeValues` for allowed time specifications.
           :param ca_path_len: (optional)
               The maximum number of levels of intermediate CAs allowed
               below this new CA or `None` to not enforce a limit,
               defaulting to no limit.
           :param hash_alg: (optional)
               The hash algorithm to use when signing the new certificate,
               defaulting to SHA256.
           :param comment: (optional)
               The comment to associate with this certificate. By default,
               the comment will be set to the comment currently set on
               ca_key.
           :type ca_key: :class:`SSHKey`
           :type subject: `str`
           :type issuer: `str`
           :type serial: `int`
           :type ca_path_len: `int` or `None`
           :type hash_alg: `str`
           :type comment: `str`, `bytes`, or `None`

           :returns: :class:`SSHCertificate`

           :raises: | :exc:`ValueError` if the validity times are invalid
                    | :exc:`KeyGenerationError` if the requested certificate
                      parameters are unsupported
        """

        return self._generate_x509_certificate(ca_key, subject, issuer,
                                               serial, valid_after,
                                               valid_before, True,
                                               ca_path_len, None, (), (),
                                               hash_alg, comment)

    def export_private_key(self, format_name: str = 'openssh',
                           passphrase: Optional[BytesOrStr] = None,
                           cipher_name: str = 'aes256-cbc',
                           hash_name: str = 'sha256',
                           pbe_version: int = 2, rounds: int = 128,
                           ignore_few_rounds: bool = False) -> bytes:
        """Export a private key in the requested format

           This method returns this object's private key encoded in the
           requested format. If a passphrase is specified, the key will
           be exported in encrypted form.

           Available formats include:

               pkcs1-der, pkcs1-pem, pkcs8-der, pkcs8-pem, openssh

           By default, openssh format will be used.

           Encryption is supported in pkcs1-pem, pkcs8-der, pkcs8-pem,
           and openssh formats. For pkcs1-pem, only the cipher can be
           specified. For pkcs8-der and pkcs-8, cipher,  hash and PBE
           version can be specified. For openssh, cipher and rounds
           can be specified.

           Available ciphers for pkcs1-pem are:

               aes128-cbc, aes192-cbc, aes256-cbc, des-cbc, des3-cbc

           Available ciphers for pkcs8-der and pkcs8-pem are:

               aes128-cbc, aes192-cbc, aes256-cbc, blowfish-cbc,
               cast128-cbc, des-cbc, des2-cbc, des3-cbc, rc4-40, rc4-128

           Available ciphers for openssh format include the following
           :ref:`encryption algorithms <EncryptionAlgs>`.

           Available hashes include:

               md5, sha1, sha256, sha384, sha512

           Available PBE versions include 1 for PBES1 and 2 for PBES2.

           Not all combinations of cipher, hash, and version are supported.

           The default cipher is aes256. In the pkcs8 formats, the default
           hash is sha256 and default version is PBES2.

           In openssh format, the default number of rounds is 128.

           .. note:: The openssh format uses bcrypt for encryption, but
                     unlike the traditional bcrypt cost factor used in
                     password hashing which scales logarithmically, the
                     encryption strength here scales linearly with the
                     rounds value. Since the cipher is rekeyed 64 times
                     per round, the default rounds value of 128 corresponds
                     to 8192 total iterations, which is the equivalent of
                     a bcrypt cost factor of 13.

           :param format_name: (optional)
               The format to export the key in.
           :param passphrase: (optional)
               A passphrase to encrypt the private key with.
           :param cipher_name: (optional)
               The cipher to use for private key encryption.
           :param hash_name: (optional)
               The hash to use for private key encryption.
           :param pbe_version: (optional)
               The PBE version to use for private key encryption.
           :param rounds: (optional)
               The number of KDF rounds to apply to the passphrase.
           :type format_name: `str`
           :type passphrase: `str` or `bytes`
           :type cipher_name: `str`
           :type hash_name: `str`
           :type pbe_version: `int`
           :type rounds: `int`

           :returns: `bytes` representing the exported private key

        """

        if format_name in ('pkcs1-der', 'pkcs1-pem'):
            data = der_encode(self.encode_pkcs1_private())

            if passphrase is not None:
                if format_name == 'pkcs1-der':
                    raise KeyExportError('PKCS#1 DER format does not support '
                                         'private key encryption')

                alg, iv, data = pkcs1_encrypt(data, cipher_name, passphrase)
                headers = (b'Proc-Type: 4,ENCRYPTED\n' +
                           b'DEK-Info: ' + alg + b',' +
                           binascii.b2a_hex(iv).upper() + b'\n\n')
            else:
                headers = b''

            if format_name == 'pkcs1-pem':
                keytype = self.pem_name + b' PRIVATE KEY'
                data = (b'-----BEGIN ' + keytype + b'-----\n' +
                        headers + _wrap_base64(data) +
                        b'-----END ' + keytype + b'-----\n')

            return data
        elif format_name in ('pkcs8-der', 'pkcs8-pem'):
            alg_params, pkcs8_data = self.encode_pkcs8_private()

            if alg_params is OMIT:
                data = der_encode((0, (self.pkcs8_oid,), pkcs8_data))
            else:
                data = der_encode((0, (self.pkcs8_oid, alg_params), pkcs8_data))

            if passphrase is not None:
                data = pkcs8_encrypt(data, cipher_name, hash_name,
                                     pbe_version, passphrase)

            if format_name == 'pkcs8-pem':
                if passphrase is not None:
                    keytype = b'ENCRYPTED PRIVATE KEY'
                else:
                    keytype = b'PRIVATE KEY'

                data = (b'-----BEGIN ' + keytype + b'-----\n' +
                        _wrap_base64(data) +
                        b'-----END ' + keytype + b'-----\n')

            return data
        elif format_name == 'openssh':
            check = os.urandom(4)
            nkeys = 1

            data = b''.join((check, check, self.private_data,
                             String(self._comment or b'')))

            cipher: Optional[Encryption]

            if passphrase is not None:
                try:
                    alg = cipher_name.encode('ascii')
                    key_size, iv_size, block_size, _, _, _ = \
                        get_encryption_params(alg)
                except (KeyError, UnicodeEncodeError):
                    raise KeyEncryptionError('Unknown cipher: ' +
                                             cipher_name) from None

                if not _bcrypt_available: # pragma: no cover
                    raise KeyExportError('OpenSSH private key encryption '
                                         'requires bcrypt with KDF support')

                kdf = b'bcrypt'
                salt = os.urandom(_OPENSSH_SALT_LEN)
                kdf_data = b''.join((String(salt), UInt32(rounds)))

                if isinstance(passphrase, str):
                    passphrase = passphrase.encode('utf-8')

                key = bcrypt.kdf(passphrase, salt, key_size + iv_size,
                                 rounds, ignore_few_rounds)

                cipher = get_encryption(alg, key[:key_size], key[key_size:])
                block_size = max(block_size, 8)
            else:
                cipher = None
                alg = b'none'
                kdf = b'none'
                kdf_data = b''
                block_size = 8
                mac = b''

            pad = len(data) % block_size
            if pad: # pragma: no branch
                data = data + bytes(range(1, block_size + 1 - pad))

            if cipher:
                data, mac = cipher.encrypt_packet(0, b'', data)
            else:
                mac = b''

            data = b''.join((_OPENSSH_KEY_V1, String(alg), String(kdf),
                             String(kdf_data), UInt32(nkeys),
                             String(self.public_data), String(data), mac))

            return (b'-----BEGIN OPENSSH PRIVATE KEY-----\n' +
                    _wrap_base64(data, _OPENSSH_WRAP_LEN) +
                    b'-----END OPENSSH PRIVATE KEY-----\n')
        else:
            raise KeyExportError('Unknown export format')

    def export_public_key(self, format_name: str = 'openssh') -> bytes:
        """Export a public key in the requested format

           This method returns this object's public key encoded in the
           requested format. Available formats include:

               pkcs1-der, pkcs1-pem, pkcs8-der, pkcs8-pem, openssh, rfc4716

           By default, openssh format will be used.

           :param format_name: (optional)
               The format to export the key in.
           :type format_name: `str`

           :returns: `bytes` representing the exported public key

        """

        if format_name in ('pkcs1-der', 'pkcs1-pem'):
            data = der_encode(self.encode_pkcs1_public())

            if format_name == 'pkcs1-pem':
                keytype = self.pem_name + b' PUBLIC KEY'
                data = (b'-----BEGIN ' + keytype + b'-----\n' +
                        _wrap_base64(data) +
                        b'-----END ' + keytype + b'-----\n')

            return data
        elif format_name in ('pkcs8-der', 'pkcs8-pem'):
            alg_params, pkcs8_data = self.encode_pkcs8_public()
            pkcs8_data = BitString(pkcs8_data)

            if alg_params is OMIT:
                data = der_encode(((self.pkcs8_oid,), pkcs8_data))
            else:
                data = der_encode(((self.pkcs8_oid, alg_params), pkcs8_data))

            if format_name == 'pkcs8-pem':
                data = (b'-----BEGIN PUBLIC KEY-----\n' +
                        _wrap_base64(data) +
                        b'-----END PUBLIC KEY-----\n')

            return data
        elif format_name == 'openssh':
            if self._comment:
                comment = b' ' + self._comment
            else:
                comment = b''

            return (self.algorithm + b' ' +
                    binascii.b2a_base64(self.public_data)[:-1] +
                    comment + b'\n')
        elif format_name == 'rfc4716':
            if self._comment:
                comment = (b'Comment: "' + self._comment + b'"\n')
            else:
                comment = b''

            return (b'---- BEGIN SSH2 PUBLIC KEY ----\n' +
                    comment + _wrap_base64(self.public_data) +
                    b'---- END SSH2 PUBLIC KEY ----\n')
        else:
            raise KeyExportError('Unknown export format')

    def write_private_key(self, filename: FilePath, *args, **kwargs) -> None:
        """Write a private key to a file in the requested format

           This method is a simple wrapper around :meth:`export_private_key`
           which writes the exported key data to a file.

           :param filename:
               The filename to write the private key to.
           :param \\*args,\\ \\*\\*kwargs:
               Additional arguments to pass through to
               :meth:`export_private_key`.
           :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

        """

        write_file(filename, self.export_private_key(*args, **kwargs))

    def write_public_key(self, filename: FilePath, *args, **kwargs) -> None:
        """Write a public key to a file in the requested format

           This method is a simple wrapper around :meth:`export_public_key`
           which writes the exported key data to a file.

           :param filename:
               The filename to write the public key to.
           :param \\*args,\\ \\*\\*kwargs:
               Additional arguments to pass through to
               :meth:`export_public_key`.
           :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

        """

        write_file(filename, self.export_public_key(*args, **kwargs))

    def append_private_key(self, filename: FilePath, *args, **kwargs) -> None:
        """Append a private key to a file in the requested format

           This method is a simple wrapper around :meth:`export_private_key`
           which appends the exported key data to an existing file.

           :param filename:
               The filename to append the private key to.
           :param \\*args,\\ \\*\\*kwargs:
               Additional arguments to pass through to
               :meth:`export_private_key`.
           :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

        """

        write_file(filename, self.export_private_key(*args, **kwargs), 'ab')

    def append_public_key(self, filename: FilePath, *args, **kwargs) -> None:
        """Append a public key to a file in the requested format

           This method is a simple wrapper around :meth:`export_public_key`
           which appends the exported key data to an existing file.

           :param filename:
               The filename to append the public key to.
           :param \\*args,\\ \\*\\*kwargs:
               Additional arguments to pass through to
               :meth:`export_public_key`.
           :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

        """

        write_file(filename, self.export_public_key(*args, **kwargs), 'ab')


class SSHCertificate:
    """Parent class which holds an SSH certificate"""

    is_x509 = False
    is_x509_chain = False

    def __init__(self, algorithm: bytes, sig_algorithms: Sequence[bytes],
                 host_key_algorithms: Sequence[bytes], key: SSHKey,
                 public_data: bytes, comment: _Comment):
        self.algorithm = algorithm
        self.sig_algorithms = sig_algorithms
        self.host_key_algorithms = host_key_algorithms
        self.key = key
        self.public_data = public_data

        self.set_comment(comment)

    @classmethod
    def construct(cls, packet: SSHPacket, algorithm: bytes,
                  key_handler: Optional[Type[SSHKey]],
                  comment: _Comment) -> 'SSHCertificate':
        """Construct an SSH certificate from packetized data"""

        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, type(self)) and
                self.public_data == other.public_data)

    def __hash__(self) -> int:
        return hash(self.public_data)

    def get_algorithm(self) -> str:
        """Return the algorithm associated with this certificate"""

        return self.algorithm.decode('ascii')

    def has_comment(self) -> bool:
        """Return whether a comment is set for this certificate

           :returns: `bool`

        """

        return bool(self._comment)

    def get_comment_bytes(self) -> Optional[bytes]:
        """Return the comment associated with this certificate as a
           byte string

           :returns: `bytes` or `None`

        """

        return self._comment

    def get_comment(self, encoding: str = 'utf-8',
                    errors: str = 'strict') -> Optional[str]:
        """Return the comment associated with this certificate as a
           Unicode string

           :param encoding:
               The encoding to use to decode the comment as a Unicode
               string, defaulting to UTF-8
           :param errors:
               The error handling scheme to use for Unicode decode errors
           :type encoding: `str`
           :type errors: `str`

           :returns: `str` or `None`

           :raises: :exc:`UnicodeDecodeError` if the comment cannot be
                    decoded using the specified encoding

        """

        return self._comment.decode(encoding, errors) if self._comment else None

    def set_comment(self, comment: _Comment, encoding: str = 'utf-8',
                    errors: str = 'strict') -> None:
        """Set the comment associated with this certificate

           :param comment:
               The new comment to associate with this key
           :param encoding:
               The Unicode encoding to use to encode the comment,
               defaulting to UTF-8
           :param errors:
               The error handling scheme to use for Unicode encode errors
           :type comment: `str`, `bytes`, or `None`
           :type encoding: `str`
           :type errors: `str`

           :raises: :exc:`UnicodeEncodeError` if the comment cannot be
                    encoded using the specified encoding

        """

        if isinstance(comment, str):
            comment = comment.encode(encoding, errors)

        self._comment = comment or None

    def export_certificate(self, format_name: str = 'openssh') -> bytes:
        """Export a certificate in the requested format

           This function returns this certificate encoded in the requested
           format. Available formats include:

               der, pem, openssh, rfc4716

           By default, OpenSSH format will be used.

           :param format_name: (optional)
               The format to export the certificate in.
           :type format_name: `str`

           :returns: `bytes` representing the exported certificate

        """

        if self.is_x509:
            if format_name == 'rfc4716':
                raise KeyExportError('RFC4716 format is not supported for '
                                     'X.509 certificates')
        else:
            if format_name in ('der', 'pem'):
                raise KeyExportError('DER and PEM formats are not supported '
                                     'for OpenSSH certificates')

        if format_name == 'der':
            return self.public_data
        elif format_name == 'pem':
            return (b'-----BEGIN CERTIFICATE-----\n' +
                    _wrap_base64(self.public_data) +
                    b'-----END CERTIFICATE-----\n')
        elif format_name == 'openssh':
            if self._comment:
                comment = b' ' + self._comment
            else:
                comment = b''

            return (self.algorithm + b' ' +
                    binascii.b2a_base64(self.public_data)[:-1] +
                    comment + b'\n')
        elif format_name == 'rfc4716':
            if self._comment:
                comment = (b'Comment: "' + self._comment + b'"\n')
            else:
                comment = b''

            return (b'---- BEGIN SSH2 PUBLIC KEY ----\n' +
                    comment + _wrap_base64(self.public_data) +
                    b'---- END SSH2 PUBLIC KEY ----\n')
        else:
            raise KeyExportError('Unknown export format')

    def write_certificate(self, filename: FilePath,
                          format_name: str = 'openssh') -> None:
        """Write a certificate to a file in the requested format

           This function is a simple wrapper around export_certificate
           which writes the exported certificate to a file.

           :param filename:
               The filename to write the certificate to.
           :param format_name: (optional)
               The format to export the certificate in.
           :type filename: :class:`PurePath <pathlib.PurePath>` or `str`
           :type format_name: `str`

        """

        write_file(filename, self.export_certificate(format_name))

    def append_certificate(self, filename: FilePath,
                           format_name: str = 'openssh') -> None:
        """Append a certificate to a file in the requested format

           This function is a simple wrapper around export_certificate
           which appends the exported certificate to an existing file.

           :param filename:
               The filename to append the certificate to.
           :param format_name: (optional)
               The format to export the certificate in.
           :type filename: :class:`PurePath <pathlib.PurePath>` or `str`
           :type format_name: `str`

        """

        write_file(filename, self.export_certificate(format_name), 'ab')


class SSHOpenSSHCertificate(SSHCertificate):
    """Class which holds an OpenSSH certificate"""

    _user_option_encoders: _OpenSSHCertEncoders = ()
    _user_extension_encoders: _OpenSSHCertEncoders = ()
    _host_option_encoders: _OpenSSHCertEncoders = ()
    _host_extension_encoders: _OpenSSHCertEncoders = ()

    _user_option_decoders: _OpenSSHCertDecoders = {}
    _user_extension_decoders: _OpenSSHCertDecoders = {}
    _host_option_decoders: _OpenSSHCertDecoders = {}
    _host_extension_decoders: _OpenSSHCertDecoders = {}

    def __init__(self, algorithm: bytes, key: SSHKey, data: bytes,
                 principals: Sequence[str], options: _OpenSSHCertOptions,
                 signing_key: SSHKey, serial: int, cert_type: int,
                 key_id: str, valid_after: int, valid_before: int,
                 comment: _Comment):
        super().__init__(algorithm, key.sig_algorithms,
                         key.cert_algorithms or (algorithm,),
                         key, data, comment)

        self.principals = principals
        self.options = options
        self.signing_key = signing_key

        self._serial = serial
        self._cert_type = cert_type
        self._key_id = key_id
        self._valid_after = valid_after
        self._valid_before = valid_before

    @classmethod
    def generate(cls, signing_key: 'SSHKey', algorithm: bytes, key: 'SSHKey',
                 serial: int, cert_type: int, key_id: str,
                 principals: Sequence[str], valid_after: int,
                 valid_before: int, options: _OpenSSHCertOptions,
                 sig_alg: bytes, comment: _Comment) -> 'SSHOpenSSHCertificate':
        """Generate a new SSH certificate"""

        principal_bytes = b''.join(String(p) for p in principals)

        if cert_type == CERT_TYPE_USER:
            cert_options = cls._encode_options(options,
                                               cls._user_option_encoders)
            cert_extensions = cls._encode_options(options,
                                                  cls._user_extension_encoders)
        else:
            cert_options = cls._encode_options(options,
                                               cls._host_option_encoders)
            cert_extensions = cls._encode_options(options,
                                                  cls._host_extension_encoders)

        key = key.convert_to_public()

        data = b''.join((String(algorithm),
                         cls._encode(key, serial, cert_type, key_id,
                                     principal_bytes, valid_after,
                                     valid_before, cert_options,
                                     cert_extensions),
                         String(signing_key.public_data)))

        data += String(signing_key.sign(data, sig_alg))

        signing_key = signing_key.convert_to_public()

        return cls(algorithm, key, data, principals, options, signing_key,
                   serial, cert_type, key_id, valid_after, valid_before,
                   comment)

    @classmethod
    def construct(cls, packet: SSHPacket, algorithm: bytes,
                  key_handler: Optional[Type[SSHKey]],
                  comment: _Comment) -> 'SSHOpenSSHCertificate':
        """Construct an SSH certificate from packetized data"""

        assert key_handler is not None

        key_params, serial, cert_type, key_id, \
            principals, valid_after, valid_before, \
            options, extensions = cls._decode(packet, key_handler)

        signing_key = decode_ssh_public_key(packet.get_string())
        data = packet.get_consumed_payload()
        signature = packet.get_string()
        packet.check_end()

        if not signing_key.verify(data, signature):
            raise KeyImportError('Invalid certificate signature')

        key = key_handler.make_public(key_params)
        data = packet.get_consumed_payload()

        try:
            key_id_bytes = key_id.decode('utf-8')
        except UnicodeDecodeError:
            raise KeyImportError('Invalid characters in key ID') from None

        packet = SSHPacket(principals)
        principals: List[str] = []

        while packet:
            try:
                principal = packet.get_string().decode('utf-8')
            except UnicodeDecodeError:
                raise KeyImportError('Invalid characters in principal '
                                     'name') from None

            principals.append(principal)

        if cert_type == CERT_TYPE_USER:
            cert_options = cls._decode_options(
                options, cls._user_option_decoders, True)
            cert_options.update(cls._decode_options(
                extensions, cls._user_extension_decoders, False))
        elif cert_type == CERT_TYPE_HOST:
            cert_options = cls._decode_options(
                options, cls._host_option_decoders, True)
            cert_options.update(cls._decode_options(
                extensions, cls._host_extension_decoders, False))
        else:
            raise KeyImportError('Unknown certificate type')

        return cls(algorithm, key, data, principals, cert_options, signing_key,
                   serial, cert_type, key_id_bytes, valid_after, valid_before,
                   comment)

    @classmethod
    def _encode(cls, key: SSHKey, serial: int, cert_type: int, key_id: str,
                principals: bytes, valid_after: int, valid_before: int,
                options: bytes, extensions: bytes) -> bytes:

        """Encode an SSH certificate"""

        raise NotImplementedError

    @classmethod
    def _decode(cls, packet: SSHPacket,
                key_handler: Type[SSHKey]) -> _OpenSSHCertParams:
        """Decode an SSH certificate"""

        raise NotImplementedError

    @staticmethod
    def _encode_options(options: _OpenSSHCertOptions,
                        encoders: _OpenSSHCertEncoders) -> bytes:
        """Encode options found in this certificate"""

        result = []

        for name, encoder in encoders:
            value = options.get(name)
            if value:
                result.append(String(name) + String(encoder(value)))

        return b''.join(result)

    @staticmethod
    def _encode_bool(_value: object) -> bytes:
        """Encode a boolean option value"""

        return b''

    @staticmethod
    def _encode_force_cmd(force_command: object) -> bytes:
        """Encode a force-command option"""

        return String(cast(BytesOrStr, force_command))

    @staticmethod
    def _encode_source_addr(source_address: object) -> bytes:
        """Encode a source-address option"""

        return NameList(str(addr).encode('ascii')
                        for addr in cast(Sequence[IPNetwork], source_address))

    @staticmethod
    def _decode_bool(_packet: SSHPacket) -> bool:
        """Decode a boolean option value"""

        return True

    @staticmethod
    def _decode_force_cmd(packet: SSHPacket) -> str:
        """Decode a force-command option"""

        try:
            return packet.get_string().decode('utf-8')
        except UnicodeDecodeError:
            raise KeyImportError('Invalid characters in command') from None

    @staticmethod
    def _decode_source_addr(packet: SSHPacket) -> Sequence[IPNetwork]:
        """Decode a source-address option"""

        try:
            return [ip_network(addr.decode('ascii'))
                    for addr in packet.get_namelist()]
        except (UnicodeDecodeError, ValueError):
            raise KeyImportError('Invalid source address') from None

    @staticmethod
    def _decode_options(options: bytes, decoders: _OpenSSHCertDecoders,
                        critical: bool = True) -> _OpenSSHCertOptions:
        """Decode options found in this certificate"""

        packet = SSHPacket(options)
        result: _OpenSSHCertOptions = {}

        while packet:
            name = packet.get_string()

            decoder = decoders.get(name)
            if decoder:
                data_packet = SSHPacket(packet.get_string())
                result[name.decode('ascii')] = decoder(data_packet)
                data_packet.check_end()
            elif critical:
                raise KeyImportError('Unrecognized critical option: ' +
                                     name.decode('ascii', errors='replace'))

        return result

    def validate(self, cert_type: int, principal: Optional[str]) -> None:
        """Validate an OpenSSH certificate"""

        if self._cert_type != cert_type:
            raise ValueError('Invalid certificate type')

        now = time.time()

        if now < self._valid_after:
            raise ValueError('Certificate not yet valid')

        if now >= self._valid_before:
            raise ValueError('Certificate expired')

        if principal is not None and self.principals and \
                principal not in self.principals:
            raise ValueError('Certificate principal mismatch')


class SSHOpenSSHCertificateV01(SSHOpenSSHCertificate):
    """Encoder/decoder class for version 01 OpenSSH certificates"""

    _user_option_encoders = (
        ('force-command',           SSHOpenSSHCertificate._encode_force_cmd),
        ('source-address',          SSHOpenSSHCertificate._encode_source_addr)
    )

    _user_extension_encoders = (
        ('permit-X11-forwarding',   SSHOpenSSHCertificate._encode_bool),
        ('permit-agent-forwarding', SSHOpenSSHCertificate._encode_bool),
        ('permit-port-forwarding',  SSHOpenSSHCertificate._encode_bool),
        ('permit-pty',              SSHOpenSSHCertificate._encode_bool),
        ('permit-user-rc',          SSHOpenSSHCertificate._encode_bool),
        ('no-touch-required',       SSHOpenSSHCertificate._encode_bool)
    )

    _user_option_decoders = {
        b'force-command':           SSHOpenSSHCertificate._decode_force_cmd,
        b'source-address':          SSHOpenSSHCertificate._decode_source_addr
    }

    _user_extension_decoders = {
        b'permit-X11-forwarding':   SSHOpenSSHCertificate._decode_bool,
        b'permit-agent-forwarding': SSHOpenSSHCertificate._decode_bool,
        b'permit-port-forwarding':  SSHOpenSSHCertificate._decode_bool,
        b'permit-pty':              SSHOpenSSHCertificate._decode_bool,
        b'permit-user-rc':          SSHOpenSSHCertificate._decode_bool,
        b'no-touch-required':       SSHOpenSSHCertificate._decode_bool
    }

    @classmethod
    def _encode(cls, key: SSHKey, serial: int, cert_type: int, key_id: str,
                principals: bytes, valid_after: int, valid_before: int,
                options: bytes, extensions: bytes) -> bytes:
        """Encode a version 01 SSH certificate"""

        return b''.join((String(os.urandom(32)), key.encode_ssh_public(),
                         UInt64(serial), UInt32(cert_type), String(key_id),
                         String(principals), UInt64(valid_after),
                         UInt64(valid_before), String(options),
                         String(extensions), String('')))

    @classmethod
    def _decode(cls, packet: SSHPacket,
                key_handler: Type[SSHKey]) -> _OpenSSHCertParams:
        """Decode a version 01 SSH certificate"""

        _ = packet.get_string()                             # nonce
        key_params = key_handler.decode_ssh_public(packet)
        serial = packet.get_uint64()
        cert_type = packet.get_uint32()
        key_id = packet.get_string()
        principals = packet.get_string()
        valid_after = packet.get_uint64()
        valid_before = packet.get_uint64()
        options = packet.get_string()
        extensions = packet.get_string()
        _ = packet.get_string()                             # reserved

        return (key_params, serial, cert_type, key_id, principals,
                valid_after, valid_before, options, extensions)


class SSHX509Certificate(SSHCertificate):
    """Encoder/decoder class for SSH X.509 certificates"""

    is_x509 = True

    def __init__(self, key: SSHKey, x509_cert: 'X509Certificate',
                 comment: _Comment = None):
        super().__init__(b'x509v3-' + key.algorithm, key.x509_algorithms,
                         key.x509_algorithms, key, x509_cert.data,
                         x509_cert.comment or comment)

        self.subject = x509_cert.subject
        self.issuer = x509_cert.issuer
        self.issuer_hash = x509_cert.issuer_hash
        self.user_principals = x509_cert.user_principals
        self.x509_cert = x509_cert

    def _expand_trust_store(self, cert: 'SSHX509Certificate',
                            trusted_cert_paths: Sequence[FilePath],
                            trust_store: Set['SSHX509Certificate']) -> None:
        """Look up certificates by issuer hash to build a trust store"""

        issuer_hash = cert.issuer_hash

        for path in trusted_cert_paths:
            idx = 0

            try:
                while True:
                    cert_path = Path(path, issuer_hash + '.' + str(idx))
                    idx += 1

                    c = cast('SSHX509Certificate', read_certificate(cert_path))

                    if c.subject != cert.issuer or c in trust_store:
                        continue

                    trust_store.add(c)
                    self._expand_trust_store(c, trusted_cert_paths, trust_store)
            except (OSError, KeyImportError):
                pass

    @classmethod
    def construct(cls, packet: SSHPacket, algorithm: bytes,
                  key_handler: Optional[Type[SSHKey]],
                  comment: _Comment) -> 'SSHX509Certificate':
        """Construct an SSH X.509 certificate from packetized data"""

        raise RuntimeError # pragma: no cover

    @classmethod
    def generate(cls, signing_key: 'SSHKey', key: 'SSHKey', subject: str,
                 issuer: Optional[str], serial: Optional[int],
                 valid_after: int, valid_before: int, ca: bool,
                 ca_path_len: Optional[int], purposes: X509CertPurposes,
                 user_principals: _CertPrincipals,
                 host_principals: _CertPrincipals, hash_name: str,
                 comment: _Comment) -> 'SSHX509Certificate':
        """Generate a new X.509 certificate"""

        key = key.convert_to_public()

        x509_cert = generate_x509_certificate(signing_key.pyca_key,
                                              key.pyca_key, subject, issuer,
                                              serial, valid_after, valid_before,
                                              ca, ca_path_len, purposes,
                                              user_principals, host_principals,
                                              hash_name, comment)

        return cls(key, x509_cert)

    @classmethod
    def construct_from_der(cls, data: bytes,
                           comment: _Comment = None) -> 'SSHX509Certificate':
        """Construct an SSH X.509 certificate from DER data"""

        try:
            x509_cert = import_x509_certificate(data)
            key = import_public_key(x509_cert.key_data)
        except ValueError as exc:
            raise KeyImportError(str(exc)) from None

        return cls(key, x509_cert, comment)

    def validate_chain(self, trust_chain: Sequence['SSHX509Certificate'],
                       trusted_certs: Sequence['SSHX509Certificate'],
                       trusted_cert_paths: Sequence[FilePath],
                       purposes: X509CertPurposes, user_principal: str = '',
                       host_principal: str = '') -> None:
        """Validate an X.509 certificate chain"""

        trust_store = {c for c in trust_chain if c.subject != c.issuer} | \
            set(trusted_certs)

        if trusted_cert_paths:
            self._expand_trust_store(self, trusted_cert_paths, trust_store)

            for c in trust_chain:
                self._expand_trust_store(c, trusted_cert_paths, trust_store)

        self.x509_cert.validate([c.x509_cert for c in trust_store],
                                purposes, user_principal, host_principal)


class SSHX509CertificateChain(SSHCertificate):
    """Encoder/decoder class for an SSH X.509 certificate chain"""

    is_x509_chain = True

    def __init__(self, algorithm: bytes, certs: Sequence[SSHCertificate],
                 ocsp_responses: Sequence[bytes], comment: _Comment):
        key = certs[0].key
        data = self._public_data(algorithm, certs, ocsp_responses)

        super().__init__(algorithm, key.x509_algorithms, key.x509_algorithms,
                         key, data, comment)

        x509_certs = cast(Sequence[SSHX509Certificate], certs)
        first_cert = x509_certs[0]
        last_cert = x509_certs[-1]

        self.subject = first_cert.subject
        self.issuer = last_cert.issuer
        self.user_principals = first_cert.user_principals

        self._certs = x509_certs
        self._ocsp_responses = ocsp_responses

    @staticmethod
    def _public_data(algorithm: bytes, certs: Sequence[SSHCertificate],
                     ocsp_responses: Sequence[bytes]) -> bytes:
        """Return the X509 chain public data"""

        return (String(algorithm) + UInt32(len(certs)) +
                b''.join(String(c.public_data) for c in certs) +
                UInt32(len(ocsp_responses)) +
                b''.join(String(resp) for resp in ocsp_responses))

    @classmethod
    def construct(cls, packet: SSHPacket, algorithm: bytes,
                  key_handler: Optional[Type[SSHKey]],
                  comment: _Comment) -> 'SSHX509CertificateChain':
        """Construct an SSH X.509 certificate from packetized data"""

        cert_count = packet.get_uint32()
        certs = [import_certificate(packet.get_string())
                 for _ in range(cert_count)]

        ocsp_resp_count = packet.get_uint32()
        ocsp_responses = [packet.get_string() for _ in range(ocsp_resp_count)]

        packet.check_end()

        if not certs:
            raise KeyImportError('No certificates present')

        return cls(algorithm, certs, ocsp_responses, comment)

    @classmethod
    def construct_from_certs(cls, certs: Sequence['SSHCertificate']) -> \
            'SSHX509CertificateChain':
        """Construct an SSH X.509 certificate chain from certificates"""

        cert = certs[0]

        return cls(cert.algorithm, certs, (), cert.get_comment_bytes())

    def adjust_public_data(self, algorithm: bytes) -> bytes:
        """Adjust public data to reflect chosen signature algorithm"""

        return self._public_data(algorithm, self._certs, self._ocsp_responses)

    def validate_chain(self, trusted_certs: Sequence[SSHX509Certificate],
                       trusted_cert_paths: Sequence[FilePath],
                       revoked_certs: Set[SSHX509Certificate],
                       purposes: X509CertPurposes, user_principal: str = '',
                       host_principal: str = '') -> None:
        """Validate an X.509 certificate chain"""

        if revoked_certs:
            for cert in self._certs:
                if cert in revoked_certs:
                    raise ValueError('Revoked X.509 certificate in '
                                     'certificate chain')

        self._certs[0].validate_chain(self._certs[1:], trusted_certs,
                                      trusted_cert_paths, purposes,
                                      user_principal, host_principal)


class SSHKeyPair:
    """Parent class which represents an asymmetric key pair

       This is an abstract class which provides a method to sign data
       with a private key and members to access the corresponding
       algorithm and public key or certificate information needed to
       identify what key was used for signing.

    """

    _key_type = 'unknown'

    def __init__(self, algorithm: bytes, sig_algorithm: bytes,
                 sig_algorithms: Sequence[bytes],
                 host_key_algorithms: Sequence[bytes],
                 public_data: bytes, comment: _Comment,
                 cert: Optional[SSHCertificate] = None,
                 filename: Optional[bytes] = None,
                 use_executor: bool = False,
                 use_webauthn: bool = False):
        self.key_algorithm = algorithm
        self.key_public_data = public_data

        self.set_comment(comment)
        self._cert = cert
        self._filename = filename

        self.use_executor = use_executor
        self.use_webauthn = use_webauthn

        if cert:
            if cert.key.public_data != self.key_public_data:
                raise ValueError('Certificate key mismatch')

            self.algorithm = cert.algorithm

            if cert.is_x509_chain:
                self.sig_algorithm = cert.algorithm
            else:
                self.sig_algorithm = sig_algorithm

            self.sig_algorithms = cert.sig_algorithms
            self.host_key_algorithms = cert.host_key_algorithms
            self.public_data = cert.public_data
        else:
            self.algorithm = algorithm
            self.sig_algorithm = algorithm
            self.sig_algorithms = sig_algorithms
            self.host_key_algorithms = host_key_algorithms
            self.public_data = public_data

    def get_key_type(self) -> str:
        """Return what type of key pair this is

           This method returns 'local' for locally loaded keys, and
           'agent' for keys managed by an SSH agent.

        """

        return self._key_type

    @property
    def has_cert(self) -> bool:
        """ Return if this key pair has an associated cert"""

        return bool(self._cert)

    @property
    def has_x509_chain(self) -> bool:
        """ Return if this key pair has an associated X.509 cert chain"""

        return self._cert.is_x509_chain if self._cert else False

    def get_algorithm(self) -> str:
        """Return the algorithm associated with this key pair"""

        return self.algorithm.decode('ascii')

    def get_agent_private_key(self) -> bytes:
        """Return binary encoding of keypair for upload to SSH agent"""

        # pylint: disable=no-self-use
        raise KeyImportError('Private key export to agent not supported')

    def get_comment_bytes(self) -> Optional[bytes]:
        """Return the comment associated with this key pair as a
           byte string

           :returns: `bytes` or `None`

        """

        return self._comment or self._filename

    def get_comment(self, encoding: str = 'utf-8',
                    errors: str = 'strict') -> Optional[str]:
        """Return the comment associated with this key pair as a
           Unicode string

           :param encoding:
               The encoding to use to decode the comment as a Unicode
               string, defaulting to UTF-8
           :param errors:
               The error handling scheme to use for Unicode decode errors
           :type encoding: `str`
           :type errors: `str`

           :returns: `str` or `None`

           :raises: :exc:`UnicodeDecodeError` if the comment cannot be
                    decoded using the specified encoding

        """

        comment = self.get_comment_bytes()

        return comment.decode(encoding, errors) if comment else None

    def set_comment(self, comment: _Comment, encoding: str = 'utf-8',
                    errors: str = 'strict') -> None:
        """Set the comment associated with this key pair

           :param comment:
               The new comment to associate with this key
           :param encoding:
               The Unicode encoding to use to encode the comment,
               defaulting to UTF-8
           :param errors:
               The error handling scheme to use for Unicode encode errors
           :type comment: `str`, `bytes`, or `None`
           :type encoding: `str`
           :type errors: `str`

           :raises: :exc:`UnicodeEncodeError` if the comment cannot be
                    encoded using the specified encoding

        """

        if isinstance(comment, str):
            comment = comment.encode(encoding, errors)

        self._comment = comment or None

    def set_certificate(self, cert: SSHCertificate) -> None:
        """Set certificate to use with this key"""

        if cert.key.public_data != self.key_public_data:
            raise ValueError('Certificate key mismatch')

        self._cert = cert
        self.algorithm = cert.algorithm

        if cert.is_x509_chain:
            self.sig_algorithm = cert.algorithm
        else:
            self.sig_algorithm = self.key_algorithm

        self.sig_algorithms = cert.sig_algorithms
        self.host_key_algorithms = cert.host_key_algorithms
        self.public_data = cert.public_data

    def set_sig_algorithm(self, sig_algorithm: bytes) -> None:
        """Set the signature algorithm to use when signing data"""

        try:
            sig_algorithm = _certificate_sig_alg_map[sig_algorithm]
        except KeyError:
            pass

        self.sig_algorithm = sig_algorithm

        if not self.has_cert:
            self.algorithm = sig_algorithm
        elif self.has_x509_chain:
            self.algorithm = sig_algorithm

            cert = cast('SSHX509CertificateChain', self._cert)
            self.public_data = cert.adjust_public_data(sig_algorithm)

    def sign(self, data: bytes) -> bytes:
        """Sign a block of data with this private key"""

        # pylint: disable=no-self-use
        raise RuntimeError # pragma: no cover


class SSHLocalKeyPair(SSHKeyPair):
    """Class which holds a local asymmetric key pair

       This class holds a private key and associated public data
       which can either be the matching public key or a certificate
       which has signed that public key.

    """

    _key_type = 'local'

    def __init__(self, key: SSHKey, pubkey: Optional[SSHKey] = None,
                 cert: Optional[SSHCertificate] = None):
        if pubkey and pubkey.public_data != key.public_data:
            raise ValueError('Public key mismatch')

        if key.has_comment():
            comment = key.get_comment_bytes()
        elif cert and cert.has_comment():
            comment = cert.get_comment_bytes()
        elif pubkey and pubkey.has_comment():
            comment = pubkey.get_comment_bytes()
        else:
            comment = None

        super().__init__(key.algorithm, key.algorithm, key.sig_algorithms,
                         key.sig_algorithms, key.public_data, comment,
                         cert, key.get_filename(), key.use_executor,
                         key.use_webauthn)

        self._key = key

    def get_agent_private_key(self) -> bytes:
        """Return binary encoding of keypair for upload to SSH agent"""

        if self._cert:
            data = String(self.public_data) + \
                       self._key.encode_agent_cert_private()
        else:
            data = self._key.encode_ssh_private()

        return String(self.algorithm) + data

    def sign(self, data: bytes) -> bytes:
        """Sign a block of data with this private key"""

        return self._key.sign(data, self.sig_algorithm)


def _parse_openssh(data: bytes) -> Tuple[bytes, Optional[bytes], bytes]:
    """Parse an OpenSSH format public key or certificate"""

    line = data.split(None, 2)

    if len(line) < 2:
        raise KeyImportError('Invalid OpenSSH public key or certificate')
    elif len(line) == 2:
        comment = None
    else:
        comment = line[2]

    if (line[0] not in _public_key_alg_map and
            line[0] not in _certificate_alg_map):
        raise KeyImportError('Unknown OpenSSH public key algorithm')

    try:
        return line[0], comment, binascii.a2b_base64(line[1])
    except binascii.Error:
        raise KeyImportError('Invalid OpenSSH public key '
                             'or certificate') from None


def _parse_pem(data: bytes) -> Tuple[Mapping[bytes, bytes], bytes]:
    """Parse a PEM data block"""

    start = 0
    end: Optional[int] = None
    headers: Dict[bytes, bytes] = {}

    while True:
        end = data.find(b'\n', start) + 1

        line = data[start:end] if end else data[start:]
        line = line.rstrip()

        if b':' in line:
            hdr, value = line.split(b':', 1)
            headers[hdr.strip()] = value.strip()
        else:
            break

        start = end if end != 0 else len(data)

    try:
        return headers, binascii.a2b_base64(data[start:])
    except binascii.Error:
        raise KeyImportError('Invalid PEM data') from None


def _parse_rfc4716(data: bytes) -> Tuple[Optional[bytes], bytes]:
    """Parse an RFC 4716 data block"""

    start = 0
    end = None
    hdr = b''
    comment = None

    while True:
        end = data.find(b'\n', start) + 1
        line = data[start:end] if end else data[start:]
        line = line.rstrip()

        if line[-1:] == b'\\':
            hdr += line[:-1]
        else:
            hdr += line
            if b':' in hdr:
                hdr, value = hdr.split(b':', 1)

                if hdr.strip() == b'Comment':
                    comment = value.strip()
                    if comment[:1] == b'"' and comment[-1:] == b'"':
                        comment = comment[1:-1]

                hdr = b''
            else:
                break

        start = end if end != 0 else len(data)

    try:
        return comment, binascii.a2b_base64(data[start:])
    except binascii.Error:
        raise KeyImportError('Invalid RFC 4716 data') from None


def _match_block(data: bytes, start: int, header: bytes,
                 fmt: str) -> Tuple[bytes, int]:
    """Match a block of data wrapped in a header/footer"""

    match = re.compile(b'^' + header[:5] + b'END' + header[10:] +
                       rb'[ \t\r\f\v]*$', re.M).search(data, start)

    if not match:
        raise KeyImportError(f'Missing {fmt} footer')

    return data[start:match.start()], match.end()


def _match_next(data: bytes, keytype: bytes, public: bool = False) -> \
        Tuple[Optional[str], Tuple, Optional[int]]:
    """Find the next key/certificate and call the appropriate decode"""

    end: Optional[int]

    if data.startswith(b'\x30'):
        try:
            key_data, end = der_decode_partial(data)
            return 'der', (key_data,), end
        except ASN1DecodeError:
            pass

    start = 0
    end = None

    while end != 0:
        end = data.find(b'\n', start) + 1

        line = data[start:end] if end else data[start:]
        line = line.rstrip()

        if (line.startswith(b'-----BEGIN ') and
                line.endswith(b' ' + keytype + b'-----')):
            pem_name = line[11:-(6+len(keytype))].strip()
            data, end = _match_block(data, end, line, 'PEM')
            headers, data = _parse_pem(data)
            return 'pem', (pem_name, headers, data), end
        elif public:
            if line == b'---- BEGIN SSH2 PUBLIC KEY ----':
                data, end = _match_block(data, end, line, 'RFC 4716')
                return 'rfc4716', _parse_rfc4716(data), end
            else:
                try:
                    cert = _parse_openssh(line)
                except KeyImportError:
                    pass
                else:
                    return 'openssh', cert, (end if end else len(data))

        start = end

    return None, (), len(data)


def _decode_pkcs1_private(
        pem_name: bytes, key_data: object,
        unsafe_skip_rsa_key_validation: Optional[bool]) -> SSHKey:
    """Decode a PKCS#1 format private key"""

    handler = _pem_map.get(pem_name)
    if handler is None:
        raise KeyImportError('Unknown PEM key type: ' +
                             pem_name.decode('ascii'))

    key_params = handler.decode_pkcs1_private(key_data)
    if key_params is None:
        raise KeyImportError(
            f'Invalid {pem_name.decode("ascii")} private key')

    if pem_name == b'RSA':
        key_params = cast(Tuple, key_params) + \
            (unsafe_skip_rsa_key_validation,)

    return handler.make_private(key_params)


def _decode_pkcs1_public(pem_name: bytes, key_data: object) -> SSHKey:
    """Decode a PKCS#1 format public key"""

    handler = _pem_map.get(pem_name)
    if handler is None:
        raise KeyImportError('Unknown PEM key type: ' +
                             pem_name.decode('ascii'))

    key_params = handler.decode_pkcs1_public(key_data)
    if key_params is None:
        raise KeyImportError(f'Invalid {pem_name.decode("ascii")} public key')

    return handler.make_public(key_params)


def _decode_pkcs8_private(
        key_data: object,
        unsafe_skip_rsa_key_validation: Optional[bool]) -> SSHKey:
    """Decode a PKCS#8 format private key"""

    if (isinstance(key_data, tuple) and len(key_data) >= 3 and
            key_data[0] in (0, 1) and isinstance(key_data[1], tuple) and
            1 <= len(key_data[1]) <= 2 and isinstance(key_data[2], bytes)):
        if len(key_data[1]) == 2:
            alg, alg_params = key_data[1]
        else:
            alg, alg_params = key_data[1][0], OMIT

        handler = _pkcs8_oid_map.get(alg)
        if handler is None:
            raise KeyImportError('Unknown PKCS#8 algorithm')

        key_params = handler.decode_pkcs8_private(alg_params, key_data[2])
        if key_params is None:
            key_type = handler.pem_name.decode('ascii') if \
                       handler.pem_name else 'PKCS#8'
            raise KeyImportError(f'Invalid {key_type} private key')

        if alg == ObjectIdentifier('1.2.840.113549.1.1.1'):
            key_params = cast(Tuple, key_params) + \
                (unsafe_skip_rsa_key_validation,)

        return handler.make_private(key_params)
    else:
        raise KeyImportError('Invalid PKCS#8 private key')


def _decode_pkcs8_public(key_data: object) -> SSHKey:
    """Decode a PKCS#8 format public key"""

    if (isinstance(key_data, tuple) and len(key_data) == 2 and
            isinstance(key_data[0], tuple) and 1 <= len(key_data[0]) <= 2 and
            isinstance(key_data[1], BitString) and key_data[1].unused == 0):
        if len(key_data[0]) == 2:
            alg, alg_params = key_data[0]
        else:
            alg, alg_params = key_data[0][0], OMIT

        handler = _pkcs8_oid_map.get(alg)
        if handler is None:
            raise KeyImportError('Unknown PKCS#8 algorithm')

        key_params = handler.decode_pkcs8_public(alg_params, key_data[1].value)
        if key_params is None:
            key_type = handler.pem_name.decode('ascii') if \
                       handler.pem_name else 'PKCS#8'
            raise KeyImportError(f'Invalid {key_type} public key')

        return handler.make_public(key_params)
    else:
        raise KeyImportError('Invalid PKCS#8 public key')


def _decode_openssh_private(
        data: bytes, passphrase: Optional[BytesOrStr],
        unsafe_skip_rsa_key_validation: Optional[bool]) -> SSHKey:
    """Decode an OpenSSH format private key"""

    try:
        if not data.startswith(_OPENSSH_KEY_V1):
            raise KeyImportError('Unrecognized OpenSSH private key type')

        data = data[len(_OPENSSH_KEY_V1):]
        packet = SSHPacket(data)

        cipher_name = packet.get_string()
        kdf = packet.get_string()
        kdf_data = packet.get_string()
        nkeys = packet.get_uint32()
        _ = packet.get_string()                 # public_key
        key_data = packet.get_string()
        mac = packet.get_remaining_payload()

        if nkeys != 1:
            raise KeyImportError('Invalid OpenSSH private key')

        if cipher_name != b'none':
            if passphrase is None:
                raise KeyImportError('Passphrase must be specified to import '
                                     'encrypted private keys')

            try:
                key_size, iv_size, _, _, _, _ = \
                    get_encryption_params(cipher_name)
            except KeyError:
                raise KeyEncryptionError('Unknown cipher: ' +
                                         cipher_name.decode('ascii')) from None

            if kdf != b'bcrypt':
                raise KeyEncryptionError('Unknown kdf: ' + kdf.decode('ascii'))

            if not _bcrypt_available: # pragma: no cover
                raise KeyEncryptionError('OpenSSH private key encryption '
                                         'requires bcrypt with KDF support')

            packet = SSHPacket(kdf_data)
            salt = packet.get_string()
            rounds = packet.get_uint32()
            packet.check_end()

            if isinstance(passphrase, str):
                passphrase = passphrase.encode('utf-8')

            try:
                bcrypt_key = bcrypt.kdf(passphrase, salt, key_size + iv_size,
                                        rounds, ignore_few_rounds=True)
            except ValueError:
                raise KeyEncryptionError('Invalid OpenSSH '
                                         'private key') from None

            cipher = get_encryption(cipher_name, bcrypt_key[:key_size],
                                    bcrypt_key[key_size:])

            decrypted_key = cipher.decrypt_packet(0, b'', key_data, 0, mac)

            if decrypted_key is None:
                raise KeyEncryptionError('Incorrect passphrase')

            key_data = decrypted_key

        packet = SSHPacket(key_data)

        check1 = packet.get_uint32()
        check2 = packet.get_uint32()
        if check1 != check2:
            if cipher_name != b'none':
                raise KeyEncryptionError('Incorrect passphrase') from None
            else:
                raise KeyImportError('Invalid OpenSSH private key')

        alg = packet.get_string()
        handler = _public_key_alg_map.get(alg)
        if not handler:
            raise KeyImportError('Unknown OpenSSH private key algorithm')

        key_params = handler.decode_ssh_private(packet)
        comment = packet.get_string()
        pad = packet.get_remaining_payload()

        if len(pad) >= 256 or pad != bytes(range(1, len(pad) + 1)):
            raise KeyImportError('Invalid OpenSSH private key')

        if alg == b'ssh-rsa':
            key_params = cast(Tuple, key_params) + \
                (unsafe_skip_rsa_key_validation,)

        key = handler.make_private(key_params)
        key.set_comment(comment)
        return key
    except PacketDecodeError:
        raise KeyImportError('Invalid OpenSSH private key') from None


def _decode_openssh_public(data: bytes) -> SSHKey:
    """Decode public key within OpenSSH format private key"""

    try:
        if not data.startswith(_OPENSSH_KEY_V1):
            raise KeyImportError('Unrecognized OpenSSH private key type')

        data = data[len(_OPENSSH_KEY_V1):]
        packet = SSHPacket(data)

        _ = packet.get_string()                 # cipher_name
        _ = packet.get_string()                 # kdf
        _ = packet.get_string()                 # kdf_data
        nkeys = packet.get_uint32()
        pubkey = packet.get_string()

        if nkeys != 1:
            raise KeyImportError('Invalid OpenSSH private key')

        return decode_ssh_public_key(pubkey)
    except PacketDecodeError:
        raise KeyImportError('Invalid OpenSSH private key') from None


def _decode_der_private(
        key_data: object, passphrase: Optional[BytesOrStr],
        unsafe_skip_rsa_key_validation: Optional[bool]) -> SSHKey:
    """Decode a DER format private key"""

    # First, if there's a passphrase, try to decrypt PKCS#8
    if passphrase is not None:
        try:
            key_data = pkcs8_decrypt(key_data, passphrase)
        except KeyEncryptionError:
            # Decryption failed - try decoding it as unencrypted
            pass

    # Then, try to decode PKCS#8
    try:
        return _decode_pkcs8_private(key_data, unsafe_skip_rsa_key_validation)
    except KeyImportError:
        # PKCS#8 failed - try PKCS#1 instead
        pass

    # If that fails, try each of the possible PKCS#1 encodings
    for pem_name in _pem_map:
        try:
            return _decode_pkcs1_private(pem_name, key_data,
                                         unsafe_skip_rsa_key_validation)
        except KeyImportError:
            # Try the next PKCS#1 encoding
            pass

    raise KeyImportError('Invalid DER private key')


def _decode_der_public(key_data: object) -> SSHKey:
    """Decode a DER format public key"""

    # First, try to decode PKCS#8
    try:
        return _decode_pkcs8_public(key_data)
    except KeyImportError:
        # PKCS#8 failed - try PKCS#1 instead
        pass

    # If that fails, try each of the possible PKCS#1 encodings
    for pem_name in _pem_map:
        try:
            return _decode_pkcs1_public(pem_name, key_data)
        except KeyImportError:
            # Try the next PKCS#1 encoding
            pass

    raise KeyImportError('Invalid DER public key')


def _decode_der_certificate(data: bytes,
                            comment: _Comment = None) -> SSHCertificate:
    """Decode a DER format X.509 certificate"""

    return SSHX509Certificate.construct_from_der(data, comment)


def _decode_pem_private(
        pem_name: bytes, headers: Mapping[bytes, bytes],
        data: bytes, passphrase: Optional[BytesOrStr],
        unsafe_skip_rsa_key_validation: Optional[bool]) -> SSHKey:
    """Decode a PEM format private key"""

    if pem_name == b'OPENSSH':
        return _decode_openssh_private(data, passphrase,
                                       unsafe_skip_rsa_key_validation)

    if headers.get(b'Proc-Type') == b'4,ENCRYPTED':
        if passphrase is None:
            raise KeyImportError('Passphrase must be specified to import '
                                 'encrypted private keys')

        dek_info = headers.get(b'DEK-Info', b'').split(b',')
        if len(dek_info) != 2:
            raise KeyImportError('Invalid PEM encryption params')

        alg, iv = dek_info
        try:
            iv = binascii.a2b_hex(iv)
        except binascii.Error:
            raise KeyImportError('Invalid PEM encryption params') from None

        try:
            data = pkcs1_decrypt(data, alg, iv, passphrase)
        except KeyEncryptionError:
            raise KeyImportError('Unable to decrypt PKCS#1 '
                                 'private key') from None

    try:
        key_data = der_decode(data)
    except ASN1DecodeError:
        raise KeyImportError('Invalid PEM private key') from None

    if pem_name == b'ENCRYPTED':
        if passphrase is None:
            raise KeyImportError('Passphrase must be specified to import '
                                 'encrypted private keys')

        pem_name = b''

        try:
            key_data = pkcs8_decrypt(key_data, passphrase)
        except KeyEncryptionError:
            raise KeyImportError('Unable to decrypt PKCS#8 '
                                 'private key') from None

    if pem_name:
        return _decode_pkcs1_private(pem_name, key_data,
                                     unsafe_skip_rsa_key_validation)
    else:
        return _decode_pkcs8_private(key_data, unsafe_skip_rsa_key_validation)


def _decode_pem_public(pem_name: bytes, data: bytes) -> SSHKey:
    """Decode a PEM format public key"""

    try:
        key_data = der_decode(data)
    except ASN1DecodeError:
        raise KeyImportError('Invalid PEM public key') from None

    if pem_name:
        return _decode_pkcs1_public(pem_name, key_data)
    else:
        return _decode_pkcs8_public(key_data)


def _decode_pem_certificate(pem_name: bytes, data: bytes) -> SSHCertificate:
    """Decode a PEM format X.509 certificate"""

    if pem_name == b'TRUSTED':
        # Strip off OpenSSL trust information
        try:
            _, end = der_decode_partial(data)
            data = data[:end]
        except ASN1DecodeError:
            raise KeyImportError('Invalid PEM trusted certificate') from None
    elif pem_name:
        raise KeyImportError('Invalid PEM certificate')

    return SSHX509Certificate.construct_from_der(data)


def _decode_private(
        data: bytes, passphrase: Optional[BytesOrStr],
        unsafe_skip_rsa_key_validation: Optional[bool]) -> \
            Tuple[Optional[SSHKey], Optional[int]]:
    """Decode a private key"""

    fmt, key_info, end = _match_next(data, b'PRIVATE KEY')

    key: Optional[SSHKey]

    if fmt == 'der':
        key = _decode_der_private(key_info[0], passphrase,
                                  unsafe_skip_rsa_key_validation)
    elif fmt == 'pem':
        pem_name, headers, data = key_info
        key = _decode_pem_private(pem_name, headers, data, passphrase,
                                  unsafe_skip_rsa_key_validation)
    else:
        key = None

    return key, end


def _decode_public(data: bytes) -> Tuple[Optional[SSHKey], Optional[int]]:
    """Decode a public key"""

    fmt, key_info, end = _match_next(data, b'PUBLIC KEY', public=True)

    key: Optional[SSHKey]

    if fmt == 'der':
        key = _decode_der_public(key_info[0])
    elif fmt == 'pem':
        pem_name, _, data = key_info
        key = _decode_pem_public(pem_name, data)
    elif fmt == 'openssh':
        algorithm, comment, data = key_info
        key = decode_ssh_public_key(data)

        if algorithm != key.algorithm:
            raise KeyImportError('Public key algorithm mismatch')

        key.set_comment(comment)
    elif fmt == 'rfc4716':
        comment, data = key_info
        key = decode_ssh_public_key(data)
        key.set_comment(comment)
    else:
        fmt, key_info, end = _match_next(data, b'PRIVATE KEY')

        if fmt == 'pem' and key_info[0] == b'OPENSSH':
            key = _decode_openssh_public(key_info[2])
        else:
            key, _ = _decode_private(data, None, False)

            if key:
                key = key.convert_to_public()

    return key, end


def _decode_certificate(data: bytes) -> \
        Tuple[Optional[SSHCertificate], Optional[int]]:
    """Decode a certificate"""

    fmt, key_info, end = _match_next(data, b'CERTIFICATE', public=True)

    cert: Optional[SSHCertificate]

    if fmt == 'der':
        cert = _decode_der_certificate(data[:end])
    elif fmt == 'pem':
        pem_name, _, data = key_info
        cert = _decode_pem_certificate(pem_name, data)
    elif fmt == 'openssh':
        algorithm, comment, data = key_info

        if algorithm.startswith(b'x509v3-'):
            cert = _decode_der_certificate(data, comment)
        else:
            cert = decode_ssh_certificate(data, comment)
    elif fmt == 'rfc4716':
        comment, data = key_info
        cert = decode_ssh_certificate(data, comment)
    else:
        cert = None

    return cert, end


def _decode_private_list(
        data: bytes, passphrase: Optional[BytesOrStr],
        unsafe_skip_rsa_key_validation: Optional[bool]) -> Sequence[SSHKey]:
    """Decode a private key list"""

    keys: List[SSHKey] = []

    while data:
        key, end = _decode_private(data, passphrase,
                                   unsafe_skip_rsa_key_validation)

        if key:
            keys.append(key)

        data = data[end:]

    return keys


def _decode_public_list(data: bytes) -> Sequence[SSHKey]:
    """Decode a public key list"""

    keys: List[SSHKey] = []

    while data:
        key, end = _decode_public(data)

        if key:
            keys.append(key)

        data = data[end:]

    return keys


def _decode_certificate_list(data: bytes) -> Sequence[SSHCertificate]:
    """Decode a certificate list"""

    certs: List[SSHCertificate] = []

    while data:
        cert, end = _decode_certificate(data)

        if cert:
            certs.append(cert)

        data = data[end:]

    return certs


def register_sk_alg(sk_alg: int, handler: Type[SSHKey], *args: object) -> None:
    """Register a new security key algorithm"""

    _sk_alg_map[sk_alg] = handler, args


def register_public_key_alg(algorithm: bytes, handler: Type[SSHKey],
                            default: bool,
                            sig_algorithms: Optional[Sequence[bytes]] = \
                                None) -> None:
    """Register a new public key algorithm"""

    if not sig_algorithms:
        sig_algorithms = handler.sig_algorithms

    _public_key_algs.extend(sig_algorithms)

    if default:
        _default_public_key_algs.extend(sig_algorithms)

    _public_key_alg_map[algorithm] = handler

    if handler.pem_name:
        _pem_map[handler.pem_name] = handler

    if handler.pkcs8_oid: # pragma: no branch
        _pkcs8_oid_map[handler.pkcs8_oid] = handler


def register_certificate_alg(version: int, algorithm: bytes,
                             cert_algorithm: bytes,
                             key_handler: Type[SSHKey],
                             cert_handler: Type[SSHOpenSSHCertificate],
                             default: bool) -> None:
    """Register a new certificate algorithm"""

    _certificate_algs.append(cert_algorithm)

    if default:
        _default_certificate_algs.append(cert_algorithm)

    _certificate_alg_map[cert_algorithm] = (key_handler, cert_handler)

    _certificate_sig_alg_map[cert_algorithm] = algorithm

    _certificate_version_map[algorithm, version] = \
        (cert_algorithm, cert_handler)


def register_x509_certificate_alg(cert_algorithm: bytes, default: bool) -> None:
    """Register a new X.509 certificate algorithm"""

    if _x509_available: # pragma: no branch
        _x509_certificate_algs.append(cert_algorithm)

        if default:
            _default_x509_certificate_algs.append(cert_algorithm)

        _certificate_alg_map[cert_algorithm] = (None, SSHX509CertificateChain)


def get_public_key_algs() -> List[bytes]:
    """Return supported public key algorithms"""

    return _public_key_algs


def get_default_public_key_algs() -> List[bytes]:
    """Return default public key algorithms"""

    return _default_public_key_algs


def get_certificate_algs() -> List[bytes]:
    """Return supported certificate-based public key algorithms"""

    return _certificate_algs


def get_default_certificate_algs() -> List[bytes]:
    """Return default certificate-based public key algorithms"""

    return _default_certificate_algs


def get_x509_certificate_algs() -> List[bytes]:
    """Return supported X.509 certificate-based public key algorithms"""

    return _x509_certificate_algs


def get_default_x509_certificate_algs() -> List[bytes]:
    """Return default X.509 certificate-based public key algorithms"""

    return _default_x509_certificate_algs


def decode_ssh_public_key(data: bytes) -> SSHKey:
    """Decode a packetized SSH public key"""

    try:
        packet = SSHPacket(data)
        alg = packet.get_string()
        handler = _public_key_alg_map.get(alg)

        if handler:
            key_params = handler.decode_ssh_public(packet)
            packet.check_end()

            key = handler.make_public(key_params)
            key.algorithm = alg
            return key
        else:
            raise KeyImportError('Unknown key algorithm: ' +
                                 alg.decode('ascii', errors='replace'))
    except PacketDecodeError:
        raise KeyImportError('Invalid public key') from None


def decode_ssh_certificate(data: bytes,
                           comment: _Comment = None) -> SSHCertificate:
    """Decode a packetized SSH certificate"""

    try:
        packet = SSHPacket(data)
        alg = packet.get_string()
        key_handler, cert_handler = _certificate_alg_map.get(alg, (None, None))

        if cert_handler:
            return cert_handler.construct(packet, alg, key_handler, comment)
        else:
            raise KeyImportError('Unknown certificate algorithm: ' +
                                 alg.decode('ascii', errors='replace'))
    except (PacketDecodeError, ValueError):
        raise KeyImportError('Invalid OpenSSH certificate') from None


def generate_private_key(alg_name: str, comment: _Comment = None,
                         **kwargs) -> SSHKey:
    """Generate a new private key

       This function generates a new private key of a type matching
       the requested SSH algorithm. Depending on the algorithm, additional
       parameters can be passed which affect the generated key.

       Available algorithms include:

           ssh-dss, ssh-rsa, ecdsa-sha2-nistp256, ecdsa-sha2-nistp384,
           ecdsa-sha2-nistp521, ecdsa-sha2-1.3.132.0.10, ssh-ed25519,
           ssh-ed448, sk-ecdsa-sha2-nistp256\\@openssh.com,
           sk-ssh-ed25519\\@openssh.com

       For dss keys, no parameters are supported. The key size is fixed at
       1024 bits due to the use of SHA1 signatures.

       For rsa keys, the key size can be specified using the `key_size`
       parameter, and the RSA public exponent can be changed using the
       `exponent` parameter. By default, generated keys are 2048 bits
       with a public exponent of 65537.

       For ecdsa keys, the curve to use is part of the SSH algorithm name
       and that determines the key size. No other parameters are supported.

       For ed25519 and ed448 keys, no parameters are supported. The key size
       is fixed by the algorithms at 256 bits and 448 bits, respectively.

       For sk keys, the application name to associate with the generated
       key can be specified using the `application` parameter. It defaults
       to `'ssh:'`. The user name to associate with the generated key can
       be specified using the `user` parameter. It defaults to `'AsyncSSH'`.

       When generating an sk key, a PIN can be provided via the `pin`
       parameter if the security key requires it.

       The `resident` parameter can be set to `True` to request that a
       resident key be created on the security key. This allows the key
       handle and public key information to later be retrieved so that
       the generated key can be used without having to store any
       information on the client system. It defaults to `False`.

       You can enable or disable the security key touch requirement by
       setting the `touch_required` parameter. It defaults to `True`,
       requiring that the user confirm their presence by touching the
       security key each time they use it to authenticate.

       :param alg_name:
           The SSH algorithm name corresponding to the desired type of key.
       :param comment: (optional)
           A comment to associate with this key.
       :param key_size: (optional)
           The key size in bits for RSA keys.
       :param exponent: (optional)
           The public exponent for RSA keys.
       :param application: (optional)
           The application name to associate with the generated SK key,
           defaulting to `'ssh:'`.
       :param user: (optional)
           The user name to associate with the generated SK key, defaulting
           to `'AsyncSSH'`.
       :param pin: (optional)
           The PIN to use to access the security key, defaulting to `None`.
       :param resident: (optional)
           Whether or not to create a resident key on the security key,
           defaulting to `False`.
       :param touch_required: (optional)
           Whether or not to require the user to touch the security key
           when authenticating with it, defaulting to `True`.
       :type alg_name: `str`
       :type comment: `str`, `bytes`, or `None`
       :type key_size: `int`
       :type exponent: `int`
       :type application: `str`
       :type user: `str`
       :type pin: `str`
       :type resident: `bool`
       :type touch_required: `bool`

       :returns: An :class:`SSHKey` private key

       :raises: :exc:`KeyGenerationError` if the requested key parameters
                are unsupported
    """

    algorithm = alg_name.encode('utf-8')
    handler = _public_key_alg_map.get(algorithm)

    if handler:
        try:
            key = handler.generate(algorithm, **kwargs)
        except (TypeError, ValueError) as exc:
            raise KeyGenerationError(str(exc)) from None
    else:
        raise KeyGenerationError('Unknown algorithm: ' + alg_name)

    key.set_comment(comment)
    return key

def import_private_key(
        data: BytesOrStr, passphrase: Optional[BytesOrStr] = None,
        unsafe_skip_rsa_key_validation: Optional[bool] = None) -> SSHKey:
    """Import a private key

       This function imports a private key encoded in PKCS#1 or PKCS#8 DER
       or PEM format or OpenSSH format. Encrypted private keys can be
       imported by specifying the passphrase needed to decrypt them.

       :param data:
           The data to import.
       :param passphrase: (optional)
           The passphrase to use to decrypt the key.
       :param unsafe_skip_rsa_key_validation: (optional)
           Whether or not to skip key validation when loading RSA private
           keys, defaulting to performing these checks unless changed by
           calling :func:`set_default_skip_rsa_key_validation`.
       :type data: `bytes` or ASCII `str`
       :type passphrase: `str` or `bytes`
       :type unsafe_skip_rsa_key_validation: bool

       :returns: An :class:`SSHKey` private key

    """

    if isinstance(data, str):
        try:
            data = data.encode('ascii')
        except UnicodeEncodeError:
            raise KeyImportError('Invalid encoding for key') from None

    key, _ = _decode_private(data, passphrase, unsafe_skip_rsa_key_validation)

    if key:
        return key
    else:
        raise KeyImportError('Invalid private key')


def import_private_key_and_certs(
        data: bytes, passphrase: Optional[BytesOrStr] = None,
        unsafe_skip_rsa_key_validation: Optional[bool] = None) -> \
            Tuple[SSHKey, Optional[SSHX509CertificateChain]]:
    """Import a private key and optional certificate chain"""

    key, end = _decode_private(data, passphrase,
                               unsafe_skip_rsa_key_validation)

    if key:
        return key, import_certificate_chain(data[end:])
    else:
        raise KeyImportError('Invalid private key')


def import_public_key(data: BytesOrStr) -> SSHKey:
    """Import a public key

       This function imports a public key encoded in OpenSSH, RFC4716, or
       PKCS#1 or PKCS#8 DER or PEM format.

       :param data:
           The data to import.
       :type data: `bytes` or ASCII `str`

       :returns: An :class:`SSHKey` public key

    """

    if isinstance(data, str):
        try:
            data = data.encode('ascii')
        except UnicodeEncodeError:
            raise KeyImportError('Invalid encoding for key') from None

    key, _ = _decode_public(data)

    if key:
        return key
    else:
        raise KeyImportError('Invalid public key')


def import_certificate(data: BytesOrStr) -> SSHCertificate:
    """Import a certificate

       This function imports an SSH certificate in DER, PEM, OpenSSH, or
       RFC4716 format.

       :param data:
           The data to import.
       :type data: `bytes` or ASCII `str`

       :returns: An :class:`SSHCertificate` object

    """

    if isinstance(data, str):
        try:
            data = data.encode('ascii')
        except UnicodeEncodeError:
            raise KeyImportError('Invalid encoding for key') from None

    cert, _ = _decode_certificate(data)

    if cert:
        return cert
    else:
        raise KeyImportError('Invalid certificate')


def import_certificate_chain(data: bytes) -> Optional[SSHX509CertificateChain]:
    """Import an X.509 certificate chain"""

    certs = _decode_certificate_list(data)

    chain: Optional[SSHX509CertificateChain]

    if certs:
        chain = SSHX509CertificateChain.construct_from_certs(certs)
    else:
        chain = None

    return chain


def import_certificate_subject(data: str) -> str:
    """Import an X.509 certificate subject name"""

    try:
        algorithm, data = data.strip().split(None, 1)
    except ValueError:
        raise KeyImportError('Missing certificate subject algorithm') from None

    if algorithm.startswith('x509v3-'):
        match = _subject_pattern.match(data)

        if match:
            return data[match.end():]

    raise KeyImportError('Invalid certificate subject')


def read_private_key(
        filename: FilePath, passphrase: Optional[BytesOrStr] = None,
        unsafe_skip_rsa_key_validation: Optional[bool] = None) -> SSHKey:
    """Read a private key from a file

       This function reads a private key from a file. See the function
       :func:`import_private_key` for information about the formats
       supported.

       :param filename:
           The file to read the key from.
       :param passphrase: (optional)
           The passphrase to use to decrypt the key.
       :param unsafe_skip_rsa_key_validation: (optional)
           Whether or not to skip key validation when loading RSA private
           keys, defaulting to performing these checks unless changed by
           calling :func:`set_default_skip_rsa_key_validation`.
       :type filename: :class:`PurePath <pathlib.PurePath>` or `str`
       :type passphrase: `str` or `bytes`
       :type unsafe_skip_rsa_key_validation: bool

       :returns: An :class:`SSHKey` private key

    """

    key = import_private_key(read_file(filename), passphrase,
                             unsafe_skip_rsa_key_validation)

    key.set_filename(filename)

    return key


def read_private_key_and_certs(
        filename: FilePath, passphrase: Optional[BytesOrStr] = None,
        unsafe_skip_rsa_key_validation: Optional[bool] = None) -> \
            Tuple[SSHKey, Optional[SSHX509CertificateChain]]:
    """Read a private key and optional certificate chain from a file"""

    key, cert = import_private_key_and_certs(read_file(filename), passphrase,
                                             unsafe_skip_rsa_key_validation)

    key.set_filename(filename)

    return key, cert


def read_public_key(filename: FilePath) -> SSHKey:
    """Read a public key from a file

       This function reads a public key from a file. See the function
       :func:`import_public_key` for information about the formats
       supported.

       :param filename:
           The file to read the key from.
       :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

       :returns: An :class:`SSHKey` public key

    """

    key = import_public_key(read_file(filename))

    key.set_filename(filename)

    return key


def read_certificate(filename: FilePath) -> SSHCertificate:
    """Read a certificate from a file

       This function reads an SSH certificate from a file. See the
       function :func:`import_certificate` for information about the
       formats supported.

       :param filename:
           The file to read the certificate from.
       :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

       :returns: An :class:`SSHCertificate` object

    """

    return import_certificate(read_file(filename))


def read_private_key_list(
        filename: FilePath, passphrase: Optional[BytesOrStr] = None,
        unsafe_skip_rsa_key_validation: Optional[bool] = None) -> \
            Sequence[SSHKey]:
    """Read a list of private keys from a file

       This function reads a list of private keys from a file. See the
       function :func:`import_private_key` for information about the
       formats supported. If any of the keys are encrypted, they must
       all be encrypted with the same passphrase.

       :param filename:
           The file to read the keys from.
       :param passphrase: (optional)
           The passphrase to use to decrypt the keys.
       :param unsafe_skip_rsa_key_validation: (optional)
           Whether or not to skip key validation when loading RSA private
           keys, defaulting to performing these checks unless changed by
           calling :func:`set_default_skip_rsa_key_validation`.
       :type filename: :class:`PurePath <pathlib.PurePath>` or `str`
       :type passphrase: `str` or `bytes`
       :type unsafe_skip_rsa_key_validation: bool

       :returns: A list of :class:`SSHKey` private keys

    """

    keys = _decode_private_list(read_file(filename), passphrase,
                                unsafe_skip_rsa_key_validation)

    for key in keys:
        key.set_filename(filename)

    return keys


def read_public_key_list(filename: FilePath) -> Sequence[SSHKey]:
    """Read a list of public keys from a file

       This function reads a list of public keys from a file. See the
       function :func:`import_public_key` for information about the
       formats supported.

       :param filename:
           The file to read the keys from.
       :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

       :returns: A list of :class:`SSHKey` public keys

    """

    keys = _decode_public_list(read_file(filename))

    for key in keys:
        key.set_filename(filename)

    return keys


def read_certificate_list(filename: FilePath) -> Sequence[SSHCertificate]:
    """Read a list of certificates from a file

       This function reads a list of SSH certificates from a file. See
       the function :func:`import_certificate` for information about
       the formats supported.

       :param filename:
           The file to read the certificates from.
       :type filename: :class:`PurePath <pathlib.PurePath>` or `str`

       :returns: A list of :class:`SSHCertificate` certificates

    """

    return _decode_certificate_list(read_file(filename))


def load_keypairs(
        keylist: KeyPairListArg, passphrase: Optional[BytesOrStr] = None,
        certlist: CertListArg = (), skip_public: bool = False,
        ignore_encrypted: bool = False,
        unsafe_skip_rsa_key_validation: Optional[bool] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None) -> \
            Sequence[SSHKeyPair]:
    """Load SSH private keys and optional matching certificates

       This function loads a list of SSH keys and optional matching
       certificates.

       When certificates are specified, the private key is added to
       the list both with and without the certificate.

       :param keylist:
           The list of private keys and certificates to load.
       :param passphrase: (optional)
           The passphrase to use to decrypt the keys, or a `callable` which
           takes a filename and returns the passphrase to decrypt it.
       :param certlist: (optional)
           A list of certificates to attempt to pair with the provided
           list of private keys.
       :param skip_public: (optional)
           An internal parameter used to skip public keys and certificates
           when IdentitiesOnly and IdentityFile are used to specify a
           mixture of private and public keys.
       :param unsafe_skip_rsa_key_validation: (optional)
           Whether or not to skip key validation when loading RSA private
           keys, defaulting to performing these checks unless changed by
           calling :func:`set_default_skip_rsa_key_validation`.
       :type keylist: *see* :ref:`SpecifyingPrivateKeys`
       :type passphrase: `str` or `bytes`
       :type certlist: *see* :ref:`SpecifyingCertificates`
       :type skip_public: `bool`
       :type unsafe_skip_rsa_key_validation: bool

       :returns: A list of :class:`SSHKeyPair` objects

    """

    keys_to_load: Sequence[_KeyPairArg]
    result: List[SSHKeyPair] = []

    certlist = load_certificates(certlist)
    certdict = {cert.key.public_data: cert for cert in certlist}

    if isinstance(keylist, (PurePath, str)):
        try:
            if callable(passphrase):
                resolved_passphrase = passphrase(str(keylist))
            else:
                resolved_passphrase = passphrase

            if loop and inspect.isawaitable(resolved_passphrase):
                resolved_passphrase = asyncio.run_coroutine_threadsafe(
                    resolved_passphrase, loop).result()

            priv_keys = read_private_key_list(keylist, resolved_passphrase,
                                              unsafe_skip_rsa_key_validation)

            if len(priv_keys) <= 1:
                keys_to_load = [keylist]
                passphrase = resolved_passphrase
            else:
                keys_to_load = priv_keys
        except KeyImportError:
            keys_to_load = [keylist]
    elif isinstance(keylist, (tuple, bytes, SSHKey, SSHKeyPair)):
        keys_to_load = [cast(_KeyPairArg, keylist)]
    else:
        keys_to_load = keylist if keylist else []

    for key_to_load in keys_to_load:
        allow_certs = False
        key_prefix = None
        saved_exc = None
        pubkey_or_certs = None
        pubkey_to_load: Optional[_KeyArg] = None
        certs_to_load: Optional[_CertArg] = None
        key: Union['SSHKey', 'SSHKeyPair']

        if isinstance(key_to_load, (PurePath, str, bytes)):
            allow_certs = True
        elif isinstance(key_to_load, tuple):
            key_to_load, pubkey_or_certs = key_to_load

        try:
            if isinstance(key_to_load, (PurePath, str)):
                key_prefix = str(key_to_load)

                if callable(passphrase):
                    resolved_passphrase = passphrase(key_prefix)
                else:
                    resolved_passphrase = passphrase

                if loop and inspect.isawaitable(resolved_passphrase):
                    resolved_passphrase = asyncio.run_coroutine_threadsafe(
                        resolved_passphrase, loop).result()

                if allow_certs:
                    key, certs_to_load = read_private_key_and_certs(
                        key_to_load, resolved_passphrase,
                        unsafe_skip_rsa_key_validation)

                    if not certs_to_load:
                        certs_to_load = key_prefix + '-cert.pub'
                else:
                    key = read_private_key(key_to_load, resolved_passphrase,
                                           unsafe_skip_rsa_key_validation)

                pubkey_to_load = key_prefix + '.pub'
            elif isinstance(key_to_load, bytes):
                if allow_certs:
                    key, certs_to_load = import_private_key_and_certs(
                        key_to_load, passphrase,
                        unsafe_skip_rsa_key_validation)
                else:
                    key = import_private_key(key_to_load, passphrase,
                                             unsafe_skip_rsa_key_validation)
            else:
                key = key_to_load
        except KeyImportError as exc:
            if skip_public or \
                    (ignore_encrypted and str(exc).startswith('Passphrase')):
                continue

            raise

        certs: Optional[Sequence[SSHCertificate]]

        if pubkey_or_certs:
            try:
                certs = load_certificates(pubkey_or_certs)
            except (TypeError, OSError, KeyImportError) as exc:
                saved_exc = exc
                certs = None

            if not certs:
                pubkey_to_load = cast(_KeyArg, pubkey_or_certs)
        elif certs_to_load:
            try:
                certs = load_certificates(certs_to_load)
            except (OSError, KeyImportError):
                certs = None
        else:
            certs = None

        pubkey: Optional[SSHKey]

        if pubkey_to_load:
            try:
                if isinstance(pubkey_to_load, (PurePath, str)):
                    pubkey = read_public_key(pubkey_to_load)
                elif isinstance(pubkey_to_load, bytes):
                    pubkey = import_public_key(pubkey_to_load)
                else:
                    pubkey = pubkey_to_load
            except (OSError, KeyImportError):
                pubkey = None
            else:
                saved_exc = None
        else:
            pubkey = None

        if saved_exc:
            raise saved_exc # pylint: disable=raising-bad-type

        if not certs:
            if isinstance(key, SSHKeyPair):
                pubdata = key.key_public_data
            else:
                pubdata = key.public_data

            cert = certdict.get(pubdata)

            if cert and cert.is_x509:
                cert = SSHX509CertificateChain.construct_from_certs(certlist)
        elif len(certs) == 1 and not certs[0].is_x509:
            cert = certs[0]
        else:
            cert = SSHX509CertificateChain.construct_from_certs(certs)

        if isinstance(key, SSHKeyPair):
            if cert:
                key.set_certificate(cert)

            result.append(key)
        else:
            if cert:
                result.append(SSHLocalKeyPair(key, pubkey, cert))

            result.append(SSHLocalKeyPair(key, pubkey))

    return result


def load_default_keypairs(passphrase: Optional[BytesOrStr] = None,
                          certlist: CertListArg = ()) -> \
        Sequence[SSHKeyPair]:
    """Return a list of default keys from the user's home directory"""

    result: List[SSHKeyPair] = []

    for file, condition in _DEFAULT_KEY_FILES:
        if condition: # pragma: no branch
            try:
                path = Path('~', '.ssh', file).expanduser()
                result.extend(load_keypairs(path, passphrase, certlist,
                                            ignore_encrypted=True))
            except OSError:
                pass

    return result


def load_public_keys(keylist: KeyListArg) -> Sequence[SSHKey]:
    """Load public keys

       This function loads a list of SSH public keys.

       :param keylist:
           The list of public keys to load.
       :type keylist: *see* :ref:`SpecifyingPublicKeys`

       :returns: A list of :class:`SSHKey` objects

    """

    if isinstance(keylist, (PurePath, str)):
        return read_public_key_list(keylist)
    else:
        result: List[SSHKey] = []

        for key in keylist:
            if isinstance(key, (PurePath, str)):
                key = read_public_key(key)
            elif isinstance(key, bytes):
                key = import_public_key(key)

            result.append(key)

        return result


def load_default_host_public_keys() -> Sequence[Union[SSHKey, SSHCertificate]]:
    """Return a list of default host public keys or certificates"""

    result: List[Union[SSHKey, SSHCertificate]] = []

    for host_key_dir in _DEFAULT_HOST_KEY_DIRS:
        for file in _DEFAULT_HOST_KEY_FILES:
            try:
                cert = read_certificate(Path(host_key_dir, file + '-cert.pub'))
            except (OSError, KeyImportError):
                pass
            else:
                result.append(cert)

    for host_key_dir in _DEFAULT_HOST_KEY_DIRS:
        for file in _DEFAULT_HOST_KEY_FILES:
            try:
                key = read_public_key(Path(host_key_dir, file + '.pub'))
            except (OSError, KeyImportError):
                pass
            else:
                result.append(key)

    return result


def load_certificates(certlist: CertListArg) -> Sequence[SSHCertificate]:
    """Load certificates

       This function loads a list of OpenSSH or X.509 certificates.

       :param certlist:
           The list of certificates to load.
       :type certlist: *see* :ref:`SpecifyingCertificates`

       :returns: A list of :class:`SSHCertificate` objects

    """

    if isinstance(certlist, SSHCertificate):
        return [certlist]
    elif isinstance(certlist, (PurePath, str, bytes)):
        certlist = [certlist]

    result: List[SSHCertificate] = []

    for cert in certlist:
        if isinstance(cert, (PurePath, str)):
            certs = read_certificate_list(cert)
        elif isinstance(cert, bytes):
            certs = _decode_certificate_list(cert)
        elif isinstance(cert, SSHCertificate):
            certs = [cert]
        else:
            certs = cert

        result.extend(certs)

    return result


def load_identities(keylist: IdentityListArg,
                    skip_private: bool = False) -> Sequence[bytes]:
    """Load public key and certificate identities"""

    if isinstance(keylist, (bytes, str, PurePath, SSHKey, SSHCertificate)):
        identities: Sequence[_IdentityArg] = [keylist]
    else:
        identities = keylist

    result = []

    for identity in identities:
        if isinstance(identity, (PurePath, str)):
            try:
                pubdata = read_certificate(identity).public_data
            except KeyImportError:
                try:
                    pubdata = read_public_key(identity).public_data
                except KeyImportError:
                    if skip_private:
                        continue

                    raise
        elif isinstance(identity, (SSHKey, SSHCertificate)):
            pubdata = identity.public_data
        else:
            pubdata = identity

        result.append(pubdata)

    return result


def load_default_identities() -> Sequence[bytes]:
    """Return a list of default public key and certificate identities"""

    result: List[bytes] = []

    for file, condition in _DEFAULT_KEY_FILES:
        if condition: # pragma: no branch
            try:
                cert = read_certificate(Path('~', '.ssh', file + '-cert.pub'))
            except (OSError, KeyImportError):
                pass
            else:
                result.append(cert.public_data)

            try:
                key = read_public_key(Path('~', '.ssh', file + '.pub'))
            except (OSError, KeyImportError):
                pass
            else:
                result.append(key.public_data)

    return result


def load_resident_keys(pin: str, *, application: str = 'ssh:',
                       user: Optional[str] = None,
                       touch_required: bool = True) -> Sequence[SSHKey]:
    """Load keys resident on attached FIDO2 security keys

       This function loads keys resident on any FIDO2 security keys
       currently attached to the system. The user name associated
       with each key is returned in the key's comment field.

       :param pin:
           The PIN to use to access the security keys, defaulting to `None`.
       :param application: (optional)
           The application name associated with the keys to load,
           defaulting to `'ssh:'`.
       :param user: (optional)
           The user name associated with the keys to load. By default,
           keys for all users are loaded.
       :param touch_required: (optional)
           Whether or not to require the user to touch the security key
           when authenticating with it, defaulting to `True`.
       :type application: `str`
       :type user: `str`
       :type pin: `str`
       :type touch_required: `bool`

    """

    flags = SSH_SK_USER_PRESENCE_REQD if touch_required else 0
    reserved = b''

    try:
        resident_keys = sk_get_resident(application, user, pin)
    except ValueError as exc:
        raise KeyImportError(str(exc)) from None

    result: List[SSHKey] = []

    for sk_alg, name, public_value, key_handle in resident_keys:
        handler, key_params = _sk_alg_map[sk_alg]
        key_params += (public_value, application, flags, key_handle, reserved)

        key = handler.make_private(key_params)
        key.set_comment(name)

        result.append(key)

    return result
