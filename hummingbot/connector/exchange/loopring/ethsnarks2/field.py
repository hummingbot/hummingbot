# Code copied from https://github.com/ethereum/py_ecc/blob/master/py_ecc/bn128/bn128_curve.py
#
# The MIT License (MIT)
#
# Copyright (c) 2015 Vitalik Buterin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import sys
import bitstring
from math import ceil, log2
from os import urandom
from collections import defaultdict
from .numbertheory import square_root_mod_prime

# python3 compatibility
if sys.version_info.major > 2:
    int_types = (int,)
    long = int
else:
    int_types = (int, long)  # noqa: F821

# Fq is the base field of Jubjub
SNARK_SCALAR_FIELD = 21888242871839275222246405745257275088548364400416034343698204186575808495617
# Fr is the scalar field of Jubjub
FR_ORDER = 21888242871839275222246405745257275088614511777268538073601725287587578984328

# A class for field elements in FQ. Wrap a number in this class,
# and it becomes a field element.
class FQ(object):
    _COUNTS = None

    @classmethod
    def _disable_counting(cls):
        cls._COUNTS = None

    @classmethod
    def _print_counts(cls):
        for k in sorted(cls._COUNTS.keys()):
            print(k, "=", cls._COUNTS[k])
        print()

    @classmethod
    def _count(cls, what):
        if cls._COUNTS is not None:
            cls._COUNTS[what] += 1

    @classmethod
    def _reset_counts(cls):
        cls._COUNTS = defaultdict(int)

    def __init__(self, n, field_modulus=SNARK_SCALAR_FIELD):
        if isinstance(n, self.__class__):
            if n.m != field_modulus:
                raise ValueError("Field modulus mismatch")
            self.m = n.m
            self.n = n.n
        else:
            if not isinstance(n, int_types):
                raise ValueError("Invalid number type: " + str(type(n)))
            if not isinstance(field_modulus, int_types):
                raise ValueError("Invalid modulus type: " + str(type(field_modulus)))
            self.m = field_modulus
            self.n = n % self.m

    def __int__(self):
        return self.n

    def __hash__(self):
        return hash((self.n, self.m))

    def _other_n(self, other):
        if isinstance(other, FQ):
            if other.m != self.m:
                raise RuntimeError("Other field element has different modulus")
            return other.n
        if not isinstance(other, int_types):
            raise RuntimeError("Not a valid value type: " + str(type(other).__name__))
        return other

    def __add__(self, other):
        on = self._other_n(other)
        self._count('add')
        return FQ((self.n + on) % self.m, self.m)

    def __mul__(self, other):
        on = self._other_n(other)
        self._count('mul')
        return FQ((self.n * on) % self.m, self.m)

    def __rmul__(self, other):
        return self * other

    def __radd__(self, other):
        return self + other

    def __pow__(self, e):
        return self.exp(e)

    def __rsub__(self, other):
        on = self._other_n(other)
        self._count('sub')
        return FQ((on - self.n) % self.m, self.m)

    def __sub__(self, other):
        on = self._other_n(other)
        self._count('sub')
        return FQ((self.n - on) % self.m, self.m)

    def to_bytes(self, endian='big'):
        nbits = ceil(log2(self.m))
        nbits += 8 - (nbits % 8)
        nbytes = nbits // 8
        return self.n.to_bytes(nbytes, endian)

    def bits(self):
        # TODO: endian
        nbits = ceil(log2(self.m))
        bits = bin(self.n)[2:][::-1].ljust(nbits, '0')
        return bitstring.BitArray('0b' + bits)

    def inv(self):
        self._count('inv')
        return FQ(pow(self.n, self.m - 2, self.m), self.m)

    def sqrt(self):
        self._count('sqrt')
        return FQ(square_root_mod_prime(self.n, self.m), self.m)

    def exp(self, e):
        e = self._other_n(e)
        self._count('exp')
        return FQ(pow(self.n, e, self.m), self.m)

    def __div__(self, other):
        on = self._other_n(other)
        self._count('inv')
        return FQ((self.n * pow(on, self.m-2, self.m)) % self.m, self.m)

    def __floordiv__(self, other):
        return self.__div__(other)

    def __truediv__(self, other):
        return self.__div__(other)

    def __rdiv__(self, other):
        on = self._other_n(other)
        self._count('inv')
        self._count('mul')
        return FQ((pow(self.n, self.m-2, self.m) * on) % self.m, self.m)

    def __rtruediv__(self, other):
        return self.__rdiv__(other)

    def __eq__(self, other):
        if other == 0.:
            other = 0
        # TODO: verify modulus matches other?
        return self.n == self._other_n(other)

    def __ne__(self, other):
        return not self == other

    def __neg__(self):
        self._count('sub')
        return FQ(-self.n, self.m)

    def __repr__(self):
        return repr(self.n)

    @classmethod
    def random(cls, modulus=SNARK_SCALAR_FIELD):
        if isinstance(modulus, FQ):
            modulus = modulus.m
        nbytes = ceil(ceil(log2(modulus)) / 8) + 1
        rand_n = int.from_bytes(urandom(nbytes), 'little')
        return FQ(rand_n, modulus)

    @classmethod
    def one(self, modulus=SNARK_SCALAR_FIELD):
        if isinstance(modulus, FQ):
            modulus = modulus.m
        return FQ(1, modulus)

    @classmethod
    def zero(self, modulus=SNARK_SCALAR_FIELD):
        if isinstance(modulus, FQ):
            modulus = modulus.m
        return FQ(0, modulus)

class FR(FQ):
    def __init__(self, n, field_modulus=FR_ORDER):
        FQ.__init__(self, n, field_modulus)
