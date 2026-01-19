import fnmatch
import os
import subprocess
import sys

import numpy as np
from Cython.Build import cythonize
from setuptools import find_packages, setup
from setuptools.command.build_ext import build_ext

is_posix = (os.name == "posix")


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
    version = "20251215"
    all_packages = find_packages(include=["hummingbot", "hummingbot.*"], )
    excluded_paths = [
        "hummingbot.connector.gateway.clob_spot.data_sources.injective",
        "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual"
    ]
    packages = [
        pkg for pkg in all_packages
        if not any(fnmatch.fnmatch(pkg, pattern) for pattern in excluded_paths)
    ]
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
        "numba>=0.61.2",
        "numpy>=2.2.6",
        "objgraph",
        "pandas>=2.3.2",
        "pandas-ta>=0.4.71b",
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
        "TA-Lib>=0.6.4",
        "tqdm>=4.67.1",
        "ujson>=5.7.0",
        "urllib3>=1.26.15,<2.0",
        "web3",
        "xrpl-py>=4.1.0",
        "PyYaml>=0.2.5",
    ]

    # --- 1. Define Flags (But don't pass them to Cython yet) ---
    extra_compile_args = []
    extra_link_args = []

    if is_posix:
        os_name = subprocess.check_output("uname").decode("utf8")
        if "Darwin" in os_name:
            # macOS specific flags
            extra_compile_args.extend(["-stdlib=libc++", "-std=c++11"])
            extra_link_args.extend(["-stdlib=libc++", "-std=c++11"])
        else:
            # Linux/POSIX flags
            extra_compile_args.append("-std=c++11")
            extra_link_args.append("-std=c++11")

    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        extra_compile_args.append("-O0")

    # --- 2. Setup Cython Options (Without the flags) ---
    cython_kwargs = {
        "language": "c++",
        "language_level": 3,
    }

    if is_posix:
        cython_kwargs["nthreads"] = cpu_count

    cython_sources = ["hummingbot/**/*.pyx"]

    compiler_directives = {
        "annotation_typing": False,
    }
    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        compiler_directives.update({
            "optimize.use_switch": False,
            "optimize.unpack_method_calls": False,
        })

    if "DEV_MODE" in os.environ:
        version += ".dev1"
        package_data[""] = [
            "*.pxd", "*.pyx", "*.h"
        ]
        package_data["hummingbot"].append("core/cpp/*.cpp")

    if len(sys.argv) > 1 and sys.argv[1] == "build_ext" and is_posix:
        sys.argv.append(f"--parallel={cpu_count}")

    # --- 3. Generate Extensions & Manually Apply Flags ---
    extensions = cythonize(
        cython_sources,
        compiler_directives=compiler_directives,
        **cython_kwargs
    )

    for ext in extensions:
        ext.extra_compile_args = extra_compile_args
        ext.extra_link_args = extra_link_args

    # --- 4. Pass the modified extensions to setup ---
    setup(
        name="hummingbot",
        version=version,
        description="Hummingbot",
        url="https://github.com/hummingbot/hummingbot",
        author="Hummingbot Foundation",
        author_email="dev@hummingbot.org",
        license="Apache 2.0",
        packages=packages,
        package_data=package_data,
        install_requires=install_requires,
        ext_modules=extensions,  # <--- Use the list we modified
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
