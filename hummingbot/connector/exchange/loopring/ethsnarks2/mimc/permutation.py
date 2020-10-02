# Copyright (c) 2018 HarryR
# License: LGPL-3.0+

from ..sha3 import keccak_256
from ..field import SNARK_SCALAR_FIELD


DEFAULT_EXPONENT = 7
DEFAULT_ROUNDS = 91
DEFAULT_SEED = b'mimc'


def to_bytes(*args):
    for i, _ in enumerate(args):
        if isinstance(_, str):
            yield _.encode('ascii')
        elif not isinstance(_, int) and hasattr(_, 'to_bytes'):
            # for 'F_p' or 'FQ' class etc.
            yield _.to_bytes('big')
        elif isinstance(_, bytes):
            yield _
        else:
            # Try conversion to integer first?
            yield int(_).to_bytes(32, 'big')


def H(*args):
    data = b''.join(to_bytes(*args))
    hashed = keccak_256(data).digest()
    return int.from_bytes(hashed, 'big')

assert H(123) == 38632140595220392354280998614525578145353818029287874088356304829962854601866


def mimc_constants(seed=DEFAULT_SEED, p=SNARK_SCALAR_FIELD, R=DEFAULT_ROUNDS):
    """
    Generate a sequence of round constants

    These can hard-coded into circuits or generated on-demand
    """
    if isinstance(seed, str):
        seed = seed.encode('ascii')
    if isinstance(seed, bytes):
        # pre-hash byte strings before use
        seed = H(seed)
    else:
        seed = int(seed)

    for _ in range(R):
        seed = H(seed)
        yield seed


def mimc(x, k, seed=DEFAULT_SEED, p=SNARK_SCALAR_FIELD, e=DEFAULT_EXPONENT, R=DEFAULT_ROUNDS):
    """
    The MiMC cipher: https://eprint.iacr.org/2016/492

     First round

                x    k
                |    |
                |    |
               (+)---|     X[0] = x + k
                |    |
        C[0] --(+)   |     Y[0] = X[0] + C[0]
                |    |
              (n^7)  |     Z[0] = Y[0]^7
                |    |
    *****************************************
     per-round  |    |
                |    |
               (+)---|     X[i] = Z[i-1] + k
                |    |
        C[i] --(+)   |     Y[i] = X[i] + C[i]
                |    |
              (n^7)  |     Z[i] = Y[i]^7
                |    |
    *****************************************
     Last round
                |    |
               (+)---'     result = Z.back() + k
                |
              result
    """
    assert R > 2
    # TODO: assert gcd(p-1, e) == 1
    for c_i in list(mimc_constants(seed, p, R)):
        a = (x + k + c_i) % p
        x = (a ** e) % p
    return (x + k) % p


def mimc_hash(x, k=0, seed=DEFAULT_SEED, p=SNARK_SCALAR_FIELD, e=DEFAULT_EXPONENT, R=DEFAULT_ROUNDS):
    """
    The Miyaguchi–Preneel single-block-length one-way compression
    function is an extended variant of Matyas–Meyer–Oseas. It was
    independently proposed by Shoji Miyaguchi and Bart Preneel.

    H_i = E_{H_{i-1}}(m_i) + {H_{i-1}} + m_i

    The previous output is used as the key for
    the next iteration.

    or..

                 m_i
                  |
                  |----,
                  |    |
                  v    |
    H_{i-1}--,-->[E]   |
             |    |    |
             `-->(+)<--'
                  |
                  v
                 H_i

    @param x list of inputs
    @param k initial key
    """
    for x_i in x:
        r = mimc(x_i, k, seed, p, e, R)
        k = (k + x_i + r) % p
    return k


def mimc_hash_md(x, k=0, seed=DEFAULT_SEED, p=SNARK_SCALAR_FIELD, e=DEFAULT_EXPONENT, R=DEFAULT_ROUNDS):
    """
    Merkle-Damgard structure, used to turn a cipher into a one-way-compression function

                  m_i
                   |
                   |
                   v
       k_{i-1} -->[E]
                   |
                   |
                   v
                  k_i

    The output is used as the key for the next message
    The last output is used as the result
    """
    for x_i in x:
        k = mimc(x_i, k, seed, p, e, R)
    return k


def _main():
    import argparse
    parser = argparse.ArgumentParser("MiMC")
    parser.add_argument('-r', '--rounds', metavar='N', type=int, default=DEFAULT_ROUNDS, help='number of rounds')
    parser.add_argument('-e', '--exponent', metavar='N', type=int, default=DEFAULT_EXPONENT, help='exponent for round function')
    parser.add_argument('-s', '--seed', type=bytes, default=DEFAULT_SEED, help='seed for round constants')
    parser.add_argument('-k', '--key', type=int, default=0, help='initial key')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='display settings')
    parser.add_argument('cmd', nargs='?', default='test')
    parser.add_argument('subargs', nargs='*')
    args = parser.parse_args()

    exponent = args.exponent
    rounds = args.rounds
    seed = args.seed
    key = int(args.key)
    cmd = args.cmd

    if args.verbose:
        print('# exponent', exponent)
        print('# rounds', rounds)
        print('# seed', seed)
        print('# key', key)

    if cmd == "test":
        # With default parameters, known results
        assert mimc(1, 1) == 2447343676970420247355835473667983267115132689045447905848734383579598297563
        assert mimc_hash([1,1]) == 4087330248547221366577133490880315793780387749595119806283278576811074525767

        # Verify cross-compatibility with EVM/Solidity implementation
        assert mimc(3703141493535563179657531719960160174296085208671919316200479060314459804651,
                    134551314051432487569247388144051420116740427803855572138106146683954151557,
                    b'mimc') == 11437467823393790387399137249441941313717686441929791910070352316474327319704
        assert mimc_hash([3703141493535563179657531719960160174296085208671919316200479060314459804651,
                        134551314051432487569247388144051420116740427803855572138106146683954151557],
                       918403109389145570117360101535982733651217667914747213867238065296420114726,
                       b'mimc') == 15683951496311901749339509118960676303290224812129752890706581988986633412003
        print('OK')
        return 0

    elif cmd == "constants":
        for x in mimc_constants(seed, SNARK_SCALAR_FIELD, rounds):
            print(x % SNARK_SCALAR_FIELD)  # hex(x), x)

    elif cmd == "encrypt":
        for x in args.subargs:
            x = int(x)
            result = mimc(x, key, seed, SNARK_SCALAR_FIELD, exponent, rounds)
            key = mimc(key, key, seed, SNARK_SCALAR_FIELD, exponent, rounds)
            print(result)

    elif cmd == "hash":
        result = mimc_hash([int(x) for x in args.subargs], key, seed, SNARK_SCALAR_FIELD, exponent, rounds)
        print(result)

    else:
        parser.print_help()
        return 1

    return 0
        

if __name__ == "__main__":
    import sys
    sys.exit(_main())
