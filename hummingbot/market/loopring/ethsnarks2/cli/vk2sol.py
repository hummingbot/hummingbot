import sys
import json

from ..verifier import VerifyingKey

from .utils import g2_to_sol, g1_to_sol


def main(vk_filename, name='_getVerifyingKey'):
    """Outputs the solidity code necessary to instansiate a VerifyingKey variable"""
    with open(vk_filename, 'r') as handle:
        vk = VerifyingKey.from_dict(json.load(handle))
        indent = "\t\t"
        varname = "vk"
        out = [
            "\tfunction %s (Verifier.VerifyingKey memory %s)" % (name, varname),
            "\t\tinternal pure",
            "\t{",
        ]
        for k in vk.G2_POINTS:
            x = getattr(vk, k)
            out.append("%s%s.%s = %s;" % (indent, varname, k, g2_to_sol(x)))
        for k in vk.G1_POINTS:
            x = getattr(vk, k)
            out.append("%s%s.%s = %s;" % (indent, varname, k, g1_to_sol(x)))

        out.append("%s%s.gammaABC = new Pairing.G1Point[](%d);" % (indent, varname, len(vk.gammaABC)))
        for i, v in enumerate(vk.gammaABC):
            out.append("%s%s.gammaABC[%d] = %s;" % (indent, varname, i, g1_to_sol(v)))
        out.append("\t}")

        print('\n'.join(out))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ethsnarks.cli.vk2sol <vk.json> [func-name]")
        print("Outputs Solidity code, depending on Verifier.sol, which can be included in your code")
        sys.exit(1)
    sys.exit(main(*sys.argv[1:]))
