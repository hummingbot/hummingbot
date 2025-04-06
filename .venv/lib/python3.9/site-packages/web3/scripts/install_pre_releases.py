"""
The goal of this script is to install the latest versions, including pre-releases, for
libraries that we maintain (and therefore control the release process) during our CI
runs. This helps us test pre-releases before they cause any issues once stable versions
are released.
"""

import subprocess
import sys

ETHEREUM_LIBRARIES = [
    "eth-account",
    "eth-abi",
    "eth-account",
    "eth-hash[pycryptodome]",
    "eth-typing",
    "eth-utils",
    "hexbytes",
    "eth-tester[py-evm]",
    "py-geth",
]


def install_eth_pre_releases() -> None:
    for lib in ETHEREUM_LIBRARIES:
        print(f"Installing {lib} with `--pre` and `-U`")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--pre", "-U", lib]
        )


if __name__ == "__main__":
    install_eth_pre_releases()
