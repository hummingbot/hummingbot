# Copyright (c) 2018 Jordi Baylina
# Copyright (c) 2019 Harry Roberts
# License: LGPL-3.0+


import sys
import json
from binascii import hexlify
from ..evmasm import *
from ..field import SNARK_SCALAR_FIELD
from .permutation import DefaultParams


def _add_round_key(r, t, K):
    """
    function ark(r) {
        C.push(toHex256(K[r])); // K, st, q
        for (let i=0; i<t; i++) {
            C.dup(1+t); // q, K, st, q
            C.dup(1);   // K, q, K, st, q
            C.dup(3+i); // st[i], K, q, K, st, q
            C.addmod(); // newSt[i], K, st, q
            C.swap(2 + i); // xx, K, st, q
            C.pop();
        }
        C.pop();
    }
    """
    middle = [[DUP(1+t),
               DUP(1),
               DUP(3+i),
               ADDMOD,
               SWAP(2+i),
               POP] for i in range(t)]
    return [PUSH(K[r])] + middle + [POP]


def _sigma(p, t):
    """
    function sigma(p) {
        // sq, q
        C.dup(t);   // q, st, q
        C.dup(1+p); // st[p] , q , st, q
        C.dup(1);   // q, st[p] , q , st, q
        C.dup(0);   // q, q, st[p] , q , st, q
        C.dup(2);   // st[p] , q, q, st[p] , q , st, q
        C.dup(0);   // st[p] , st[p] , q, q, st[p] , q , st, q
        C.mulmod(); // st2[p], q, st[p] , q , st, q
        C.dup(0);   // st2[p], st2[p], q, st[p] , q , st, q
        C.mulmod(); // st4[p], st[p] , q , st, q
        C.mulmod(); // st5[p], st, q
        C.swap(1+p);
        C.pop();      // newst, q
    }
    """
    return [
        # sq, q
        DUP(t),         # q, st, q
        DUP(1+p),       # st[p] , q , st, q
        DUP(1),         # q, st[p] , q , st, q
        DUP(0),         # q, q, st[p] , q , st, q
        DUP(2),         # st[p] , q, q, st[p] , q , st, q
        DUP(0),         # st[p] , st[p] , q, q, st[p] , q , st, q
        MULMOD,         # st2[p], q, st[p] , q , st, q
        DUP(0),         # st2[p], st2[p], q, st[p] , q , st, q
        MULMOD,         # st4[p], st[p] , q , st, q
        MULMOD,         # st5[p], st, q
        SWAP(1+p),
        POP             # newst, q
    ]


def _mix(params):
    """
    C.label("mix");
    for (let i=0; i<t; i++) {
        for (let j=0; j<t; j++) {
            if (j==0) {
                C.dup(i+t);      // q, newSt, oldSt, q
                C.push((1+i*t+j)*32);
                C.mload();      // M, q, newSt, oldSt, q
                C.dup(2+i+j);    // oldSt[j], M, q, newSt, oldSt, q
                C.mulmod();      // acc, newSt, oldSt, q
            } else {
                C.dup(1+i+t);    // q, acc, newSt, oldSt, q
                C.push((1+i*t+j)*32);
                C.mload();      // M, q, acc, newSt, oldSt, q
                C.dup(3+i+j);    // oldSt[j], M, q, acc, newSt, oldSt, q
                C.mulmod();      // aux, acc, newSt, oldSt, q
                C.dup(2+i+t);    // q, aux, acc, newSt, oldSt, q
                C.swap(2);       // acc, aux, q, newSt, oldSt, q
                C.addmod();      // acc, newSt, oldSt, q
            }
        }
    }
    for (let i=0; i<t; i++) {
        C.swap((t -i) + (t -i-1));
        C.pop();
    }
    C.push(0);
    C.mload();
    C.jmp();
    """
    yield LABEL("mix")

    t = params.t
    for i in range(t):
        for j in range(t):
            if j == 0:
                yield [
                    DUP(i+t),           # q, newSt, oldSt, q
                    PUSH((1+i*t+j)*32),
                    MLOAD,              # M, q, newSt, oldSt, q
                    DUP(2+i+j),         # oldSt[j], M, q, newSt, oldSt, q
                    MULMOD,             # acc, newSt, oldSt, q
                ]
            else:
                yield [
                    DUP(1+i+t),         # q, acc, newSt, oldSt, q
                    PUSH((1+i*t+j)*32),
                    MLOAD,              # M, q, acc, newSt, oldSt, q
                    DUP(3+i+j),         # oldSt[j], M, q, acc, newSt, oldSt, q
                    MULMOD,             # aux, acc, newSt, oldSt, q
                    DUP(2+i+t),         # q, aux, acc, newSt, oldSt, q
                    SWAP(2),            # acc, aux, q, newSt, oldSt, q
                    ADDMOD              # acc, newSt, oldSt, q
                ]

    for i in range(t):
        yield [SWAP((t - i) + (t - i - 1)), POP]

    yield [PUSH(0), MLOAD, JMP()]


def poseidon_contract_opcodes(params=None):
    if params is None:
        params = DefaultParams

    # Check selector
    """
    C.push("0x0100000000000000000000000000000000000000000000000000000000");
    C.push(0);
    C.calldataload();
    C.div();
    C.push("0xc4420fb4"); // poseidon(uint256[])
    C.eq();
    C.jmpi("start");
    C.invalid();
    C.label("start");
    """    
    yield [
        PUSH(1<<224),
        PUSH(0),
        CALLDATALOAD,
        DIV,
        PUSH(0xc4420fb4),  # poseidon(uint256[])
        EQ,
        JMPI("start"),
        INVALID,
        LABEL("start")
    ]

    """
    function saveM() {
        for (let i=0; i<t; i++) {
            for (let j=0; j<t; j++) {
                C.push(toHex256(M[i][j]));
                C.push((1+i*t+j)*32);
                C.mstore();
            }
        }
    }
    """
    M = params.constants_M
    yield [ [PUSH(M[i][j]), PUSH((1+i*params.t+j)*32), MSTORE]
             for j in range(params.t)
           for i in range(params.t)]

    yield PUSH(SNARK_SCALAR_FIELD)  # q

    # Load 6 values from the call data.
    # The function has a single array param param
    # [Selector (4)] [Pointer (32)][Length (32)] [data1 (32)] ....
    # We ignore the pointer and the length and just load 6 values to the state
    # (Stack positions 0-5) If the array is shorter, we just set zeros.
    """    
    for (let i=0; i<t; i++) {
        C.push(0x44+(0x20*(5-i)));
        C.calldataload();
    }
    """
    yield [[PUSH(0x44+(0x20*(5-i))), CALLDATALOAD]
           for i in range(params.t)]

    """
    for (let i=0; i<nRoundsF+nRoundsP; i++) {
        ark(i);
        if ((i<nRoundsF/2) || (i>=nRoundsP+nRoundsF/2)) {
            for (let j=0; j<t; j++) {
                sigma(j);
            }
        } else {
            sigma(0);
        }
        const strLabel = "aferMix"+i;
        C._pushLabel(strLabel);
        C.push(0);
        C.mstore();
        C.jmp("mix");
        C.label(strLabel);
    }
    """
    for i in range(params.nRoundsF + params.nRoundsP):
        yield _add_round_key(i, params.t, params.constants_C)
        if i < (params.nRoundsF//2) or i >= (params.nRoundsP+(params.nRoundsF//2)):
            for j in range(params.t):
                yield _sigma(j, params.t)
        else:
            yield _sigma(0, params.t)
        label = 'after_mix_%d' % (i,)
        yield [
            PUSHLABEL(label),
            PUSH(0),
            MSTORE,
            JMP('mix'),
            LABEL(label)
        ]

    """
    C.push("0x00");
    C.mstore();     // Save it to pos 0;
    C.push("0x20");
    C.push("0x00");
    C.return();
    mix();
    """
    yield [PUSH(0),
           MSTORE,   # Save it to pos 0
           PUSH(0x20),
           PUSH(0),           
           RETURN]

    for _ in _mix(params):
        yield _


def poseidon_contract(params=None):
    gen = Codegen()
    for _ in poseidon_contract_opcodes(params):
        gen.append(_)
    return gen.createTxData()


def poseidon_abi():
    return [
        {
            "constant": True,
            "inputs": [
                {
                    "name": "input",
                    "type": "uint256[]"
                }
            ],
            "name": "poseidon",
            "outputs": [
                {
                    "name": "",
                    "type": "uint256"
                }
            ],
            "payable": False,
            "stateMutability": "pure",
            "type": "function"
        }
    ]


def main(*args): 
    if len(args) < 2:
        print("Usage: %s <abi|contract> [outfile]" % (args[0],))
        return 1
    command = args[1]
    outfile = sys.stdout
    if len(args) > 2:
        outfile = open(args[2], 'wb')
    if command == "abi":
        outfile.write(json.dumps(poseidon_abi()) + "\n")
        return 0
    elif command == "contract":
        data = poseidon_contract()
        if outfile == sys.stdout:            
            data = '0x' + hexlify(data).decode('ascii')
        outfile.write(data)
        return 0
    else:
        print("Error: unknown command", command)
    if outfile != sys.stdout:
        outfile.close()

if __name__ == "__main__":
    sys.exit(main(*sys.argv))
