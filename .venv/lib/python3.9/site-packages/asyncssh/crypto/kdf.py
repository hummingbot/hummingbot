# Copyright (c) 2017-2021 by Ron Frederick <ronf@timeheart.net> and others.
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

"""A shim around PyCA for key derivation functions"""

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .misc import hashes


def pbkdf2_hmac(hash_name: str, passphrase: bytes, salt: bytes,
                count: int, key_size: int) -> bytes:
    """A shim around PyCA for PBKDF2 HMAC key derivation"""

    return PBKDF2HMAC(hashes[hash_name](), key_size, salt,
                      count).derive(passphrase)
