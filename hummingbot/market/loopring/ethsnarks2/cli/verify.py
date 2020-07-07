import sys
import json

from ..verifier import VerifyingKey, Proof


def main(vk_file, proof_file):
    """Verifies the proof.json using the vk.json"""
    with open(vk_file, 'r') as vk_handle:
        vk = VerifyingKey.from_dict(json.load(vk_handle))
    with open(proof_file, 'r') as proof_handle:
        proof = Proof.from_dict(json.load(proof_handle))
    if not vk.verify(proof):
        print("FAIL")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: ethsnarks.cli.verify <vk.json> <proof.json>")
        sys.exit(1)
    sys.exit(main(*sys.argv[1:]))
