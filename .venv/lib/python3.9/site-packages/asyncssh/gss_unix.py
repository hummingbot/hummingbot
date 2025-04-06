# Copyright (c) 2017-2022 by Ron Frederick <ronf@timeheart.net> and others.
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

"""GSSAPI wrapper for UNIX"""

from typing import Optional, Sequence, SupportsBytes, cast

from gssapi import Credentials, Name, NameType, OID
from gssapi import RequirementFlag, SecurityContext
from gssapi.exceptions import GSSError

from .asn1 import OBJECT_IDENTIFIER
from .misc import BytesOrStrDict


def _mech_to_oid(mech: OID) -> bytes:
    """Return a DER-encoded OID corresponding to the requested GSS mechanism"""

    mech_bytes = bytes(cast(SupportsBytes, mech))
    return bytes((OBJECT_IDENTIFIER, len(mech_bytes))) + mech_bytes


class GSSBase:
    """GSS base class"""

    def __init__(self, host: str, store: Optional[BytesOrStrDict]):
        if '@' in host:
            self._host = Name(host)
        else:
            self._host = Name('host@' + host, NameType.hostbased_service)

        self._store = store

        self._mechs = [_mech_to_oid(mech) for mech in self._creds.mechs]
        self._ctx: Optional[SecurityContext] = None

    @property
    def _creds(self) -> Credentials:
        """Abstract method to construct GSS credentials"""

        raise NotImplementedError

    def _init_context(self) -> None:
        """Abstract method to construct GSS security context"""

        raise NotImplementedError

    @property
    def mechs(self) -> Sequence[bytes]:
        """Return GSS mechanisms available for this host"""

        return self._mechs

    @property
    def complete(self) -> bool:
        """Return whether or not GSS negotiation is complete"""

        return self._ctx.complete if self._ctx else False

    @property
    def provides_mutual_auth(self) -> bool:
        """Return whether or not this context provides mutual authentication"""

        assert self._ctx is not None

        return bool(self._ctx.actual_flags &
                    RequirementFlag.mutual_authentication)

    @property
    def provides_integrity(self) -> bool:
        """Return whether or not this context provides integrity protection"""

        assert self._ctx is not None

        return bool(self._ctx.actual_flags & RequirementFlag.integrity)

    @property
    def user(self) -> str:
        """Return user principal associated with this context"""

        assert self._ctx is not None

        return str(self._ctx.initiator_name)

    @property
    def host(self) -> str:
        """Return host principal associated with this context"""

        assert self._ctx is not None

        return str(self._ctx.target_name)

    def reset(self) -> None:
        """Reset GSS security context"""

        self._ctx = None

    def step(self, token: Optional[bytes] = None) -> Optional[bytes]:
        """Perform next step in GSS security exchange"""

        if not self._ctx:
            self._init_context()

        assert self._ctx is not None

        return self._ctx.step(token)

    def sign(self, data: bytes) -> bytes:
        """Sign a block of data"""

        assert self._ctx is not None

        return self._ctx.get_signature(data)

    def verify(self, data: bytes, sig: bytes) -> bool:
        """Verify a signature for a block of data"""

        assert self._ctx is not None

        try:
            self._ctx.verify_signature(data, sig)
            return True
        except GSSError:
            return False


class GSSClient(GSSBase):
    """GSS client"""

    def __init__(self, host: str, store: Optional[BytesOrStrDict],
                 delegate_creds: bool):
        super().__init__(host, store)

        flags = RequirementFlag.mutual_authentication | \
                RequirementFlag.integrity

        if delegate_creds:
            flags |= RequirementFlag.delegate_to_peer

        self._flags = flags

    @property
    def _creds(self) -> Credentials:
        """Abstract method to construct GSS credentials"""

        return Credentials(usage='initiate', store=self._store)

    def _init_context(self) -> None:
        """Construct GSS client security context"""

        self._ctx = SecurityContext(name=self._host, creds=self._creds,
                                    flags=self._flags)


class GSSServer(GSSBase):
    """GSS server"""

    @property
    def _creds(self) -> Credentials:
        """Abstract method to construct GSS credentials"""

        return Credentials(name=self._host, usage='accept', store=self._store)

    def _init_context(self) -> None:
        """Construct GSS server security context"""

        self._ctx = SecurityContext(creds=self._creds)
