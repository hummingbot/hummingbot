import sys
import json

from ..verifier import Proof

from .utils import g2_to_sol, g1_to_sol


def main(vk_filename, name='_getStaticProof'):
    """Outputs the solidity code necessary to instansiate a ProofWithInput variable"""
    with open(vk_filename, 'r') as handle:
        proof = Proof.from_dict(json.load(handle))

        out = [
            "\tfunction %s (Verifier.ProofWithInput memory output)" % (name),
            "\t\tinternal pure",
            "\t{",
            "\t\tVerifier.Proof memory proof = output.proof;"
        ]

        for k in proof.G2_POINTS:
            x = getattr(proof, k)
            out.append("\t\tproof.%s = %s;" % (k, g2_to_sol(x)))

        for k in proof.G1_POINTS:
            x = getattr(proof, k)
            out.append("\t\tproof.%s = %s;" % (k, g1_to_sol(x)))

        out.append("\t\toutput.input = new uint256[](%d);" % (len(proof.input),))
        for i, v in enumerate(proof.input):
            out.append("\t\toutput.input[%d] = %s;" % (i, hex(v)))

        out.append("\t}")
        print('\n'.join(out))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ethsnarks.cli.proof2sol <proof.json> [func-name]")
        print("Outputs Solidity code, depending on Verifier.sol, which can be included in your code")
        sys.exit(1)
    sys.exit(main(*sys.argv[1:]))
