"""Utility for Unicode normalization.

This is a pure Python implementation of the Unicode normalization algorithm,
independent of the Python core Unicode database, and ensuring compliance
with version 16.0 of the Unicode standard (released in September 2024). It has
been rigorously tested using the official Unicode test file, available
at https://www.unicode.org/Public/16.0.0/ucd/NormalizationTest.txt.

For the formal specification of the Unicode normalization algorithm,
see Section 3.11, "Normalization Forms," in the Unicode core specification.

Copyright (c) 2021-2024, Marc Lodewijck
All rights reserved.

This software is distributed under the MIT license.
"""

import sys

if sys.version_info < (3, 6):
    raise SystemExit(f"\n{__package__} requires Python 3.6 or later.")
del sys

__all__ = [
    "NFC",
    "NFD",
    "NFKC",
    "NFKD",
    "normalize",
    "UCD_VERSION",
    "UNICODE_VERSION",
    "__version__",
]

# Unicode standard used to process the data
UNICODE_VERSION = UCD_VERSION = "16.0.0"


from pyunormalize import _version
__version__ = _version.__version__
del _version

from pyunormalize._unicode import _UNICODE_VERSION
if _UNICODE_VERSION != UNICODE_VERSION:
    raise SystemExit(
        f"Unicode version mismatch in {_unicode.__name__} "
        f"(expected {UNICODE_VERSION}, found {_UNICODE_VERSION})."
    )
del _UNICODE_VERSION

from pyunormalize.normalization import *
