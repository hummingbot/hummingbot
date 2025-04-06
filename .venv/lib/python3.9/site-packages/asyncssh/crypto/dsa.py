# Copyright (c) 2014-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""A shim around PyCA for DSA public and private keys"""

from typing import Optional, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import dsa

from .misc import CryptoKey, PyCAKey, hashes


# Short variable names are used here, matching names in the spec
# pylint: disable=invalid-name


class _DSAKey(CryptoKey):
    """Base class for shim around PyCA for DSA keys"""

    def __init__(self, pyca_key: PyCAKey, params: dsa.DSAParameterNumbers,
                 pub: dsa.DSAPublicNumbers,
                 priv: Optional[dsa.DSAPrivateNumbers] = None):
        super().__init__(pyca_key)

        self._params = params
        self._pub = pub
        self._priv = priv

    @property
    def p(self) -> int:
        """Return the DSA public modulus"""

        return self._params.p

    @property
    def q(self) -> int:
        """Return the DSA sub-group order"""

        return self._params.q

    @property
    def g(self) -> int:
        """Return the DSA generator"""

        return self._params.g

    @property
    def y(self) -> int:
        """Return the DSA public value"""

        return self._pub.y

    @property
    def x(self) -> Optional[int]:
        """Return the DSA private value"""

        return self._priv.x if self._priv else None


class DSAPrivateKey(_DSAKey):
    """A shim around PyCA for DSA private keys"""

    @classmethod
    def construct(cls, p: int, q: int, g: int,
                  y: int, x: int) -> 'DSAPrivateKey':
        """Construct a DSA private key"""

        params = dsa.DSAParameterNumbers(p, q, g)
        pub = dsa.DSAPublicNumbers(y, params)
        priv = dsa.DSAPrivateNumbers(x, pub)
        priv_key = priv.private_key()

        return cls(priv_key, params, pub, priv)

    @classmethod
    def generate(cls, key_size: int) -> 'DSAPrivateKey':
        """Generate a new DSA private key"""

        priv_key = dsa.generate_private_key(key_size)
        priv = priv_key.private_numbers()
        pub = priv.public_numbers
        params = pub.parameter_numbers

        return cls(priv_key, params, pub, priv)

    def sign(self, data: bytes, hash_name: str = '') -> bytes:
        """Sign a block of data"""

        priv_key = cast('dsa.DSAPrivateKey', self.pyca_key)
        return priv_key.sign(data, hashes[hash_name]())


class DSAPublicKey(_DSAKey):
    """A shim around PyCA for DSA public keys"""

    @classmethod
    def construct(cls, p: int, q: int, g: int, y: int) -> 'DSAPublicKey':
        """Construct a DSA public key"""

        params = dsa.DSAParameterNumbers(p, q, g)
        pub = dsa.DSAPublicNumbers(y, params)
        pub_key = pub.public_key()

        return cls(pub_key, params, pub)

    def verify(self, data: bytes, sig: bytes, hash_name: str = '') -> bool:
        """Verify the signature on a block of data"""

        try:
            pub_key = cast('dsa.DSAPublicKey', self.pyca_key)
            pub_key.verify(sig, data, hashes[hash_name]())
            return True
        except InvalidSignature:
            return False
