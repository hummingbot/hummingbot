import sys
from math import log2

from ..field import SNARK_SCALAR_FIELD

from .permutation import mimc_constants


def mimc_contract_solidity(exponent, constants):
    # This means we can do 3 additions in sequence, before modulo reduction
    # Essentially replacing most of the `ADDMOD` instructions with `ADD`
    assert (3*(SNARK_SCALAR_FIELD-1)) < ((1<<256)-1)

    yield "pragma solidity ^0.5.0;"
    yield "library MiMCpe%d_generated {" % (exponent,)
    yield "\tfunction MiMCpe%d (uint256 in_x, uint256 in_k) internal pure returns (uint256 out_x) {" % (exponent,)
    yield "\t\tassembly {"
    yield f"\t\t\tlet localQ := {hex(SNARK_SCALAR_FIELD)}"
    yield "\t\t\tlet t"
    yield "\t\t\tlet a"

    for c_i in constants:
        c_i = c_i % SNARK_SCALAR_FIELD
        if exponent == 7:
            yield f"\t\t\tt := add(add(in_x, {hex(c_i)}), in_k)"        # t = x + c_i + k
            yield "\t\t\ta := mulmod(t, t, localQ)"                                           # t^2
            yield "\t\t\tin_x := mulmod(mulmod(a, mulmod(a, a, localQ), localQ), t, localQ)"  # t^7
        elif exponent == 5:
            yield f"\t\t\tt := add(add(in_x, {hex(c_i)}), in_k)"  # t = x + c_i + k
            yield "\t\t\ta := mulmod(t, t, localQ)"                                     # t^2
            yield "\t\t\tin_x := mulmod(mulmod(a, a, localQ), t, localQ)"               # t^5

    yield "\t\t\tout_x := addmod(in_x, in_k, localQ)"

    yield "\t\t}"
    yield "\t}"
    yield "}"


def main(*args): 
    if len(args) < 2:
        print("Usage: %s <exponent> [outfile]" % (args[0],))
        return 1

    exponent = int(args[1])
    if exponent not in (5, 7):
        print("Error: exponent must be 5 or 7")
        return 2

    outfile = sys.stdout
    if len(args) > 2:
        outfile = open(args[3], 'wb')

    constants = mimc_constants(R=110 if exponent == 5 else 91)

    for line in mimc_contract_solidity(exponent, constants):
        outfile.write(line + "\n")

    if outfile != sys.stdout:
        outfile.close()

    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
