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
    # name/version/description/author/license/requires-python/dependencies live in
    # pyproject.toml's [project] table now — setup.py only supplies what pyproject.toml
    # can't express (the Cython build and the fnmatch-filtered package list).
    setup(
        packages=packages,
        package_data=package_data,
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
