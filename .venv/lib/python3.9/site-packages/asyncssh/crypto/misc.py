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

"""Miscellaneous PyCA utility classes and functions"""

from typing import Callable, Mapping, Union

from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.hazmat.primitives.asymmetric import ed25519, ed448
from cryptography.hazmat.primitives.hashes import HashAlgorithm
from cryptography.hazmat.primitives.hashes import MD5, SHA1, SHA224
from cryptography.hazmat.primitives.hashes import SHA256, SHA384, SHA512


PyCAPrivateKey = Union[dsa.DSAPrivateKey, rsa.RSAPrivateKey,
                       ec.EllipticCurvePrivateKey,
                       ed25519.Ed25519PrivateKey, ed448.Ed448PrivateKey]

PyCAPublicKey = Union[dsa.DSAPublicKey, rsa.RSAPublicKey,
                      ec.EllipticCurvePublicKey,
                      ed25519.Ed25519PublicKey, ed448.Ed448PublicKey]

PyCAKey = Union[PyCAPrivateKey, PyCAPublicKey]


hashes: Mapping[str, Callable[[], HashAlgorithm]] = {
    str(h.name): h for h in (MD5, SHA1, SHA224, SHA256, SHA384, SHA512)
}


class CryptoKey:
    """Base class for PyCA private/public keys"""

    def __init__(self, pyca_key: PyCAKey):
        self._pyca_key = pyca_key

    @property
    def pyca_key(self) -> PyCAKey:
        """Return the PyCA object associated with this key"""

        return self._pyca_key

    def sign(self, data: bytes, hash_name: str = '') -> bytes:
        """Sign a block of data"""

        # pylint: disable=no-self-use
        raise RuntimeError # pragma: no cover

    def verify(self, data: bytes, sig: bytes, hash_name: str = '') -> bool:
        """Verify the signature on a block of data"""

        # pylint: disable=no-self-use
        raise RuntimeError # pragma: no cover
