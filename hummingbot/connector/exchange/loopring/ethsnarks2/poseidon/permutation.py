#!/usr/bin/env python

"""
Implements the Poseidon permutation:

Starkad and Poseidon: New Hash Functions for Zero Knowledge Proof Systems
 - Lorenzo Grassi, Daniel Kales, Dmitry Khovratovich, Arnab Roy, Christian Rechberger, and Markus Schofnegger
 - https://eprint.iacr.org/2019/458.pdf

Other implementations:

 - https://github.com/shamatar/PoseidonTree/
 - https://github.com/iden3/circomlib/blob/master/src/poseidon.js
 - https://github.com/dusk-network/poseidon252
"""

from math import log2, floor
from collections import namedtuple
from pyblake2 import blake2b
from ..field import SNARK_SCALAR_FIELD


PoseidonParamsType = namedtuple('_PoseidonParams', ('p', 't', 'nRoundsF', 'nRoundsP', 'seed', 'e', 'constants_C', 'constants_M'))


def poseidon_params(p, t, nRoundsF, nRoundsP, seed, e, constants_C=None, constants_M=None, security_target=None):
    assert nRoundsF % 2 == 0 and nRoundsF > 0
    assert nRoundsP > 0
    assert t >= 2
    assert isinstance(seed, bytes)    

    n = floor(log2(p))
    if security_target is None:
        M = n  # security target, in bits
    else:
        M = security_target
    assert n >= M

    # Size of the state (in bits)
    N = n * t

    if p % 2 == 3:        
        assert e == 3
        grobner_attack_ratio_rounds = 0.32
        grobner_attack_ratio_sboxes = 0.18
        interpolation_attack_ratio = 0.63
    elif p % 5 != 1:
        assert e == 5
        grobner_attack_ratio_rounds = 0.21
        grobner_attack_ratio_sboxes = 0.14
        interpolation_attack_ratio = 0.43
    else:
        # XXX: in other cases use, can we use 7?
        raise ValueError('Invalid p for congruency')

    # Verify that the parameter choice exceeds the recommendations to prevent attacks
    # iacr.org/2019/458 § 3 Cryptanalysis Summary of Starkad and Poseidon Hashes (pg 10)
    # Figure 1
    #print('(nRoundsF + nRoundsP)', (nRoundsF + nRoundsP))
    #print('Interpolation Attackable Rounds', ((interpolation_attack_ratio * min(n, M)) + log2(t)))
    assert (nRoundsF + nRoundsP) > ((interpolation_attack_ratio * min(n, M)) + log2(t))
    # Figure 3
    #print('grobner_attack_ratio_rounds', ((2 + min(M, n)) * grobner_attack_ratio_rounds))
    assert (nRoundsF + nRoundsP) > ((2 + min(M, n)) * grobner_attack_ratio_rounds)
    # Figure 4
    #print('grobner_attack_ratio_sboxes', (M * grobner_attack_ratio_sboxes))
    assert (nRoundsF + (t * nRoundsP)) > (M * grobner_attack_ratio_sboxes)

    # iacr.org/2019/458 § 4.1 Minimize "Number of S-Boxes"
    # In order to minimize the number of S-boxes for given `n` and `t`, the goal is to and
    # the best ratio between RP and RF that minimizes:
    #   number of S-Boxes = t · RF + RP
    # - Use S-box x^q
    # - Select R_F to 6 or rhigher
    # - Select R_P that minimizes tRF +RP such that no inequation (1),(3),(4),(5) is satisfied.

    if constants_C is None:
        constants_C = list(poseidon_constants(p, seed + b'_constants', nRoundsF + nRoundsP))
    if constants_M is None:
        constants_M = poseidon_matrix(p, seed + b'_matrix_0000', t)

    # iacr.org/2019/458 § 4.1 6 SNARKs Application via Poseidon-π
    # page 16 formula (8) and (9)
    n_constraints = (nRoundsF * t) + nRoundsP
    if e == 5:
        n_constraints *= 3
    elif e == 3:
        n_constraints *= 2
    #print('n_constraints', n_constraints)

    return PoseidonParamsType(p, t, nRoundsF, nRoundsP, seed, e, constants_C, constants_M)


def H(arg):
    if isinstance(arg, int):
        arg = arg.to_bytes(32, 'little')
    # XXX: ensure that (digest_size*8) >= log2(p)
    hashed = blake2b(data=arg, digest_size=32).digest()
    return int.from_bytes(hashed, 'little')


def poseidon_constants(p, seed, n):
    assert isinstance(n, int)
    for _ in range(n):
        seed = H(seed)
        yield seed % p


def poseidon_matrix(p, seed, t):
    """
    iacr.org/2019/458 § 2.3 About the MDS Matrix (pg 8)
    Also:
     - https://en.wikipedia.org/wiki/Cauchy_matrix     
    """
    c = list(poseidon_constants(p, seed, t * 2))
    return [[pow((c[i] - c[t+j]) % p, p - 2, p) for j in range(t)]
            for i in range(t)]


DefaultParams = poseidon_params(SNARK_SCALAR_FIELD, 6, 8, 57, b'poseidon', 5, security_target=126)


def poseidon_sbox(state, i, params):
    """
    iacr.org/2019/458 § 2.2 The Hades Strategy (pg 6)

    In more details, assume R_F = 2 · R_f is an even number. Then
     - the first R_f rounds have a full S-Box layer,
     - the middle R_P rounds have a partial S-Box layer (i.e., 1 S-Box layer),
     - the last R_f rounds have a full S-Box layer
    """
    half_F = params.nRoundsF // 2
    e, p = params.e, params.p
    if i < half_F or i >= (half_F + params.nRoundsP):
        for j, _ in enumerate(state):
            state[j] = pow(_, e, p)
    else:
        state[0] = pow(state[0], e, p)


def poseidon_mix(state, M, p):
    """
    The mixing layer is a matrix vector product of the state with the mixing matrix
     - https://mathinsight.org/matrix_vector_multiplication
    """
    return [ sum([M[i][j] * _ for j, _ in enumerate(state)]) % p 
             for i in range(len(M)) ]


def poseidon(inputs, params=None, chained=False, trace=False):
    """
    Main instansiation of the Poseidon permutation

    The state is `t` elements wide, there are `F` full-rounds
    followed by `P` partial rounds, then `F` full rounds again.

        [    ARK    ]    --,
         | | | | | |       |
        [    SBOX   ]       -  Full Round
         | | | | | |       |
        [    MIX    ]    --`


        [    ARK    ]    --,
         | | | | | |       |
        [    SBOX   ]       -  Partial Round
                   |       |   Only 1 element is substituted in partial round
        [    MIX    ]    --`

    There are F+P rounds for the full permutation.

    You can provide `r = N - 2s` bits of input per round, where `s` is the desired
    security level, in most cases this means you can provide `t-1` inputs with
    appropriately chosen parameters. The permutation can be 'chained' together
    to form a sponge construct.
    """
    if params is None:
        params = DefaultParams
    assert isinstance(params, PoseidonParamsType)
    assert len(inputs) > 0
    if not chained:
        # Don't allow inputs to exceed the rate, unless in chained mode
        assert len(inputs) < params.t
    state = [0] * params.t
    state[:len(inputs)] = inputs
    for i, C_i in enumerate(params.constants_C):
        state = [_ + C_i for _ in state]  # ARK(.)
        poseidon_sbox(state, i, params)
        state = poseidon_mix(state, params.constants_M, params.p)
        if trace:
            for j, val in enumerate(state):
                print('%d %d' % (i, j), '=', val)
    if chained:
        # Provide the full state as output in 'chained' mode
        return state
    return state[0]
