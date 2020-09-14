# Copyright (c) 2018 HarryR.
# License: LGPL-3.0+


import json
import ctypes
from functools import reduce
from binascii import unhexlify
from collections import namedtuple

from py_ecc import bn128
from py_ecc.bn128 import pairing, FQ, FQ2, FQ12, neg, multiply, add


_VerifyingKeyStruct = namedtuple('_VerifyingKeyStruct',
    ('alpha', 'beta', 'gamma', 'delta', 'gammaABC'))

_ProofStruct = namedtuple('_ProofStruct',
    ('A', 'B', 'C', 'input'))


class CustomEncoder(json.JSONEncoder):
    """Encodes FQ and FQ2 elements in same format as native library and Ethereum"""
    def default(self, o):
        if isinstance(o, FQ2):
            c0hex = hex(o.coeffs[0].n)
            c1hex = hex(o.coeffs[1].n)
            return [c1hex, c0hex]
        elif isinstance(o, FQ):
            return hex(o.n)
        raise RuntimeError("Unknown type", (type(o), o))


def _bigint_bytes_to_int(x):
    """Convert big-endian bytes to integer"""
    return reduce(lambda o, b: (o << 8) + b if isinstance(b, int) else ord(b), [0] + list(x))


def _filter_int(x):
    """Decode an optionally hex-encoded big-endian string to a integer"""
    if isinstance(x, int):
        return x
    if x[:2] == '0x':
        x = x[2:]
    if len(x) % 2 > 0:
        x = '0' + x
    return _bigint_bytes_to_int(unhexlify(x))


def _load_g1_point(point):
    """Unserialize a G1 point, from Ethereum hex encoded 0x..."""
    if len(point) != 2:
        raise RuntimeError("Invalid G1 point - not 2 vals", point)

    out = tuple(FQ(_filter_int(_)) for _ in point)

    if not bn128.is_on_curve(out, bn128.b):
        raise ValueError("Invalid G1 point - not on curve", out)

    return out


def _load_g2_point(point):
    """Unserialize a G2 point, from Ethereum hex encoded 0x..."""
    x, y = point
    if len(x) != 2 or len(y) != 2:
        raise RuntimeError("Invalid G2 point x or y", point)

    # Points are provided as X.c1, X.c0, Y.c1, Y.c2
    # As in, each component is a 512 bit big-endian number split in two
    out = (FQ2([_filter_int(x[1]), _filter_int(x[0])]),
           FQ2([_filter_int(y[1]), _filter_int(y[0])]))

    if not bn128.is_on_curve(out, bn128.b2):
        raise ValueError("Invalid G2 point - not on curve:", out)

    # TODO: verify G2 point with another algorithm?
    #   neg(G2.one()) * p + p != G2.zero()
    return out


def pairingProd(*inputs):
    """
    The Ethereum pairing opcode works like:

       e(p1[0],p2[0]) * ... * e(p1[n],p2[n]) == 1

    See: EIP 212

    >>> assert True == pairingProd((G1, G2), (G1, neg(G2)))
    """
    product = FQ12.one()
    for p1, p2 in inputs:
        product *= pairing(p2, p1)
    return product == FQ12.one()


class BaseProof(object):
    def to_json(self):
        obj = self._asdict()
        # Note, the inputs must be hex-encoded so they're JSON friendly
        # The Custom JSON encoder doesn't handle them correctly
        for field in self.FP_POINTS:
            obj[field] = [hex(_) for _ in obj[field]]
        return json.dumps(obj, cls=CustomEncoder)

    @classmethod
    def from_json(cls, json_data):
        return cls.from_dict(json.loads(json_data))

    @classmethod
    def from_dict(cls, in_data):
        """
        The G1 points in the proof JSON are affine X,Y,Z coordinates
        Because they're affine we can ignore the Z coordinate

        For G2 points on-chain, they're: X.c1, X.c0, Y.c1, Y.c0, Z.c1, Z.c0

        However, py_ecc is little endian, so it needs [X.c0, X.c1]
        """
        fields = []
        for name in cls._fields:
            val = in_data[name]
            if name in cls.G2_POINTS:
                # See note above about endian conversion
                fields.append(_load_g2_point(val))
            elif name in cls.FP_POINTS:
                fields.append([_filter_int(_) for _ in val])
            elif name in cls.G1_POINTS:
                fields.append(_load_g1_point(val[:2]))
            else:
                raise KeyError("Unknown proof field: " + name)
        return cls(*fields)


class Proof(_ProofStruct, BaseProof):
    G1_POINTS = ['A', 'C']
    G2_POINTS = ['B']
    FP_POINTS = ['input']


class BaseVerifier(object):
    def to_json(self):
        return json.dumps(self._asdict(), cls=CustomEncoder)

    @classmethod
    def from_json(cls, json_data):
        return cls.from_dict(json.loads(json_data))

    @classmethod
    def from_file(cls, filename):
        with open(filename, 'r') as handle:
            data = json.load(handle)
            return cls.from_dict(data)

    @classmethod
    def from_dict(cls, in_data):
        """Load verifying key from data dictionary, e.g. 'vk.json'"""
        fields = []
        for name in cls._fields:
            val = in_data[name]
            # Iterate in order, loading G1 or G2 points as necessary
            if name in cls.G1_POINTS:
                fields.append(_load_g1_point(val))
            elif name in cls.G1_LISTS:
                fields.append(list([_load_g1_point(_) for _ in val]))
            elif name in cls.G2_POINTS:
                fields.append(_load_g2_point(val))
            else:
                raise KeyError("Unknown verifying key field: " + name)
        # Order is necessary to pass to constructor of self
        return cls(*fields)


class VerifyingKey(BaseVerifier, _VerifyingKeyStruct):
    G1_POINTS = ['alpha']
    G2_POINTS = ['beta', 'gamma', 'delta']
    G1_LISTS = ['gammaABC']

    def verify(self, proof):
        """Verify if a proof is correct for the given inputs"""
        if not isinstance(proof, Proof):
            raise TypeError("Invalid proof type")

        # Compute the linear combination vk_x
        # vk_x = gammaABC[0] + gammaABC[1]^x[0] + ... + gammaABC[n+1]^x[n]
        vk_x = self.gammaABC[0]
        for i, x in enumerate(proof.input):
            vk_x = add(vk_x, multiply(self.gammaABC[i + 1], x))

        # e(B, A) * e(gamma, -vk_x) * e(delta, -C) * e(beta, -alpha)
        return pairingProd(
            (proof.A, proof.B),
            (neg(vk_x), self.gamma),
            (neg(proof.C), self.delta),
            (neg(self.alpha), self.beta))


class NativeVerifier(VerifyingKey):
    def verify(self, proof, native_library_path):
        if not isinstance(proof, Proof):
            raise TypeError("Invalid proof type")

        vk_cstr = ctypes.c_char_p(self.to_json().encode('ascii'))
        proof_cstr = ctypes.c_char_p(proof.to_json().encode('ascii'))

        lib = ctypes.cdll.LoadLibrary(native_library_path)
        lib_verify = lib.ethsnarks_verify
        lib_verify.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib_verify.restype = ctypes.c_bool

        return lib_verify(vk_cstr, proof_cstr)
