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

"""A shim around liboqs for Streamlined NTRU Prime post-quantum encryption"""

import ctypes
import ctypes.util
from typing import Tuple


sntrup761_available = False

sntrup761_pubkey_bytes = 1158
sntrup761_privkey_bytes = 1763
sntrup761_ciphertext_bytes = 1039
sntrup761_secret_bytes = 32


for lib in ('oqs', 'liboqs'):
    _oqs_lib = ctypes.util.find_library(lib)

    if _oqs_lib: # pragma: no branch
        break
else: # pragma: no cover
    _oqs_lib = None

if _oqs_lib: # pragma: no branch
    _oqs = ctypes.cdll.LoadLibrary(_oqs_lib)

    _sntrup761_keypair = _oqs.OQS_KEM_ntruprime_sntrup761_keypair
    _sntrup761_encaps = _oqs.OQS_KEM_ntruprime_sntrup761_encaps
    _sntrup761_decaps = _oqs.OQS_KEM_ntruprime_sntrup761_decaps

    sntrup761_available = True


def sntrup761_keypair() -> Tuple[bytes, bytes]:
    """Make a SNTRUP761 key pair"""

    pubkey = ctypes.create_string_buffer(sntrup761_pubkey_bytes)
    privkey = ctypes.create_string_buffer(sntrup761_privkey_bytes)
    _sntrup761_keypair(pubkey, privkey)

    return pubkey.raw, privkey.raw


def sntrup761_encaps(pubkey: bytes) -> Tuple[bytes, bytes]:
    """Generate a random secret and encrypt it with a public key"""

    if len(pubkey) != sntrup761_pubkey_bytes:
        raise ValueError('Invalid SNTRUP761 public key')

    ciphertext = ctypes.create_string_buffer(sntrup761_ciphertext_bytes)
    secret = ctypes.create_string_buffer(sntrup761_secret_bytes)

    _sntrup761_encaps(ciphertext, secret, pubkey)

    return secret.raw, ciphertext.raw


def sntrup761_decaps(ciphertext: bytes, privkey: bytes) -> bytes:
    """Decrypt an encrypted secret using a private key"""

    if len(ciphertext) != sntrup761_ciphertext_bytes:
        raise ValueError('Invalid SNTRUP761 ciphertext')

    secret = ctypes.create_string_buffer(sntrup761_secret_bytes)

    _sntrup761_decaps(secret, ciphertext, privkey)

    return secret.raw
