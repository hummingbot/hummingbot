import os
import subprocess
import sys
import fnmatch

import numpy as np
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

if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
    os.environ["CFLAGS"] += " -O0"


# Avoid a gcc warning below:
# cc1plus: warning: command line option ???-Wstrict-prototypes??? is valid
# for C/ObjC but not for C++
class BuildExt(build_ext):
    def build_extensions(self):
        if os.name != "nt" and "-Wstrict-prototypes" in self.compiler.compiler_so:
            self.compiler.compiler_so.remove("-Wstrict-prototypes")
        super().build_extensions()


def main():
    cpu_count = os.cpu_count() or 8
    version = "20240828"
    all_packages = find_packages(include=["hummingbot", "hummingbot.*"], )
    excluded_paths = [
        "hummingbot.connector.gateway.clob_spot.data_sources.injective",
        "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual"
    ]
    packages = [pkg for pkg in all_packages if not any(fnmatch.fnmatch(pkg, pattern) for pattern in excluded_paths)]
    package_data = {
        "hummingbot": [
            "core/cpp/*",
            "VERSION",
            "templates/*TEMPLATE.yml"
        ],
    }
    install_requires = [
        "bidict",
        "aioconsole",
        "aiohttp",
        "aioprocessing",
        "asyncssh",
        "appdirs",
        "appnope",
        "async-timeout",
        "base58",
        "cachetools",
        "certifi",
        "coincurve",
        "cryptography",
        "cython==3.0.0",
        "cytoolz",
        "commlib-py",
        "docker",
        "diff-cover",
        "ecdsa",
        "eip712-structs",
        "eth-abi",
        "eth-account",
        "eth-bloom",
        "eth-keyfile",
        "eth-typing",
        "eth-utils",
        "flake8",
        "grpc",
        "hexbytes",
        "importlib-metadata",
        "injective-py",
        "mypy-extensions",
        "msgpack",
        "nose",
        "nose-exclude",
        "numpy==1.26.4",
        "pandas",
        "pip",
        "pre-commit",
        "prompt-toolkit",
        "protobuf",
        "psutil",
        "pydantic",
        "pyjwt",
        "pyperclip",
        "python-dateutil",
        "python-telegram-bot==12.8",
        "pyOpenSSL",
        "requests",
        "rsa",
        "ruamel-yaml",
        "scipy",
        "signalr-client-aio",
        "simplejson",
        "six",
        "sqlalchemy",
        "tabulate",
        "tzlocal",
        "ujson",
        "web3",
        "websockets",
        "yarl",
        "pandas_ta==0.3.14b",
        "xrpl-py==3.0.0",
    ]

    cython_kwargs = {
        "language": "c++",
        "language_level": 3,
    }

    cython_sources = ["hummingbot/**/*.pyx"]

    compiler_directives = {
        "annotation_typing": False,
    }
    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        compiler_directives.update({
            "optimize.use_switch": False,
            "optimize.unpack_method_calls": False,
        })

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
          url="https://github.com/hummingbot/hummingbot",
          author="Hummingbot Foundation",
          author_email="dev@hummingbot.org",
          license="Apache 2.0",
          packages=packages,
          package_data=package_data,
          install_requires=install_requires,
          ext_modules=cythonize(cython_sources, compiler_directives=compiler_directives, **cython_kwargs),
          include_dirs=[
              np.get_include()
          ],
          scripts=[
              "bin/hummingbot_quickstart.py"
          ],
          cmdclass={"build_ext": BuildExt},
          )


if __name__ == "__main__":
    main()
