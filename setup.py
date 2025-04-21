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
    version = "20250421"
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
        "aiohttp>=3.8.5",
        "asyncssh>=2.13.2",
        "aioprocessing>=2.0.1",
        "aioresponses>=0.7.4",
        "aiounittest>=1.4.2",
        "async-timeout>=4.0.2,<5",
        "bidict>=0.22.1",
        "bip-utils",
        "cachetools>=5.3.1",
        "commlib-py>=0.11",
        "cryptography>=41.0.2",
        "eth-account>=0.13.0",
        "injective-py",
        "msgpack-python",
        "numpy>=1.25.0,<2",
        "objgraph",
        "pandas>=2.0.3",
        "pandas-ta>=0.3.14b",
        "prompt_toolkit>=3.0.39",
        "protobuf>=4.23.3",
        "psutil>=5.9.5",
        "pydantic>=2",
        "pyjwt>=2.3.0",
        "pyperclip>=1.8.2",
        "requests>=2.31.0",
        "ruamel.yaml>=0.2.5",
        "safe-pysha3",
        "scalecodec",
        "scipy>=1.11.1",
        "six>=1.16.0",
        "sqlalchemy>=1.4.49",
        "tabulate>=0.9.0",
        "ujson>=5.7.0",
        "urllib3>=1.26.15,<2.0",
        "web3",
        "xrpl-py>=4.1.0",
        "PyYaml>=0.2.5",
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
