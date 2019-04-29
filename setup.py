#!/usr/bin/env python

from setuptools import setup
from Cython.Build import cythonize
import numpy as np
import os
import subprocess

if os.name == "posix":
    os_name = subprocess.check_output("uname").decode("utf8")
    if "Darwin" in os_name:
        os.environ["CFLAGS"] = "-stdlib=libc++ -std=c++11"
    else:
        os.environ["CFLAGS"] = "-std=c++11"


def main():
    version = "20190429"
    packages = [
        "wings",
        "wings.logger",
        "wings.model",
        "wings.strategy",
        "wings.watcher",
        "wings.data_source",
        "wings.orderbook",
        "wings.tracker",
        "wings.market",
        "wings.wallet",
        "hummingbot",
        "hummingbot.strategy",
        "hummingbot.strategy.arbitrage",
        "hummingbot.strategy.cross_exchange_market_making",
        "hummingbot.cli",
        "hummingbot.cli.ui",
        "hummingbot.cli.utils",
        "hummingbot.logger",
        "hummingbot.management",
        "hummingbot.templates",
    ]
    package_data = {
        "wings": [
            "cpp/*.h",
            "abi/*.json",
        ],
        "hummingbot": [
            "erc20_tokens.json",
            "VERSION",
            "templates/*TEMPLATE.yml"
        ],
    }
    install_requires=[
        "aioconsole",
        "aiokafka",
        "attrdict",
        "cytoolz",
        "eth-abi",
        "eth-account",
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
        "cython==0.29.5",
        "idna",
        "idna_ssl",
        "multidict",
        "numpy",
        "pandas",
        "pytz",
        "pyyaml",
        "python-binance==0.6.9",
        "sqlalchemy",
        "ujson",
        "yarl",
    ]

    if "DEV_MODE" in os.environ:
        version += ".dev1"
        package_data[""] = [
            "*.pxd", "*.pyx", "*.h"
        ]
        package_data["wings"].append("cpp/*.cpp")

    setup(name="hummingbot",
          version=version,
          description="CoinAlpha Hummingbot",
          url="https://github.com/CoinAlpha/hummingbot",
          author="Martin Kou",
          author_email="martin@coinalpha.com",
          license="Proprietary",
          packages=packages,
          package_data=package_data,
          install_requires=install_requires,
          ext_modules=cythonize([
              "hummingbot/**/*.pyx",
              "wings/**/*.pyx",
          ], language="c++", language_level=3),
          include_dirs=[
              np.get_include(),
          ],
          scripts=[
              "bin/hummingbot.py"
          ],
          )


if __name__ == "__main__":
    main()
