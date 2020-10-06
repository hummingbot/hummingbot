"""
This module implements the extended twisted edwards and extended affine coordinates
described in the paper "Twisted Edwards Curves Revisited":

 - https://iacr.org/archive/asiacrypt2008/53500329/53500329.pdf
   Huseyin Hisil, Kenneth Koon-Ho Wong, Gary Carter, and Ed Dawson

        Information Security Institute,
        Queensland University of Technology, QLD, 4000, Australia
        {h.hisil, kk.wong, g.carter, e.dawson}@qut.edu.au

By using the extended coordinate system we can avoid expensive modular exponentiation
calls, for example - a scalar multiplication call (or multiple...) may perform only
one 3d->2d projection at the point where affine coordinates are necessary, and every
intermediate uses a much faster form.

# XXX: none of these functions are constant time, they should not be used interactively!
"""

from os import urandom
from hashlib import sha256
from collections import namedtuple

from .field import FQ, SNARK_SCALAR_FIELD
from .numbertheory import SquareRootError


JUBJUB_Q = SNARK_SCALAR_FIELD
JUBJUB_E = 21888242871839275222246405745257275088614511777268538073601725287587578984328    # #E is the order of the curve E
JUBJUB_C = 8        # Cofactor
JUBJUB_L = JUBJUB_E // JUBJUB_C    # L*B = 0, and (2^C)*L == #E
JUBJUB_A = 168700    # Coefficient A
JUBJUB_D = 168696    # Coefficient D


# Verify JUBJUB_A is a non-zero square
try:
    FQ(JUBJUB_A).sqrt()
except SquareRootError:
    raise RuntimeError("JUBJUB_A is required to be a square")

# Verify JUBJUB_D is non-square
try:
    FQ(JUBJUB_D).sqrt()
    raise RuntimeError("JUBJUB_D is required to be non-square")
except SquareRootError:
    pass


"""
From "Twisted Edwards Curves", 2008-BBJLP
Theorem 3.2
"""
MONT_A = 168698    # int(2*(JUBJUB_A+JUBJUB_D)/(JUBJUB_A-JUBJUB_D))
MONT_B = 1        # int(4/(JUBJUB_A-JUBJUB_D))
MONT_A24 = int((MONT_A + 2) / 4)
assert MONT_A24 * 4 == MONT_A + 2


"""
2017-BL - "Montgomery curves and the Montgomery ladder"
- https://eprint.iacr.org/2017/293.pdf
4.3.5, The curve parameters satisfy:
"""
assert JUBJUB_A == (MONT_A + 2) / MONT_B
assert JUBJUB_D == (MONT_A - 2) / MONT_B


def is_negative(v):
    assert isinstance(v, FQ)
    return v.n < (-v).n


class AbstractCurveOps(object):
    def __neg__(self):
        return self.neg()

    def __add__(self, other):
        return self.add(other)

    def __sub__(self, other):
        return self.add(other.neg())

    def __mul__(self, n):
        return self.mult(n)

    def double(self):
        return self.add(self)

    def rescale(self):
        return self

    def compress(self):
        return self.as_point.compress()

    @classmethod
    def all_loworder_points(cls):
        """
        All low-order points
        """
        return [
            Point(FQ(0), FQ(1)),
            Point(FQ(0), FQ(21888242871839275222246405745257275088548364400416034343698204186575808495616)),
            Point(FQ(2957874849018779266517920829765869116077630550401372566248359756137677864698), FQ(0)),
            Point(FQ(4342719913949491028786768530115087822524712248835451589697801404893164183326), FQ(4826523245007015323400664741523384119579596407052839571721035538011798951543)),
            Point(FQ(4342719913949491028786768530115087822524712248835451589697801404893164183326), FQ(17061719626832259898845741003733890968968767993363194771977168648564009544074)),
            Point(FQ(17545522957889784193459637215142187266023652151580582754000402781682644312291), FQ(4826523245007015323400664741523384119579596407052839571721035538011798951543)),
            Point(FQ(17545522957889784193459637215142187266023652151580582754000402781682644312291), FQ(17061719626832259898845741003733890968968767993363194771977168648564009544074)),
            Point(FQ(18930368022820495955728484915491405972470733850014661777449844430438130630919), FQ(0))
        ]

    @classmethod
    def decompress(cls, point):
        return Point.decompress(point).as_proj()

    def is_negative(self):
        """
        The point is negative if the X coordinate is lower than its modulo negative
        """
        return is_negative(self.as_point().x)

    def sign(self):
        return 1 if self.is_negative() else 0

    def mult_wnaf(self, scalar, window=5):
        return mult_naf_lut(self, scalar, window)

    def mult(self, scalar):
        if isinstance(scalar, FQ):
            if scalar.m not in [SNARK_SCALAR_FIELD, JUBJUB_E, JUBJUB_L]:
                raise ValueError("Invalid field modulus")
            scalar = scalar.n
        p = self
        a = self.infinity()
        i = 0
        while scalar != 0:
            if (scalar & 1) != 0:
                a = a.add(p)
            p = p.double()
            scalar = scalar // 2
            i += 1
        return a


class Point(AbstractCurveOps, namedtuple('_Point', ('x', 'y'))):
    def __str__(self):
        return ' '.join([str(_) for _ in self])

    @classmethod
    def from_y(cls, y, sign=None):
        """
        x^2 = (y^2 - 1) / (d * y^2 - a)
        """
        assert isinstance(y, FQ)
        assert y.m == JUBJUB_Q
        ysq = y * y
        lhs = (ysq - 1)
        rhs = (JUBJUB_D * ysq - JUBJUB_A)
        xsq = lhs / rhs
        x = xsq.sqrt()
        if sign is not None:
            # Used for compress & decompress
            if (x.n & 1) != sign:
                x = -x
        else:
            if is_negative(x):
                x = -x
        return cls(x, y)

    @classmethod
    def from_x(cls, x):
        """
        y^2 = ((a * x^2) / (d * x^2 - 1)) - (1 / (d * x^2 - 1))

        For every x coordinate, there are two possible points: (x, y) and (x, -y)
        """
        assert isinstance(x, FQ)
        assert x.m == JUBJUB_Q
        xsq = x * x
        ax2 = JUBJUB_A * xsq
        dxsqm1 = (JUBJUB_D * xsq - 1).inv()
        ysq = dxsqm1 * (ax2 - 1)
        y = ysq.sqrt()
        return cls(x, y)

    @classmethod
    def random(cls):
        return cls.from_hash(urandom(32))

    @classmethod
    def from_hash(cls, entropy):
        """
        HashToPoint (or Point.from_hash)

        Hashes the input entropy and interprets the result as the Y coordinate
        then recovers the X coordinate, if no valid point can be recovered
        Y is incremented until a matching X coordinate is found.

        The point is guaranteed to be prime order and not the identity.

        From: https://datatracker.ietf.org/doc/draft-irtf-cfrg-hash-to-curve/?include_text=1

        Page 6:

           o  HashToBase(x, i).  This method is parametrized by p and H, where p
              is the prime order of the base field Fp, and H is a cryptographic
              hash function which outputs at least floor(log2(p)) + 2 bits.  The
              function first hashes x, converts the result to an integer, and
              reduces modulo p to give an element of Fp.
        """
        assert isinstance(entropy, bytes)
        entropy = sha256(entropy).digest()
        entropy_as_int = int.from_bytes(entropy, 'big')
        y = FQ(entropy_as_int)
        while True:
            try:
                p = cls.from_y(y)
            except SquareRootError:
                y += 1
                continue

            # Multiply point by cofactor, ensures it's on the prime-order subgroup
            p = p * JUBJUB_C

            # Verify point is on prime-ordered sub-group
            if (p * JUBJUB_L) != Point.infinity():
                raise RuntimeError("Point not on prime-ordered subgroup")

            return p

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))

    def compress(self):
        x = self.x.n
        y = self.y.n
        return int.to_bytes(y | ((x & 1) << 255), 32, "little")

    @classmethod
    def decompress(cls, point):
        """
        From: https://ed25519.cr.yp.to/eddsa-20150704.pdf

        The encoding of F_q is used to define "negative" elements of F_q:
        specifically, x is negative if the (b-1)-bit encoding of x is
        lexiographically larger than the (b-1)-bit encoding of -x. In particular,
        if q is prime and the (b-1)-bit encoding of F_q is the little-endian
        encoding of {0, 1, ..., q-1}, then {1,3,5,...,q-2} are the negative element of F_q.

        This encoding is also used to define a b-bit encoding of each element `(x,y) ∈ E`
        as a b-bit string (x,y), namely the (b-1)-bit encoding of y followed by the sign bit.
        the sign bit is 1 if and only if x is negative.

        A parser recovers `(x,y)` from a b-bit string, while also verifying that `(x,y) ∈ E`,
        as follows: parse the first b-1 bits as y, compute `xx = (y^2 - 1) / (dy^2 - a)`;
        compute `x = [+ or -] sqrt(xx)` where the `[+ or -]` is chosen so that the sign of
        `x` matches the `b`th bit of the string. if `xx` is not a square then parsing fails.
        """
        if len(point) != 32:
            raise ValueError("Invalid input length for decompression")
        y = int.from_bytes(point, "little")
        sign = y >> 255
        y &= (1 << 255) - 1
        return cls.from_y(FQ(y), sign)

    def as_mont(self):
        return MontPoint.from_edwards(self)

    def as_proj(self):
        return ProjPoint(self.x, self.y, FQ(1))

    def as_etec(self):
        return EtecPoint(self.x, self.y, self.x * self.y, FQ(1))

    def as_point(self):
        return self

    def neg(self):
        """
        Twisted Edwards Curves, BBJLP-2008, section 2 pg 2
        """
        return Point(-self.x, self.y)

    @classmethod
    def generator(cls):
        x = 16540640123574156134436876038791482806971768689494387082833631921987005038935
        y = 20819045374670962167435360035096875258406992893633759881276124905556507972311
        return Point(FQ(x), FQ(y))

    def valid(self):
        """
        Satisfies the relationship

            ax^2 + y^2 = 1 + d x^2 y^2
        """
        xsq = self.x * self.x
        ysq = self.y * self.y
        return (JUBJUB_A * xsq) + ysq == (1 + JUBJUB_D * xsq * ysq)

    def add(self, other):
        assert isinstance(other, Point)
        if self.x == 0 and self.y == 0:
            return other
        (u1, v1) = (self.x, self.y)
        (u2, v2) = (other.x, other.y)
        u3 = ((u1 * v2) + (v1 * u2)) / (FQ.one() + (JUBJUB_D * u1 * u2 * v1 * v2))
        v3 = ((v1 * v2) - (JUBJUB_A * u1 * u2)) / (FQ.one() - (JUBJUB_D * u1 * u2 * v1 * v2))
        return Point(u3, v3)

    @staticmethod
    def infinity():
        return Point(FQ(0), FQ(1))


class ProjPoint(AbstractCurveOps, namedtuple('_ProjPoint', ('x', 'y', 'z'))):
    def rescale(self):
        return ProjPoint(self.x / self.z, self.y / self.z, FQ(1))

    def as_proj(self):
        return self

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __hash__(self):
        return hash((self.x, self.y, self.z))

    def as_etec(self):
        """
        (X, Y, Z) -> (X, Y, X*Y, Z)
        """
        return EtecPoint(self.x, self.y, self.x * self.y, self.z)

    def as_mont(self):
        return self.as_point().as_mont()

    def as_point(self):
        assert self.z != 0
        inv_z = self.z.inv()
        return Point(self.x * inv_z, self.y * inv_z)

    def valid(self):
        return self.as_point().valid()

    @staticmethod
    def infinity():
        return ProjPoint(FQ(0), FQ(1), FQ(1))

    def neg(self):
        """
        -(X : Y : Z) = (-X : Y : Z)
        """
        return ProjPoint(-self.x, self.y, self.z)

    def add(self, other):
        """
        add-2008-bbjlp
        https:/eprint.iacr.org/2008/013 Section 6
        Strongly unified
        """
        assert isinstance(other, ProjPoint)
        if self == self.infinity():
            return other
        a = self.z * other.z
        b = a * a
        c = self.x * other.x
        d = self.y * other.y
        t0 = c * d
        e = JUBJUB_D * t0
        f = b - e
        g = b + e
        t1 = self.x + self.y
        t2 = other.x + other.y
        t3 = t1 * t2
        t4 = t3 - c
        t5 = t4 - d
        t6 = f * t5
        x3 = a * t6
        t7 = JUBJUB_A * c
        t8 = d - t7
        t9 = g * t8
        y3 = a * t9
        z3 = f * g
        return ProjPoint(x3, y3, z3)

    def double(self):
        """
        dbl-2008-bbjlp https://eprint.iacr.org/2008/013

        From "Twisted Edwards Curves" - BBJLP

        # Doubling in Projective Twisted Coordinates
        > The following formulas compute (X3 : Y3 : Z3) = 2(X1 : Y1 : Z1)
        > in 3M + 4S + 1D + 7add, where the 1D is a multiplication by `a`.
        """
        if self == self.infinity():
            return self.infinity()
        t0 = self.x + self.y
        b = t0 * t0
        c = self.x * self.x
        d = self.y * self.y
        e = JUBJUB_A * c
        f = e + d
        h = self.z * self.z
        t1 = 2 * h
        j = f - t1
        t2 = b - c
        t3 = t2 - d
        x3 = t3 * j
        t4 = e - d
        y3 = f * t4
        z3 = f * j
        return ProjPoint(x3, y3, z3)


class MontPoint(AbstractCurveOps, namedtuple('_MontPoint', ('u', 'v'))):
    @classmethod
    def from_edwards(cls, e):
        """
        The map from a twisted Edwards curve is defined as

            (x, y) -> (u, v) where
                u = (1 + y) / (1 - y)
                v = u / x

        This mapping is not defined for y = 1 and for x = 0.

        We have that y != 1 above. If x = 0, the only
        solutions for y are 1 (contradiction) or -1.

        See: https://github.com/zcash/librustzcash/blob/master/sapling-crypto/src/jubjub/montgomery.rs#L121
        """
        e = e.as_point()
        if e.y == FQ.one():
            # The only solution for y = 1 is x = 0. (0, 1) is
            # the neutral element, so we map this to the point at infinity.
            return MontPoint(FQ.zero(), FQ.one())
        if e.x == FQ.zero():
            return MontPoint(FQ.zero(), FQ.zero())
        u = (FQ.one() + e.y) / (FQ.one() - e.y)
        v = u / e.x
        return cls(u, v)

    def as_point(self):
        """
        See: https://eprint.iacr.org/2008/013.pdf
         - "Twisted Edwards Curves" (BBJLP'08)
         - Theorem 3.2 pg 4

         with inverse
            (u, v) → (x, y) = (u/v, (u − 1)/(u + 1)).
        """
        x = self.u / self.v
        y = (self.u - 1) / (self.u + 1)
        return Point(x, y)

    def as_etec(self):
        return self.as_point().as_etec()

    def as_proj(self):
        return self.as_point().as_proj()

    def valid(self):
        """
        See: https://eprint.iacr.org/2008/013.pdf
         - "Twisted Edwards Curves" (BBJLP'08)

        Definition 3.1 (Montgomery curve). Fix a field k with char(k) 6= 2. Fix
            A ∈ k \\ {−2, 2} and B ∈ k \\ {0}.

        The Montgomery curve with coefficients A and B is the curve

            E_{M,A,B} : B * (v^2) = u^3 + A*(u^2) + u
        """
        lhs = MONT_B * (self.v ** 2)
        rhs = (self.u ** 3) + MONT_A * (self.u ** 2) + self.u
        return lhs == rhs

    def as_mont(self):
        return self

    @classmethod
    def infinity(cls):
        return cls(FQ(0), FQ(1))

    def neg(self):
        return type(self)(self.u, -self.v)

    def __eq__(self, other):
        return self.u == other.u and self.v == other.v

    def __hash__(self):
        return hash((self.u, self.v))

    def double(self):
        # https://github.com/zcash/librustzcash/blob/master/sapling-crypto/src/jubjub/montgomery.rs#L224
        # See §4.3.2 The group law for Weierstrass curves
        #  - Montgomery curves and the Montgomery Ladder
        #  - Daniel J. Bernstein and Tanja Lange
        #  @ https://cr.yp.to/papers/montladder-20170330.pdf
        if self.v == FQ.zero():
            return self.infinity()

        usq = self.u * self.u
        delta = (1 + (2 * (MONT_A * self.u)) + usq + (usq * 2)) / (2 * self.v)
        x3 = (delta * delta) - MONT_A - (2 * self.u)
        y3 = -((x3 - self.u) * delta + self.v)
        return type(self)(x3, y3)

    def add(self, other):
        # https://github.com/zcash/librustzcash/blob/master/sapling-crypto/src/jubjub/montgomery.rs#L288
        other = other.as_mont()
        infinity = self.infinity()
        if other == infinity:
            return self
        elif self == infinity:
            return other

        if self.u == other.u:
            if self.v == other.v:
                return self.double()
            return infinity

        delta = (other.v - self.v) / (other.u - self.u)
        x3 = (delta * delta) - MONT_A - self.u - other.u
        y3 = -((x3 - self.u) * delta + self.v)
        return type(self)(x3, y3)


class EtecPoint(AbstractCurveOps, namedtuple('_EtecPoint', ('x', 'y', 't', 'z'))):
    def as_etec(self):
        return self

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.t == other.t and self.z == other.z

    def __hash__(self):
        return hash((self.x, self.y, self.t, self.z))

    def as_mont(self):
        return self.as_point().as_mont()

    def as_point(self):
        """
        Ignoring the T value, project from 3d X,Y,Z to 2d X,Y coordinates

            (X : Y : T : Z) -> (X/Z, Y/Z)
        """
        inv_z = self.z.inv()
        return Point(self.x * inv_z, self.y * inv_z)

    def as_proj(self):
        """
        The T value is dropped when converting from extended
        twisted edwards to projective edwards coordinates.

            (X : Y : T : Z) -> (X, Y, Z)
        """
        return ProjPoint(self.x, self.y, self.z)

    @staticmethod
    def infinity():
        return EtecPoint(FQ(0), FQ(1), FQ(0), FQ(1))

    def neg(self):
        """
        Twisted Edwards Curves Revisited - HWCD, pg 5, section 3

            -(X : Y : T : Z) = (-X : Y : -T : Z)
        """
        return EtecPoint(-self.x, self.y, -self.t, self.z)

    def valid(self):
        return self.as_point().valid()

    def double(self):
        """
        dbl-2008-hwcd
        """
        if self == self.infinity():
            return self.infinity()
        a = self.x * self.x
        b = self.y * self.y
        t0 = self.z * self.z
        c = t0 * 2
        d = JUBJUB_A * a
        t1 = self.x + self.y
        t2 = t1 * t1
        t3 = t2 - a
        e = t3 - b
        g = d + b
        f = g - c
        h = d - b
        return EtecPoint(e * f, g * h, e * h, f * g)

    def add(self, other):
        """
        3.1 Unified addition in ε^e
        """
        assert isinstance(other, EtecPoint)
        if self == self.infinity():
            return other

        assert self.z != 0
        assert other.z != 0

        x1x2 = self.x * other.x
        y1y2 = self.y * other.y
        dt1t2 = (JUBJUB_D * self.t) * other.t
        z1z2 = self.z * other.z
        e = ((self.x + self.y) * (other.x + other.y)) - x1x2 - y1y2
        f = z1z2 - dt1t2
        g = z1z2 + dt1t2
        h = y1y2 - (JUBJUB_A * x1x2)

        return EtecPoint(e * f, g * h, e * h, f * g)


def wNAF(k, width=2):
    # windowed Non-Adjacent-Form
    # https://bristolcrypto.blogspot.com/2015/04/52-things-number-26-describe-naf-scalar.html
    # https://en.wikipedia.org/wiki/Elliptic_curve_point_multiplication#w-ary_non-adjacent_form_(wNAF)_method
    k = int(k)
    a = 2**width
    b = 2**(width - 1)
    output = []
    while k > 0:
        if (k % 2) == 1:
            c = k % a
            if c > b:
                k_i = c - a
            else:
                k_i = c
            k = k - k_i
        else:
            k_i = 0
        output.append(k_i)
        k = k // 2
    return output[::-1]


def naf_window(point, nbits):
    """
    Return an n-bit window of points for use with w-NAF multiplication
    """
    a = (1 << nbits) // 2
    res = {0: None}
    for n in list(range(0, a))[1:]:
        if n == 1:
            p_n = point
        elif n == 2:
            p_n = point.double()
        elif n > 2 and n % 2 == 0:
            continue
        else:
            p_n = res[n - 2] + res[2]
        res[n] = p_n
        res[-n] = -p_n
    return res


def mult_naf(point, scalar):
    # Multiplication using NAF
    a = point.infinity()
    for k_i in wNAF(scalar):
        a = a.double()
        if k_i == 1:
            a = a.add(point)
        elif k_i == -1:
            a = a.add(point.neg())
    return a


def mult_naf_lut(point, scalar, width=2):
    # Multipication using Windowed NAF, with an arbitrary sized window
    a = point.infinity()
    w = naf_window(point, width)
    for k_i in wNAF(scalar, width):
        a = a.double()
        p = w[k_i]
        if p is not None:
            a = a.add(p)
    return a
