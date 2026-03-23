import os
import subprocess
import sys

import numpy as np
from Cython.Build import cythonize
from setuptools import setup
from setuptools.command.build_ext import build_ext

is_posix = (os.name == "posix")


class BuildExt(build_ext):
    """Strip -Wstrict-prototypes (C-only flag invalid for C++)."""

    def build_extensions(self):
        if os.name != "nt" and "-Wstrict-prototypes" in self.compiler.compiler_so:
            self.compiler.compiler_so.remove("-Wstrict-prototypes")
        super().build_extensions()


def main():
    cpu_count = os.cpu_count() or 8

    # --- Platform-specific compile/link flags ---
    extra_compile_args = []
    extra_link_args = []
    if is_posix:
        os_name = subprocess.check_output("uname").decode("utf8")
        if "Darwin" in os_name:
            extra_compile_args.extend(["-stdlib=libc++", "-std=c++11"])
            extra_link_args.extend(["-stdlib=libc++", "-std=c++11"])
        else:
            extra_compile_args.append("-std=c++11")
            extra_link_args.append("-std=c++11")

    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        extra_compile_args.append("-O0")

    # --- Cython options ---
    cython_kwargs = {"language": "c++", "language_level": 3}
    if is_posix:
        cython_kwargs["nthreads"] = cpu_count

    compiler_directives = {"annotation_typing": False}
    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        compiler_directives.update({
            "optimize.use_switch": False,
            "optimize.unpack_method_calls": False,
        })

    if len(sys.argv) > 1 and sys.argv[1] == "build_ext" and is_posix:
        sys.argv.append(f"--parallel={cpu_count}")

    # --- Generate extensions & apply flags ---
    extensions = cythonize(
        ["hummingbot/**/*.pyx"],
        compiler_directives=compiler_directives,
        **cython_kwargs,
    )
    for ext in extensions:
        ext.extra_compile_args = extra_compile_args
        ext.extra_link_args = extra_link_args

    # --- Metadata in pyproject.toml [project]; only build config here ---
    package_data = {"hummingbot": ["core/cpp/*", "VERSION", "templates/*TEMPLATE.yml"]}
    if "DEV_MODE" in os.environ:
        package_data[""] = ["*.pxd", "*.pyx", "*.h"]
        package_data["hummingbot"].append("core/cpp/*.cpp")

    setup(
        ext_modules=extensions,
        include_dirs=[np.get_include()],
        package_data=package_data,
        cmdclass={"build_ext": BuildExt},
    )


if __name__ == "__main__":
    main()
