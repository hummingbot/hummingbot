# Copyright (c) 2014-2021 by Ron Frederick <ronf@timeheart.net> and others.
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

"""A shim for accessing cryptographic primitives needed by asyncssh"""

from .cipher import BasicCipher, GCMCipher, register_cipher, get_cipher_params

from .dsa import DSAPrivateKey, DSAPublicKey

from .dh import DH

from .ec import ECDSAPrivateKey, ECDSAPublicKey, ECDH

from .ed import ed25519_available, ed448_available
from .ed import curve25519_available, curve448_available
from .ed import EdDSAPrivateKey, EdDSAPublicKey, Curve25519DH, Curve448DH

from .ec_params import lookup_ec_curve_by_params

from .kdf import pbkdf2_hmac

from .misc import CryptoKey, PyCAKey

from .rsa import RSAPrivateKey, RSAPublicKey

from .pq import mlkem_available, sntrup_available, PQDH

# Import chacha20-poly1305 cipher if available
from .chacha import ChachaCipher, chacha_available

# Import umac cryptographic hash if available
try:
    from .umac import umac32, umac64, umac96, umac128
except (ImportError, AttributeError, OSError): # pragma: no cover
    pass

# Import X.509 certificate support if available
try:
    from .x509 import X509Certificate, X509Name, X509NamePattern
    from .x509 import generate_x509_certificate, import_x509_certificate
except (ImportError, AttributeError): # pragma: no cover
    pass

__all__ = [
    'BasicCipher', 'ChachaCipher', 'CryptoKey', 'Curve25519DH', 'Curve448DH',
    'DH', 'DSAPrivateKey', 'DSAPublicKey', 'ECDH', 'ECDSAPrivateKey',
    'ECDSAPublicKey', 'EdDSAPrivateKey', 'EdDSAPublicKey', 'GCMCipher', 'PQDH',
    'PyCAKey', 'RSAPrivateKey', 'RSAPublicKey', 'chacha_available',
    'curve25519_available', 'curve448_available', 'X509Certificate',
    'X509Name', 'X509NamePattern', 'ed25519_available', 'ed448_available',
    'generate_x509_certificate', 'get_cipher_params', 'import_x509_certificate',
    'lookup_ec_curve_by_params', 'mlkem_available', 'pbkdf2_hmac',
    'register_cipher', 'sntrup_available', 'umac32', 'umac64', 'umac96',
    'umac128'
]
