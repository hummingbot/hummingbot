"""Provide the apython script."""

import os
import sys
import ast
import runpy
import warnings
import argparse
import traceback

from . import events
from . import server
from . import rlwrap
from . import compat

ZERO_WIDTH_SPACE = "\u200b"

DESCRIPTION = """\
Run the given python file or module with a modified asyncio policy replacing
the default event loop with an interactive loop.
If no argument is given, it simply runs an asynchronous python console."""

USAGE = """\
usage: apython [-h] [--serve [HOST:] PORT] [--no-readline]
               [--banner BANNER] [--locals LOCALS]
               [-m MODULE | FILE] ...
""".split(
    "usage: "
)[
    1
]


def exec_pythonstartup(locals_dict):
    filename = os.environ.get("PYTHONSTARTUP")
    if filename:
        if os.path.isfile(filename):
            with open(filename) as fobj:
                startupcode = fobj.read()
            try:
                locals_dict["__file__"] = filename
                exec(startupcode, globals(), locals_dict)
            except Exception:  # pragma: no cover
                traceback.print_exc()
            finally:
                locals_dict.pop("__file__", None)

        else:
            print(f"Could not open PYTHONSTARTUP - No such file: {filename}")


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        prog="apython", description=DESCRIPTION, usage=USAGE
    )

    # Options

    parser.add_argument(
        "--serve",
        "-s",
        metavar="[HOST:] PORT",
        help="serve a console on the given interface instead",
    )
    parser.add_argument(
        "--no-readline",
        dest="readline",
        action="store_false",
        help="disable readline support",
    )
    parser.add_argument("--banner", help="provide a custom banner")
    parser.add_argument(
        "--locals", type=ast.literal_eval, help="provide custom locals as a dictionary"
    )

    # Hidden option

    parser.add_argument("--prompt-control", metavar="PC", help=argparse.SUPPRESS)

    # Input

    parser.add_argument("-m", dest="module", help="run a python module")
    parser.add_argument(
        "filename", metavar="FILE", nargs="?", help="python file to run"
    )

    # Extra arguments

    parser.add_argument(
        "args", metavar="ARGS", nargs=argparse.REMAINDER, help="extra arguments"
    )

    namespace = parser.parse_args(args)

    # If module is provided, filename is actually the fist arg
    if namespace.module is not None and namespace.filename is not None:
        namespace.args.insert(0, namespace.filename)

    # Parse the serve argument
    if namespace.serve is not None:
        namespace.serve = server.parse_server(namespace.serve, parser)

    return namespace


def load_readline():
    try:
        import readline  # noqa: F401
        import rlcompleter  # noqa: F401
    except ImportError:
        return False
    return True


def run_apython(args=None):
    namespace = parse_args(args)

    if (
        namespace.readline
        and not namespace.serve
        and compat.platform != "win32"
        and load_readline()
    ):
        # Run python interactive hook in order to configure binding and history support
        interactive_hook = getattr(sys, "__interactivehook__", None)
        if interactive_hook:
            try:
                interactive_hook()
            except Exception as exc:
                warnings.warn(f"Interactive hook failed: {exc!r}", stacklevel=2)

        code = run_apython_in_subprocess(args, namespace.prompt_control)
        sys.exit(code)

    try:
        sys._argv = sys.argv
        sys._path = sys.path
        if namespace.module:
            sys.argv = [None] + namespace.args
            sys.path.insert(0, "")
            events.set_interactive_policy(
                locals=namespace.locals,
                banner=namespace.banner,
                serve=namespace.serve,
                prompt_control=namespace.prompt_control,
            )
            runpy.run_module(namespace.module, run_name="__main__", alter_sys=True)
        elif namespace.filename:
            sys.argv = [None] + namespace.args
            path = os.path.dirname(os.path.abspath(namespace.filename))
            sys.path.insert(0, path)
            events.set_interactive_policy(
                locals=namespace.locals,
                banner=namespace.banner,
                serve=namespace.serve,
                prompt_control=namespace.prompt_control,
            )
            runpy.run_path(namespace.filename, run_name="__main__")
        else:
            if namespace.locals is None:
                namespace.locals = {}
            exec_pythonstartup(namespace.locals)
            events.run_console(
                locals=namespace.locals,
                banner=namespace.banner,
                serve=namespace.serve,
                prompt_control=namespace.prompt_control,
            )
    finally:
        sys.argv = sys._argv
        sys.path = sys._path

    sys.exit()


def run_apython_in_subprocess(args=None, prompt_control=None):
    # Default arguments
    if args is None:
        args = sys.argv[1:]
    if prompt_control is None:
        prompt_control = ZERO_WIDTH_SPACE
    # Create subprocess
    proc_args = [
        sys.executable,
        "-m",
        "aioconsole",
        "--no-readline",
        "--prompt-control",
        prompt_control,
    ]
    return rlwrap.rlwrap_process(proc_args + args, prompt_control, use_stderr=True)
