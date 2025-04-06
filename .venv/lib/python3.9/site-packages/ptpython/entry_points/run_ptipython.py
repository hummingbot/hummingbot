#!/usr/bin/env python
from __future__ import annotations

import os
import sys

from .run_ptpython import create_parser, get_config_and_history_file


def run(user_ns=None):
    a = create_parser().parse_args()

    config_file, history_file = get_config_and_history_file(a)

    # If IPython is not available, show message and exit here with error status
    # code.
    try:
        import IPython
    except ImportError:
        print("IPython not found. Please install IPython (pip install ipython).")
        sys.exit(1)
    else:
        from ptpython.ipython import embed
        from ptpython.repl import enable_deprecation_warnings, run_config

    # Add the current directory to `sys.path`.
    if sys.path[0] != "":
        sys.path.insert(0, "")

    # When a file has been given, run that, otherwise start the shell.
    if a.args and not a.interactive:
        sys.argv = a.args
        path = a.args[0]
        with open(path, "rb") as f:
            code = compile(f.read(), path, "exec")
            exec(code, {"__name__": "__main__", "__file__": path})
    else:
        enable_deprecation_warnings()

        # Create an empty namespace for this interactive shell. (If we don't do
        # that, all the variables from this function will become available in
        # the IPython shell.)
        if user_ns is None:
            user_ns = {}

        # Startup path
        startup_paths = []
        if "PYTHONSTARTUP" in os.environ:
            startup_paths.append(os.environ["PYTHONSTARTUP"])

        # --interactive
        if a.interactive:
            startup_paths.append(a.args[0])
            sys.argv = a.args

        # exec scripts from startup paths
        for path in startup_paths:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    code = compile(f.read(), path, "exec")
                    exec(code, user_ns, user_ns)
            else:
                print(f"File not found: {path}\n\n")
                sys.exit(1)

        # Apply config file
        def configure(repl):
            if os.path.exists(config_file):
                run_config(repl, config_file)

        # Run interactive shell.
        embed(
            vi_mode=a.vi,
            history_filename=history_file,
            configure=configure,
            user_ns=user_ns,
            title="IPython REPL (ptipython)",
        )


if __name__ == "__main__":
    run()
