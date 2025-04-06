# Copyright (c) 2013-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH compression handlers"""

from typing import Callable, List, Optional
import zlib

_cmp_algs: List[bytes] = []
_default_cmp_algs: List[bytes] = []

_cmp_params = {}

_cmp_compressors = {}
_cmp_decompressors = {}


class Compressor:
    """Base class for data compressor"""

    def compress(self, data: bytes) -> Optional[bytes]:
        """Compress data"""

        raise NotImplementedError


class Decompressor:
    """Base class for data decompressor"""

    def decompress(self, data: bytes) -> Optional[bytes]:
        """Decompress data"""

        raise NotImplementedError


_CompressorType = Callable[[], Optional[Compressor]]
_DecompressorType = Callable[[], Optional[Decompressor]]


def _none() -> None:
    """Compressor/decompressor for no compression"""

    return None


class _ZLibCompress(Compressor):
    """Wrapper class to force a sync flush and handle exceptions"""

    def __init__(self) -> None:
        self._comp = zlib.compressobj()

    def compress(self, data: bytes) -> Optional[bytes]:
        """Compress data using zlib compression with sync flush"""

        try:
            return self._comp.compress(data) + \
                   self._comp.flush(zlib.Z_SYNC_FLUSH)
        except zlib.error: # pragma: no cover
            return None


class _ZLibDecompress(Decompressor):
    """Wrapper class to handle exceptions"""

    def __init__(self) -> None:
        self._decomp = zlib.decompressobj()

    def decompress(self, data: bytes) -> Optional[bytes]:
        """Decompress data using zlib compression"""

        try:
            return self._decomp.decompress(data)
        except zlib.error: # pragma: no cover
            return None


def register_compression_alg(alg: bytes, compressor: _CompressorType,
                             decompressor: _DecompressorType,
                             after_auth: bool, default: bool) -> None:
    """Register a compression algorithm"""

    _cmp_algs.append(alg)

    if default:
        _default_cmp_algs.append(alg)

    _cmp_params[alg] = after_auth

    _cmp_compressors[alg] = compressor
    _cmp_decompressors[alg] = decompressor


def get_compression_algs() -> List[bytes]:
    """Return supported compression algorithms"""

    return _cmp_algs


def get_default_compression_algs() -> List[bytes]:
    """Return default compression algorithms"""

    return _default_cmp_algs


def get_compression_params(alg: bytes) -> bool:
    """Get parameters of a compression algorithm

       This function returns whether or not a compression algorithm should
       be delayed until after authentication completes.

    """

    return _cmp_params[alg]


def get_compressor(alg: bytes) -> Optional[Compressor]:
    """Return an instance of a compressor

       This function returns an object that can be used for data compression.

    """

    return _cmp_compressors[alg]()


def get_decompressor(alg: bytes) -> Optional[Decompressor]:
    """Return an instance of a decompressor

       This function returns an object that can be used for data decompression.

    """

    return _cmp_decompressors[alg]()

register_compression_alg(b'none',
                         _none,         _none,           False, True)
register_compression_alg(b'zlib@openssh.com',
                         _ZLibCompress, _ZLibDecompress, True,  True)
register_compression_alg(b'zlib',
                         _ZLibCompress, _ZLibDecompress, False, False)
