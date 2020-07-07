# Copyright (c) 2018 Jordi Baylina
# Copyright (c) 2019 Harry Roberts
# License: LGPL-3.0+
# Based on: https://github.com/iden3/circomlib/blob/master/src/mimc_gencontract.js

import sys
import json
from binascii import hexlify

from ..sha3 import keccak_256
from ..evmasm import *
from ..field import SNARK_SCALAR_FIELD

from .permutation import mimc_constants


def _mimc_opcodes_round(exponent):
    # x = input
    # k = key
    # q = field modulus
    # stack upon entry: x q q k q
    # stack upon exit: r k q
    if exponent == 7:
        return [
            DUP(3),         # k x q q k q
            ADDMOD,         # t=x+k q k q
            DUP(1),         # q t q k q
            DUP(0),         # q q t q k q
            DUP(2),         # t q q t q k q
            DUP(0),         # t t q q t q k q
            MULMOD(),       # a=t^2 q t q k q
            DUP(1),         # q a q t q k q
            DUP(1),         # a q a q t q k q
            DUP(0),         # a a q a q t q k q
            MULMOD,         # b=t^4 a q t q k q
            MULMOD,         # c=t^6 t q k q
            MULMOD          # r=t^7 k q
        ]
    elif exponent == 5:
        return [
            DUP(3),         # k x q q k q
            ADDMOD,         # t=x+k q k q
            DUP(1),         # q t q k q
            DUP(0),         # q q t q k q
            DUP(2),         # t q q t q k q
            DUP(0),         # t t q q t q k q
            MULMOD(),       # a=t^2 q t q k q
            DUP(0),         # a a q t q k q
            MULMOD,         # b=t^4 t q k q
            MULMOD          # r=t^5 k q
        ]


def mimc_contract_opcodes(exponent):
    assert exponent in (5, 7)
    tag = keccak_256(f"MiMCpe{exponent}(uint256,uint256)".encode('ascii')).hexdigest()

    # Ensuring that `exponent ** n_rounds` > SNARK_SCALAR_FIELD
    n_rounds = 110 if exponent == 5 else 91
    constants = mimc_constants(R=n_rounds)

    yield [PUSH(0x44),  # callDataLength
           PUSH(0),     # callDataOffset
           PUSH(0),     # memoryOffset
           CALLDATACOPY,
           PUSH(1<<224),
           PUSH(0),
           MLOAD,
           DIV,
           PUSH(int(tag[:8], 16)),  # function selector
           EQ,
           JMPI('start'),
           INVALID]

    yield [LABEL('start'),
           PUSH(SNARK_SCALAR_FIELD),  # q
           PUSH(0x24),
           MLOAD]           # k q

    yield [
        PUSH(0x04), # 0x04 k q
        MLOAD       # x k q
    ]

    for c_i in constants:
        yield [
            DUP(2),     # q r k q
            DUP(0),     # q q r k q
            DUP(0),     # q q q r k q
            SWAP(3),    # r q q q k q
            PUSH(c_i),  # c r q q q k q
            ADDMOD,     # c+r q q k q
        ]
        yield _mimc_opcodes_round(exponent)

    # add k to result, then return
    yield [
        ADDMOD,         # r+k
        PUSH(0),        # r+k 0
        MSTORE,         #
        PUSH(0x20),     # 0x20
        PUSH(0),        # 0 0x20
        RETURN
    ]


def mimc_abi(exponent):
    assert exponent in (5, 7)
    return [{
        "constant": True,
        "inputs": [
            {
                "name": "in_x",
                "type": "uint256"
            },
            {
                "name": "in_k",
                "type": "uint256"
            }
        ],
        "name": f"MiMCpe{exponent}",
        "outputs": [
            {
                "name": "out_x",
                "type": "uint256"
            }
        ],
        "payable": False,
        "stateMutability": "pure",
        "type": "function"
    }]


def mimc_contract(exponent):
    gen = Codegen()
    for _ in mimc_contract_opcodes(exponent):
        gen.append(_)
    return gen.createTxData()


def main(*args): 
    if len(args) < 3:
        print("Usage: %s <abi|contract> <exponent> [outfile]" % (args[0],))
        return 1

    command = args[1]
    exponent = int(args[2])
    if exponent not in (5, 7):
        print("Error: exponent must be 5 or 7")
        return 2

    outfile = sys.stdout
    if len(args) > 3:
        outfile = open(args[3], 'wb')

    if command == "abi":
        outfile.write(json.dumps(mimc_abi(exponent)) + "\n")
    elif command == "contract":
        data = mimc_contract(exponent)
        if outfile == sys.stdout:            
            data = '0x' + hexlify(data).decode('ascii')
        outfile.write(data)
    else:
        print("Error: unknown command", command)

    if outfile != sys.stdout:
        outfile.close()

    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
