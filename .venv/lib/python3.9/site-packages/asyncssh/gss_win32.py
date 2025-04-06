# Copyright (c) 2017-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""GSSAPI wrapper for Windows"""

# Some of the imports below won't be found when running pylint on UNIX
# pylint: disable=import-error

from typing import Optional, Sequence, Union

from sspi import ClientAuth, ServerAuth
from sspi import error as SSPIError

from sspicon import ISC_REQ_DELEGATE, ISC_REQ_INTEGRITY, ISC_REQ_MUTUAL_AUTH
from sspicon import ISC_RET_INTEGRITY, ISC_RET_MUTUAL_AUTH
from sspicon import ASC_REQ_INTEGRITY, ASC_REQ_MUTUAL_AUTH
from sspicon import ASC_RET_INTEGRITY, ASC_RET_MUTUAL_AUTH
from sspicon import SECPKG_ATTR_NATIVE_NAMES

from .asn1 import ObjectIdentifier, der_encode
from .misc import BytesOrStrDict


_krb5_oid = der_encode(ObjectIdentifier('1.2.840.113554.1.2.2'))


class GSSBase:
    """GSS base class"""

    # Overridden in child classes
    _mutual_auth_flag = 0
    _integrity_flag = 0

    def __init__(self, host: str):
        if '@' in host:
            self._host = host
        else:
            self._host = 'host/' + host

        self._ctx: Optional[Union[ClientAuth, ServerAuth]] = None
        self._init_token: Optional[bytes] = None

    @property
    def mechs(self) -> Sequence[bytes]:
        """Return GSS mechanisms available for this host"""

        return [_krb5_oid]

    @property
    def complete(self) -> bool:
        """Return whether or not GSS negotiation is complete"""

        assert self._ctx is not None

        return self._ctx.authenticated

    @property
    def provides_mutual_auth(self) -> bool:
        """Return whether or not this context provides mutual authentication"""

        assert self._ctx is not None

        return bool(self._ctx.ctxt_attr & self._mutual_auth_flag)

    @property
    def provides_integrity(self) -> bool:
        """Return whether or not this context provides integrity protection"""

        assert self._ctx is not None

        return bool(self._ctx.ctxt_attr & self._integrity_flag)

    @property
    def user(self) -> str:
        """Return user principal associated with this context"""

        assert self._ctx is not None

        names = self._ctx.ctxt.QueryContextAttributes(SECPKG_ATTR_NATIVE_NAMES)
        return names[0]

    @property
    def host(self) -> str:
        """Return host principal associated with this context"""

        assert self._ctx is not None

        names = self._ctx.ctxt.QueryContextAttributes(SECPKG_ATTR_NATIVE_NAMES)
        return names[1]

    def reset(self) -> None:
        """Reset GSS security context"""

        assert self._ctx is not None

        self._ctx.reset()
        self._init_token = None

    def step(self, token: Optional[bytes] = None) -> Optional[bytes]:
        """Perform next step in GSS security exchange"""

        assert self._ctx is not None

        if self._init_token:
            token = self._init_token
            self._init_token = None
            return token

        try:
            _, buf = self._ctx.authorize(token)
            return buf[0].Buffer
        except SSPIError as exc:
            raise GSSError(details=exc.strerror) from None

    def sign(self, data: bytes) -> bytes:
        """Sign a block of data"""

        assert self._ctx is not None

        try:
            return self._ctx.sign(data)
        except SSPIError as exc: # pragna: no cover
            raise GSSError(details=exc.strerror) from None

    def verify(self, data: bytes, sig: bytes) -> bool:
        """Verify a signature for a block of data"""

        assert self._ctx is not None

        try:
            self._ctx.verify(data, sig)
            return True
        except SSPIError:
            return False


class GSSClient(GSSBase):
    """GSS client"""

    _mutual_auth_flag = ISC_RET_MUTUAL_AUTH
    _integrity_flag = ISC_RET_INTEGRITY

    def __init__(self, host: str, store: Optional[BytesOrStrDict],
                 delegate_creds: bool):
        if store is not None: # pragna: no cover
            raise GSSError(details='GSS store not supported on Windows')

        super().__init__(host)

        flags = ISC_REQ_MUTUAL_AUTH | ISC_REQ_INTEGRITY

        if delegate_creds:
            flags |= ISC_REQ_DELEGATE

        try:
            self._ctx = ClientAuth('Kerberos', targetspn=self._host,
                                   scflags=flags)
        except SSPIError as exc: # pragna: no cover
            raise GSSError(1, 1, details=exc.strerror) from None

        self._init_token = self.step(None)


class GSSServer(GSSBase):
    """GSS server"""

    _mutual_auth_flag = ASC_RET_MUTUAL_AUTH
    _integrity_flag = ASC_RET_INTEGRITY

    def __init__(self, host: str, store: Optional[BytesOrStrDict]):
        if store is not None: # pragna: no cover
            raise GSSError(details='GSS store not supported on Windows')

        super().__init__(host)

        flags = ASC_REQ_MUTUAL_AUTH | ASC_REQ_INTEGRITY

        try:
            self._ctx = ServerAuth('Kerberos', spn=self._host, scflags=flags)
        except SSPIError as exc:
            raise GSSError(1, 1, details=exc.strerror) from None


class GSSError(Exception):
    """Class for reporting GSS errors"""

    def __init__(self, maj_code: int = 0, min_code: int = 0,
                 token: Optional[bytes] = None, details: str = ''):
        super().__init__(details)

        self.maj_code = maj_code
        self.min_code = min_code
        self.token = token
