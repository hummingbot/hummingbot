import numpy as np
import os
import subprocess
import sys

from setuptools import find_packages, setup
from setuptools.command.build_ext import build_ext

from Cython.Build import cythonize

is_posix = (os.name == "posix")

if is_posix:
    os_name = subprocess.check_output("uname").decode("utf8")
    if "Darwin" in os_name:
        os.environ["CFLAGS"] = "-stdlib=libc++ -std=c++11"
    else:
        os.environ["CFLAGS"] = "-std=c++11"

if os.environ.get('WITHOUT_CYTHON_OPTIMIZATIONS'):
    os.environ["CFLAGS"] += " -O0"


# Avoid a gcc warning below:
# cc1plus: warning: command line option ???-Wstrict-prototypes??? is valid
# for C/ObjC but not for C++
class BuildExt(build_ext):
    def build_extensions(self):
        if os.name != "nt" and '-Wstrict-prototypes' in self.compiler.compiler_so:
            self.compiler.compiler_so.remove('-Wstrict-prototypes')
        super().build_extensions()


def main():
    cpu_count = os.cpu_count() or 8
    version = "20211201"
    packages = find_packages(include=["hummingbot", "hummingbot.*"])
    package_data = {
        "hummingbot": [
            "core/cpp/*",
            "VERSION",
            "templates/*TEMPLATE.yml"
        ],
    }
    install_requires = [
        "0x-contract-addresses",
        "0x-contract-wrappers",
        "0x-order-utils",
        "aioconsole",
        "aiohttp",
        "aiokafka",
        "appdirs",
        "appnope",
        "bidict",
        "cachetools",
        "certifi",
        "cryptography",
        "cython",
        "cytoolz",
        "diff-cover",
        "dydx-python",
        "dydx-v3-python",
        "eth-abi",
        "eth-account",
        "eth-bloom",
        "eth-keyfile",
        "eth-typing",
        "eth-utils",
        "ethsnarks-loopring",
        "flake8",
        "hexbytes",
        "importlib-metadata",
        "mypy-extensions",
        "numpy",
        "pandas",
        "pip",
        "pre-commit",
        "prompt-toolkit",
        "psutil",
        "pyjwt",
        "pyperclip",
        "python-dateutil",
        "python-telegram-bot",
        "requests",
        "rsa",
        "ruamel-yaml",
        "scipy",
        "signalr-client-aio",
        "simplejson",
        "six",
        "sqlalchemy",
        "sync-timeout",
        "tzlocal",
        "ujson",
        "web3",
        "websockets",
        "yarl",
    ]

    cython_kwargs = {
        "language": "c++",
        "language_level": 3,
    }

    cython_sources = ["hummingbot/**/*.pyx"]
    if os.path.exists('test'):
        cython_sources.append("test/**/*.pyx")

    if os.environ.get('WITHOUT_CYTHON_OPTIMIZATIONS'):
        compiler_directives = {
            "optimize.use_switch": False,
            "optimize.unpack_method_calls": False,
        }
    else:
        compiler_directives = {}

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
          ext_modules=cythonize(cython_sources, compiler_directives=compiler_directives, **cython_kwargs),
          include_dirs=[
              np.get_include()
          ],
          scripts=[
              "bin/hummingbot.py",
              "bin/hummingbot_quickstart.py"
          ],
          cmdclass={'build_ext': BuildExt},
          )


if __name__ == "__main__":
    main()
