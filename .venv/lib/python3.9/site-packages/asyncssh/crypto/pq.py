# Copyright (c) 2022-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""A shim around liboqs for Streamlined NTRU Prime post-quantum encryption"""

import ctypes
import ctypes.util
from typing import Mapping, Tuple


_pq_algs: Mapping[bytes, Tuple[int, int, int, int, str]] = {
    b'mlkem768':  (1184, 2400, 1088, 32, 'KEM_ml_kem_768'),
    b'mlkem1024': (1568, 3168, 1568, 32, 'KEM_ml_kem_1024'),
    b'sntrup761': (1158, 1763, 1039, 32, 'KEM_ntruprime_sntrup761')
}

mlkem_available = False
sntrup_available = False

for lib in ('oqs', 'liboqs'):
    _oqs_lib = ctypes.util.find_library(lib)

    if _oqs_lib: # pragma: no branch
        break
else: # pragma: no cover
    _oqs_lib = None

if _oqs_lib: # pragma: no branch
    _oqs = ctypes.cdll.LoadLibrary(_oqs_lib)

    mlkem_available = (hasattr(_oqs, 'OQS_KEM_ml_kem_768_keypair') or
                       hasattr(_oqs, 'OQS_KEM_ml_kem_768_ipd_keypair'))
    sntrup_available = hasattr(_oqs, 'OQS_KEM_ntruprime_sntrup761_keypair')


class PQDH:
    """A shim around liboqs for post-quantum key exchange algorithms"""

    def __init__(self, alg_name: bytes):
        try:
            self.pubkey_bytes, self.privkey_bytes, \
            self.ciphertext_bytes, self.secret_bytes, \
            oqs_name = _pq_algs[alg_name]
        except KeyError: # pragma: no cover, other algs not registered
            raise ValueError(f'Unknown PQ algorithm {oqs_name}') from None

        if not hasattr(_oqs, 'OQS_' + oqs_name + '_keypair'): # pragma: no cover
            oqs_name += '_ipd'

        self._keypair = getattr(_oqs, 'OQS_' + oqs_name + '_keypair')
        self._encaps = getattr(_oqs, 'OQS_' + oqs_name + '_encaps')
        self._decaps = getattr(_oqs, 'OQS_' + oqs_name + '_decaps')

    def keypair(self) -> Tuple[bytes, bytes]:
        """Make a new key pair"""

        pubkey = ctypes.create_string_buffer(self.pubkey_bytes)
        privkey = ctypes.create_string_buffer(self.privkey_bytes)
        self._keypair(pubkey, privkey)

        return pubkey.raw, privkey.raw

    def encaps(self, pubkey: bytes) -> Tuple[bytes, bytes]:
        """Generate a random secret and encrypt it with a public key"""

        if len(pubkey) != self.pubkey_bytes:
            raise ValueError('Invalid public key')

        ciphertext = ctypes.create_string_buffer(self.ciphertext_bytes)
        secret = ctypes.create_string_buffer(self.secret_bytes)

        self._encaps(ciphertext, secret, pubkey)

        return secret.raw, ciphertext.raw

    def decaps(self, ciphertext: bytes, privkey: bytes) -> bytes:
        """Decrypt an encrypted secret using a private key"""

        if len(ciphertext) != self.ciphertext_bytes:
            raise ValueError('Invalid ciphertext')

        secret = ctypes.create_string_buffer(self.secret_bytes)

        self._decaps(secret, ciphertext, privkey)

        return secret.raw
