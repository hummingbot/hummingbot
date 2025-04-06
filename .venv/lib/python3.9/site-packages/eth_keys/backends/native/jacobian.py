from typing import (
    Tuple,
)

from eth_keys.constants import (
    IDENTITY_POINTS,
    SECPK1_A as A,
    SECPK1_N as N,
    SECPK1_P as P,
)


def inv(a: int, n: int) -> int:
    if a == 0:
        return 0
    lm, hm = 1, 0
    low, high = a % n, n
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % n


def to_jacobian(p: Tuple[int, int]) -> Tuple[int, int, int]:
    o = (p[0], p[1], 1)
    return o


def jacobian_double(p: Tuple[int, int, int]) -> Tuple[int, int, int]:
    if not p[1]:
        return (0, 0, 0)
    ysq = (p[1] ** 2) % P
    S = (4 * p[0] * ysq) % P
    M = (3 * p[0] ** 2 + A * p[2] ** 4) % P
    nx = (M**2 - 2 * S) % P
    ny = (M * (S - nx) - 8 * ysq**2) % P
    nz = (2 * p[1] * p[2]) % P
    return (nx, ny, nz)


def jacobian_add(
    p: Tuple[int, int, int], q: Tuple[int, int, int]
) -> Tuple[int, int, int]:
    if not p[1]:
        return q
    if not q[1]:
        return p
    U1 = (p[0] * q[2] ** 2) % P
    U2 = (q[0] * p[2] ** 2) % P
    S1 = (p[1] * q[2] ** 3) % P
    S2 = (q[1] * p[2] ** 3) % P
    if U1 == U2:
        if S1 != S2:
            return (0, 0, 1)
        return jacobian_double(p)
    H = U2 - U1
    R = S2 - S1
    H2 = (H * H) % P
    H3 = (H * H2) % P
    U1H2 = (U1 * H2) % P
    nx = (R**2 - H3 - 2 * U1H2) % P
    ny = (R * (U1H2 - nx) - S1 * H3) % P
    nz = (H * p[2] * q[2]) % P
    return (nx, ny, nz)


def from_jacobian(p: Tuple[int, int, int]) -> Tuple[int, int]:
    z = inv(p[2], P)
    return ((p[0] * z**2) % P, (p[1] * z**3) % P)


def jacobian_multiply(a: Tuple[int, int, int], n: int) -> Tuple[int, int, int]:
    if a[1] == 0 or n == 0:
        return (0, 0, 1)
    if n == 1:
        return a
    if n < 0 or n >= N:
        return jacobian_multiply(a, n % N)
    if (n % 2) == 0:
        return jacobian_double(jacobian_multiply(a, n // 2))
    elif (n % 2) == 1:
        return jacobian_add(jacobian_double(jacobian_multiply(a, n // 2)), a)
    else:
        raise Exception("Invariant: Unreachable code path")


def fast_multiply(a: Tuple[int, int], n: int) -> Tuple[int, int]:
    return from_jacobian(jacobian_multiply(to_jacobian(a), n))


def fast_add(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    return from_jacobian(jacobian_add(to_jacobian(a), to_jacobian(b)))


def is_identity(p: Tuple[int, int, int]) -> bool:
    return p in IDENTITY_POINTS
