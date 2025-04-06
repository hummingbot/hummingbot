# Copyright (c) 2022 by Ron Frederick <ronf@timeheart.net> and others.
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

"""A shim around PyCA for Diffie Hellman key exchange"""

from cryptography.hazmat.primitives.asymmetric import dh


class DH:
    """A shim around PyCA for Diffie Hellman key exchange"""

    def __init__(self, g: int, p: int):
        self._pn = dh.DHParameterNumbers(p, g)
        self._priv_key = self._pn.parameters().generate_private_key()

    def get_public(self) -> int:
        """Return the public key to send in the handshake"""

        pub_key = self._priv_key.public_key()

        return pub_key.public_numbers().y

    def get_shared(self, peer_public: int) -> int:
        """Return the shared key from the peer's public key"""

        peer_key = dh.DHPublicNumbers(peer_public, self._pn).public_key()
        shared_key = self._priv_key.exchange(peer_key)

        return int.from_bytes(shared_key, 'big')
