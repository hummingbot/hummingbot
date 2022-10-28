import os
import pathlib
import subprocess
import sys
from typing import List

import numpy as np
from Cython.Build import cythonize
from setuptools import find_packages, setup
from setuptools.command.build_ext import build_ext
from setuptools.extension import Extension

is_posix = (os.name == "posix")

if is_posix:
    os_name = subprocess.check_output("uname").decode("utf8")
    if "Darwin" in os_name:
        os.environ["CFLAGS"] = "-stdlib=libc++ -std=c++11"
    else:
        os.environ["CFLAGS"] = "-std=c++11"

if os.environ.get('WITHOUT_CYTHON_OPTIMIZATIONS'):
    os.environ["CFLAGS"] += " -O0"

IS_PY_DEBUG = os.getenv('EXT_BUILD_PY_DEBUG', False)

coverage_macros = []
coverage_compiler_directives = dict()
coverage_include_path = []

if not IS_PY_DEBUG:
    print('Extension IS_CYTHON_COVERAGE=True!')
    # Adding cython line trace for coverage report
    coverage_macros += ("CYTHON_TRACE_NOGIL", 1), ("CYTHON_TRACE", 1)
    # Adding upper directory for supporting code coverage when running tests inside the cython package
    coverage_include_path += ['..']
    # Some extra info for cython compiler
    coverage_compiler_directives = dict(linetrace=True, profile=True, binding=True)


# Avoid a gcc warning below:
# cc1plus: warning: command line option ???-Wstrict-prototypes??? is valid
# for C/ObjC but not for C++
class BuildExt(build_ext):
    def build_extensions(self):
        if os.name != "nt" and '-Wstrict-prototypes' in self.compiler.compiler_so:
            self.compiler.compiler_so.remove('-Wstrict-prototypes')
        super().build_extensions()


def find_py_with_pxd() -> List[Extension]:
    extensions: List[Extension] = []
    pxd_files = pathlib.Path().glob(pattern="hummingbot/**/*.pxd")
    for pxd_file in pxd_files:
        parent = str(pxd_file.parent).replace("/", ".")
        obj = pxd_file.stem
        py_file = os.path.splitext(pxd_file)[0] + ".py"
        if os.path.isfile(py_file):
            extensions.append(Extension(parent + "." + obj,
                                        sources=[py_file],
                                        include_dirs=["hummingbot/core",
                                                      "hummingbot/core/data_type",
                                                      "hummingbot/core/cpp"],
                                        define_macros=[("NPY_NO_DEPRECATED_API",
                                                        "NPY_1_7_API_VERSION")] + coverage_macros,
                                        language="c++"))
    return extensions


def main():
    cpu_count = os.cpu_count() or 8
    version = "20220930"
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
        "async-timeout",
        "bidict",
        "cachetools",
        "certifi",
        "cryptography",
        "cython",
        "cytoolz",
        "docker",
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
        "nose",
        "nose-exclude",
        "numpy",
        "pandas",
        "pip",
        "pre-commit",
        "prompt-toolkit",
        "psutil",
        "pydantic",
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
        "tabulate",
        "tzlocal",
        "ujson",
        "web3",
        "websockets",
        "yarl",
    ]

    cython_kwargs = {
        "language_level": '3str',
        "gdb_debug": False,
        "force": False,
        "annotate": False,
    }

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

    cythonized_py = []
    if not IS_PY_DEBUG:
        python_sources = find_py_with_pxd()
        cythonized_py = cythonize(python_sources, compiler_directives=coverage_compiler_directives, **cython_kwargs)

    cythonized_pyx = cythonize(Extension("*",
                                         sources=["hummingbot/**/*.pyx"],
                                         language="c++",
                                         define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")]),
                               compiler_directives=compiler_directives, **cython_kwargs)

    setup(name="hummingbot",
          version=version,
          description="Hummingbot",
          url="https://github.com/hummingbot/hummingbot",
          author="CoinAlpha, Inc.",
          author_email="dev@hummingbot.io",
          license="Apache 2.0",
          packages=packages,
          package_data=package_data,
          install_requires=install_requires,
          zip_safe=False,
          ext_modules=[*cythonized_py, *cythonized_pyx],
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
