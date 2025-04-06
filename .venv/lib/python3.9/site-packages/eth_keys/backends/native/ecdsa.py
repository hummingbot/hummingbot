"""
Functions lifted from https://github.com/vbuterin/pybitcointools
"""
import hashlib
import hmac
from typing import (
    Any,
    Callable,
    Tuple,
)

from eth_utils import (
    big_endian_to_int,
    int_to_big_endian,
)

from eth_keys.constants import (
    SECPK1_A as A,
    SECPK1_B as B,
    SECPK1_G as G,
    SECPK1_N as N,
    SECPK1_P as P,
    SECPK1_Gx as Gx,
    SECPK1_Gy as Gy,
)
from eth_keys.exceptions import (
    BadSignature,
)
from eth_keys.utils.padding import (
    pad32,
)

from .jacobian import (
    fast_add,
    fast_multiply,
    from_jacobian,
    inv,
    is_identity,
    jacobian_add,
    jacobian_multiply,
)


def decode_public_key(public_key_bytes: bytes) -> Tuple[int, int]:
    left = big_endian_to_int(public_key_bytes[0:32])
    right = big_endian_to_int(public_key_bytes[32:64])
    return left, right


def encode_raw_public_key(raw_public_key: Tuple[int, int]) -> bytes:
    left, right = raw_public_key
    return b"".join(
        (
            pad32(int_to_big_endian(left)),
            pad32(int_to_big_endian(right)),
        )
    )


def private_key_to_public_key(private_key_bytes: bytes) -> bytes:
    private_key_as_num = big_endian_to_int(private_key_bytes)

    if private_key_as_num >= N:
        raise Exception("Invalid privkey")

    raw_public_key = fast_multiply(G, private_key_as_num)
    public_key_bytes = encode_raw_public_key(raw_public_key)
    return public_key_bytes


def compress_public_key(uncompressed_public_key_bytes: bytes) -> bytes:
    x, y = decode_public_key(uncompressed_public_key_bytes)
    if y % 2 == 0:
        prefix = b"\x02"
    else:
        prefix = b"\x03"
    return prefix + pad32(int_to_big_endian(x))


def decompress_public_key(compressed_public_key_bytes: bytes) -> bytes:
    if len(compressed_public_key_bytes) != 33:
        raise ValueError("Invalid compressed public key")

    prefix = compressed_public_key_bytes[0]
    if prefix not in (2, 3):
        raise ValueError("Invalid compressed public key")

    x = big_endian_to_int(compressed_public_key_bytes[1:])
    y_squared = (x**3 + A * x + B) % P
    y_abs = pow(y_squared, ((P + 1) // 4), P)

    if (prefix == 2 and y_abs & 1 == 1) or (prefix == 3 and y_abs & 1 == 0):
        y = (-y_abs) % P
    else:
        y = y_abs

    return encode_raw_public_key((x, y))


def deterministic_generate_k(
    msg_hash: bytes,
    private_key_bytes: bytes,
    digest_fn: Callable[[], Any] = hashlib.sha256,
) -> int:
    v_0 = b"\x01" * 32
    k_0 = b"\x00" * 32

    k_1 = hmac.new(
        k_0, v_0 + b"\x00" + private_key_bytes + msg_hash, digest_fn
    ).digest()
    v_1 = hmac.new(k_1, v_0, digest_fn).digest()
    k_2 = hmac.new(
        k_1, v_1 + b"\x01" + private_key_bytes + msg_hash, digest_fn
    ).digest()
    v_2 = hmac.new(k_2, v_1, digest_fn).digest()

    kb = hmac.new(k_2, v_2, digest_fn).digest()
    k = big_endian_to_int(kb)
    return k


def ecdsa_raw_sign(msg_hash: bytes, private_key_bytes: bytes) -> Tuple[int, int, int]:
    z = big_endian_to_int(msg_hash)
    k = deterministic_generate_k(msg_hash, private_key_bytes)

    r, y = fast_multiply(G, k)
    s_raw = inv(k, N) * (z + r * big_endian_to_int(private_key_bytes)) % N

    v = 27 + ((y % 2) ^ (0 if s_raw * 2 < N else 1))
    s = s_raw if s_raw * 2 < N else N - s_raw

    return v - 27, r, s


def ecdsa_raw_verify(
    msg_hash: bytes, rs: Tuple[int, int], public_key_bytes: bytes
) -> bool:
    raw_public_key = decode_public_key(public_key_bytes)

    r, s = rs

    w = inv(s, N)
    z = big_endian_to_int(msg_hash)

    u1, u2 = z * w % N, r * w % N
    x, y = fast_add(
        fast_multiply(G, u1),
        fast_multiply(raw_public_key, u2),
    )
    return bool(r == x and (r % N) and (s % N))


def ecdsa_raw_recover(msg_hash: bytes, vrs: Tuple[int, int, int]) -> bytes:
    v, r, s = vrs

    if v not in (0, 1):
        raise BadSignature(f"value of v, aka y-parity, was {v}, must be either 0 or 1")

    v += 27
    x = r

    xcubedaxb = (x * x * x + A * x + B) % P
    beta = pow(xcubedaxb, (P + 1) // 4, P)
    y = beta if v % 2 ^ beta % 2 else (P - beta)
    # If xcubedaxb is not a quadratic residue, then r cannot be the x coord
    # for a point on the curve, and so the sig is invalid
    if (xcubedaxb - y * y) % P != 0 or not (r % N) or not (s % N):
        raise BadSignature("Invalid signature")
    z = big_endian_to_int(msg_hash)
    Gz = jacobian_multiply((Gx, Gy, 1), (N - z) % N)
    XY = jacobian_multiply((x, y, 1), s)
    Qr = jacobian_add(Gz, XY)
    Q = jacobian_multiply(Qr, inv(r, N))

    if is_identity(Q):
        raise BadSignature("InvalidSignature")

    raw_public_key = from_jacobian(Q)

    return encode_raw_public_key(raw_public_key)
