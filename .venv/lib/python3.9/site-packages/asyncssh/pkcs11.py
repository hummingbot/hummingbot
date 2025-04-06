# Copyright (c) 2020-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""PKCS#11 smart card handler"""

from types import TracebackType
from typing import Dict, List, Optional, Sequence, Tuple, Type, Union, cast

try:
    import pkcs11
    from pkcs11 import Attribute, KeyType, Mechanism, ObjectClass
    from pkcs11 import PrivateKey, Token
    from pkcs11.util.rsa import encode_rsa_public_key
    from pkcs11.util.ec import encode_ec_public_key
    pkcs11_available = True
except (ImportError, ModuleNotFoundError): # pragma: no cover
    pkcs11_available = False

from .misc import BytesOrStr
from .packet import MPInt, String
from .public_key import SSHCertificate, SSHKey, SSHKeyPair
from .public_key import import_certificate_chain, import_public_key


_AttrDict = Dict['Attribute', Union[bool, bytes, str, 'ObjectClass']]
_TokenID = Tuple[str, bytes]
_SessionMap = Dict[_TokenID, 'SSHPKCS11Session']


if pkcs11_available:
    encoders = {KeyType.RSA: encode_rsa_public_key,
                KeyType.EC:  encode_ec_public_key}

    mechanisms = {b'ssh-rsa':                Mechanism.SHA1_RSA_PKCS,
                  b'rsa-sha2-256':           Mechanism.SHA256_RSA_PKCS,
                  b'rsa-sha2-512':           Mechanism.SHA512_RSA_PKCS,
                  b'ssh-rsa-sha224@ssh.com': Mechanism.SHA224_RSA_PKCS,
                  b'ssh-rsa-sha256@ssh.com': Mechanism.SHA256_RSA_PKCS,
                  b'ssh-rsa-sha384@ssh.com': Mechanism.SHA384_RSA_PKCS,
                  b'ssh-rsa-sha512@ssh.com': Mechanism.SHA512_RSA_PKCS,
                  b'rsa1024-sha1':           Mechanism.SHA1_RSA_PKCS,
                  b'rsa2048-sha256':         Mechanism.SHA256_RSA_PKCS,
                  b'ecdsa-sha2-nistp256':    Mechanism.ECDSA_SHA256,
                  b'ecdsa-sha2-nistp384':    Mechanism.ECDSA_SHA384,
                  b'ecdsa-sha2-nistp521':    Mechanism.ECDSA_SHA512}


    class SSHPKCS11KeyPair(SSHKeyPair):
        """Surrogate for a key accessed via a PKCS#11 provider"""

        _key_type = 'pkcs11'

        def __init__(self, session: 'SSHPKCS11Session', privkey: PrivateKey,
                     pubkey: SSHKey, cert: Optional[SSHCertificate] = None):
            super().__init__(pubkey.algorithm, pubkey.algorithm,
                             pubkey.sig_algorithms, pubkey.sig_algorithms,
                             pubkey.public_data, privkey.label, cert,
                             use_executor=True)

            self._session = session
            self._privkey = privkey

        def __del__(self) -> None:
            self._session.close()

        def sign(self, data: bytes) -> bytes:
            """Sign a block of data with this private key"""

            sig_algorithm = self.sig_algorithm

            if sig_algorithm.startswith(b'x509v3-'):
                sig_algorithm = sig_algorithm[7:]

            sig = self._privkey.sign(data, mechanism=mechanisms[sig_algorithm])

            if self._privkey.key_type == KeyType.EC:
                length = len(sig) // 2
                r = int.from_bytes(sig[:length], 'big')
                s = int.from_bytes(sig[length:], 'big')
                sig = MPInt(r) + MPInt(s)

            return String(sig_algorithm) + String(sig)


    class SSHPKCS11Session:
        """Work around PKCS#11 sessions not supporting simultaneous opens"""

        _sessions: _SessionMap = {}

        def __init__(self, token_id: _TokenID, token: Token,
                     pin: Optional[str]):
            self._token_id = token_id
            self._session = token.open(user_pin=pin)
            self._refcount = 0

        def __enter__(self) -> 'SSHPKCS11Session':
            """Allow SSHPKCS11Session to be used as a context manager"""

            return self

        def __exit__(self, _exc_type: Type[BaseException],
                     _exc_value: BaseException,
                     _traceback: TracebackType) -> None:
            """Drop one reference to the session when exiting"""

            self.close()

        @classmethod
        def open(cls, token: Token, pin: Optional[str]) -> 'SSHPKCS11Session':
            """Open a new session, or return an already-open one"""

            token_id = (token.manufacturer_id, token.serial)

            try:
                session = cls._sessions[token_id]
            except KeyError:
                session = cls(token_id, token, pin)
                cls._sessions[token_id] = session

            session._refcount += 1
            return session

        def close(self) -> None:
            """Drop one reference to an open session"""

            self._refcount -= 1

            if self._refcount == 0:
                self._session.close()
                del self._sessions[self._token_id]

        def get_keys(self, load_certs: bool, key_label: Optional[str],
                     key_id: Optional[BytesOrStr]) -> \
                Sequence[SSHPKCS11KeyPair]:
            """Return the private keys found on this token"""

            if isinstance(key_id, str):
                key_id = bytes.fromhex(key_id)

            key_attrs: _AttrDict = {Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                                    Attribute.SIGN: True}

            if key_label is not None:
                key_attrs[Attribute.LABEL] = key_label

            if key_id is not None:
                key_attrs[Attribute.OBJECT_ID] = key_id

            cert_attrs: _AttrDict = {Attribute.CLASS: ObjectClass.CERTIFICATE}

            if load_certs:
                certs = [import_certificate_chain(
                         cast(bytes, cert[Attribute.VALUE]))
                         for cert in self._session.get_objects(cert_attrs)]

                certdict = {cert.key.public_data: cert for cert in certs
                            if cert and 'Attest' not in str(cert.subject)}
            else:
                certdict = {}

            keys = []

            for key in self._session.get_objects(key_attrs):
                privkey = cast(PrivateKey, key)
                encoder = encoders.get(privkey.key_type)

                if encoder:
                    pubkey = import_public_key(encoder(privkey))

                    cert = certdict.get(pubkey.public_data)

                    if cert:
                        keys.append(SSHPKCS11KeyPair(self, privkey,
                                                     pubkey, cert))

                    keys.append(SSHPKCS11KeyPair(self, privkey, pubkey))

            self._refcount += len(keys)

            return keys


    def load_pkcs11_keys(provider: str, pin: Optional[str] = None, *,
                         load_certs: bool = True,
                         token_label: Optional[str] = None,
                         token_serial: Optional[BytesOrStr] = None,
                         key_label: Optional[str] = None,
                         key_id: Optional[BytesOrStr] = None) -> \
            Sequence[SSHPKCS11KeyPair]:
        """Load PIV keys and X.509 certificates from a PKCS#11 token

           This function loads a list of SSH keypairs with optional X.509
           cerificates from attached PKCS#11 security tokens. The PKCS#11
           provider must be specified, along with a user PIN if the
           tokens are set to require one.

           By default, this function loads both private key handles
           and the X.509 certificates associated with them, allowing for
           X.509 certificate based auth to SSH servers that support it.
           To disable loading of these certificates and perform only
           key-based authentication, load_certs may be set to `False`.

           If token_label and/or token_serial are specified, only tokens
           matching those values will be accessed.

           If key_label and/or key_id are specified, only keys matching
           those values will be loaded. Key IDs can be specified as
           either raw bytes or a string containing hex digits.

               .. note:: If you have an active asyncio event loop at
                         the time you call this function, you may want
                         to consider running it via a call to
                         :meth:`asyncio.AbstractEventLoop.run_in_executor`.
                         While retrieving the keys generally takes only a
                         fraction of a second, calling this function
                         directly could block asyncio event processing
                         until it completes.

           :param provider:
               The path to the PKCS#11 provider's shared library.
           :param pin: (optional)
               The PIN to use when accessing tokens, if needed.
           :param load_certs: (optional)
               Whether or not to load X.509 certificates from the
               security tokens.
           :param token_label: (optional)
               A token label to match against. If set, only security
               tokens with this label will be accessed.
           :param token_serial: (optional)
               A token serial number to match against. If set, only
               security tokens with this serial number  will be accessed.
           :param key_label: (optional)
               A key label to match against. If set, only keys with this
               label will be loaded.
           :param key_id: (optional)
               A key ID to match against. If set, only keys with this ID
               will be loaded.
           :type provider: `str`
           :type pin: `str`
           :type load_certs: `bool`
           :type token_label: `str`
           :type token_serial: `bytes` or `str`
           :type key_label: `str`
           :type key_id: `bytes` or `str`

           :returns: list of class:`SSHKeyPair`

        """

        lib = pkcs11.lib(provider)

        keys: List[SSHPKCS11KeyPair] = []

        if isinstance(token_serial, str):
            token_serial = token_serial.encode('utf-8')

        for token in lib.get_tokens(token_label=token_label,
                                    token_serial=token_serial):
            with SSHPKCS11Session.open(token, pin) as session:
                keys.extend(session.get_keys(load_certs, key_label, key_id))

        return keys
else: # pragma: no cover
    def load_pkcs11_keys(provider: str, pin: Optional[str] = None, *,
                         load_certs: bool = True,
                         token_label: Optional[str] = None,
                         token_serial: Optional[BytesOrStr] = None,
                         key_label: Optional[str] = None,
                         key_id: Optional[BytesOrStr] = None) -> \
            Sequence['SSHPKCS11KeyPair']:
        """Report that PKCS#11 support is not available"""

        raise ValueError('PKCS#11 support not available') from None
