import sys
from typing import Optional, Tuple

from ._libsecp256k1 import ffi

# https://bugs.python.org/issue42965
if sys.version_info >= (3, 9, 2):
    from collections.abc import Callable
else:
    from typing import Callable

Hasher = Optional[Callable[[bytes], bytes]]
Nonce = Tuple[ffi.CData, ffi.CData]
