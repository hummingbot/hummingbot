#!/usr/bin/env python

from setuptools import setup
from Cython.Build import cythonize
import numpy as np
import os
import subprocess
import sys

is_posix = (os.name == "posix")

if is_posix:
    os_name = subprocess.check_output("uname").decode("utf8")
    if "Darwin" in os_name:
        os.environ["CFLAGS"] = "-stdlib=libc++ -std=c++11"
    else:
        os.environ["CFLAGS"] = "-std=c++11"


def main():
    cpu_count = os.cpu_count() or 8
    version = "20200714"
    packages = [
        "hummingbot",
        "hummingbot.client",
        "hummingbot.client.command",
        "hummingbot.client.config",
        "hummingbot.client.ui",
        "hummingbot.core",
        "hummingbot.core.data_type",
        "hummingbot.core.event",
        "hummingbot.core.management",
        "hummingbot.core.utils",
        "hummingbot.data_feed",
        "hummingbot.logger",
        "hummingbot.market",
        "hummingbot.market.bamboo_relay",
        "hummingbot.market.binance",
        "hummingbot.market.bittrex",
        "hummingbot.market.coinbase_pro",
        "hummingbot.market.huobi",
        "hummingbot.market.radar_relay",
        "hummingbot.market.kraken",
        "hummingbot.market.kucoin",
        "hummingbot.script",
        "hummingbot.strategy",
        "hummingbot.strategy.arbitrage",
        "hummingbot.strategy.cross_exchange_market_making",
        "hummingbot.strategy.pure_market_making",
        "hummingbot.templates",
        "hummingbot.wallet",
        "hummingbot.wallet.ethereum",
        "hummingbot.wallet.ethereum.uniswap",
        "hummingbot.wallet.ethereum.watcher",
        "hummingbot.wallet.ethereum.zero_ex",
    ]
    package_data = {
        "hummingbot": [
            "core/cpp/*",
            "wallet/ethereum/zero_ex/*.json",
            "wallet/ethereum/token_abi/*.json",
            "wallet/ethereum/erc20_tokens.json",
            "VERSION",
            "templates/*TEMPLATE.yml"
        ],
    }
    install_requires = [
        "aioconsole",
        "aiokafka",
        "attrdict",
        "cytoolz",
        "eth-abi",
        "eth-account",
        "eth-bloom",
        "eth-hash",
        "eth-keyfile",
        "eth-keys",
        "eth-rlp",
        "eth-utils",
        "hexbytes",
        "kafka-python",
        "lru-dict",
        "parsimonious",
        "pycryptodome",
        "requests",
        "rlp",
        "toolz",
        "tzlocal",
        "urllib3",
        "web3",
        "websockets",
        "aiohttp",
        "async-timeout",
        "attrs",
        "certifi",
        "chardet",
        "cython==0.29.15",
        "idna",
        "idna_ssl",
        "multidict",
        "numpy",
        "pandas",
        "pytz",
        "pyyaml",
        "python-binance==0.7.1",
        "sqlalchemy",
        "ujson",
        "yarl",
    ]

    cython_kwargs = {
        "language": "c++",
        "language_level": 3,
    }

    if is_posix:
        cython_kwargs["nthreads"] = cpu_count

    if "DEV_MODE" in os.environ:
        version += ".dev1"
        package_data[""] = [
            "*.pxd", "*.pyx", "*.h"
        ]
        package_data["hummingbot"].append("core/cpp/*.cpp")

    if len(sys.argv) > 1 and sys.argv[1] == "build_ext" and is_posix:
        sys.argv.append(f"--parallel={cpu_count}")

    setup(name="hummingbot",
          version=version,
          description="Hummingbot",
          url="https://github.com/CoinAlpha/hummingbot",
          author="CoinAlpha, Inc.",
          author_email="dev@hummingbot.io",
          license="Apache 2.0",
          packages=packages,
          package_data=package_data,
          install_requires=install_requires,
          ext_modules=cythonize(["hummingbot/**/*.pyx"], **cython_kwargs),
          include_dirs=[
              np.get_include()
          ],
          scripts=[
              "bin/hummingbot.py",
              "bin/hummingbot_quickstart.py"
          ],
          )


if __name__ == "__main__":
    main()
