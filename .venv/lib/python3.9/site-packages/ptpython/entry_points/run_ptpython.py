#!/usr/bin/env python
"""
ptpython: Interactive Python shell.

positional arguments:
  args                  Script and arguments

optional arguments:
  -h, --help            show this help message and exit
  --vi                  Enable Vi key bindings
  -i, --interactive     Start interactive shell after executing this file.
  --asyncio             Run an asyncio event loop to support top-level "await".
  --light-bg            Run on a light background (use dark colors for text).
  --dark-bg             Run on a dark background (use light colors for text).
  --config-file CONFIG_FILE
                        Location of configuration file.
  --history-file HISTORY_FILE
                        Location of history file.
  -V, --version         show program's version number and exit

environment variables:
  PTPYTHON_CONFIG_HOME: a configuration directory to use
  PYTHONSTARTUP: file executed on interactive startup (no default)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import sys
from textwrap import dedent
from typing import IO

import appdirs
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import print_formatted_text

from ptpython.repl import PythonRepl, embed, enable_deprecation_warnings, run_config

try:
    from importlib import metadata  # type: ignore
except ImportError:
    import importlib_metadata as metadata  # type: ignore


__all__ = ["create_parser", "get_config_and_history_file", "run"]


class _Parser(argparse.ArgumentParser):
    def print_help(self, file: IO[str] | None = None) -> None:
        super().print_help()
        print(
            dedent(
                """
                environment variables:
                  PTPYTHON_CONFIG_HOME: a configuration directory to use
                  PYTHONSTARTUP: file executed on interactive startup (no default)
                """,
            ).rstrip(),
        )


def create_parser() -> _Parser:
    parser = _Parser(description="ptpython: Interactive Python shell.")
    parser.add_argument("--vi", action="store_true", help="Enable Vi key bindings")
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start interactive shell after executing this file.",
    )
    parser.add_argument(
        "--asyncio",
        action="store_true",
        help='Run an asyncio event loop to support top-level "await".',
    )
    parser.add_argument(
        "--light-bg",
        action="store_true",
        help="Run on a light background (use dark colors for text).",
    )
    parser.add_argument(
        "--dark-bg",
        action="store_true",
        help="Run on a dark background (use light colors for text).",
    )
    parser.add_argument(
        "--config-file", type=str, help="Location of configuration file."
    )
    parser.add_argument("--history-file", type=str, help="Location of history file.")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=metadata.version("ptpython"),
    )
    parser.add_argument("args", nargs="*", help="Script and arguments")
    return parser


def get_config_and_history_file(namespace: argparse.Namespace) -> tuple[str, str]:
    """
    Check which config/history files to use, ensure that the directories for
    these files exist, and return the config and history path.
    """
    config_dir = os.environ.get(
        "PTPYTHON_CONFIG_HOME",
        appdirs.user_config_dir("ptpython", "prompt_toolkit"),
    )
    data_dir = appdirs.user_data_dir("ptpython", "prompt_toolkit")

    # Create directories.
    for d in (config_dir, data_dir):
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)

    # Determine config file to be used.
    config_file = os.path.join(config_dir, "config.py")
    legacy_config_file = os.path.join(os.path.expanduser("~/.ptpython"), "config.py")

    warnings = []

    # Config file
    if namespace.config_file:
        # Override config_file.
        config_file = os.path.expanduser(namespace.config_file)

    elif os.path.isfile(legacy_config_file):
        # Warn about the legacy configuration file.
        warnings.append(
            HTML(
                "    <i>~/.ptpython/config.py</i> is deprecated, move your configuration to <i>%s</i>\n"
            )
            % config_file
        )
        config_file = legacy_config_file

    # Determine history file to be used.
    history_file = os.path.join(data_dir, "history")
    legacy_history_file = os.path.join(os.path.expanduser("~/.ptpython"), "history")

    if namespace.history_file:
        # Override history_file.
        history_file = os.path.expanduser(namespace.history_file)

    elif os.path.isfile(legacy_history_file):
        # Warn about the legacy history file.
        warnings.append(
            HTML(
                "    <i>~/.ptpython/history</i> is deprecated, move your history to <i>%s</i>\n"
            )
            % history_file
        )
        history_file = legacy_history_file

    # Print warnings.
    if warnings:
        print_formatted_text(HTML("<u>Warning:</u>"))
        for w in warnings:
            print_formatted_text(w)

    return config_file, history_file


def run() -> None:
    a = create_parser().parse_args()

    config_file, history_file = get_config_and_history_file(a)

    # Startup path
    startup_paths = []
    if "PYTHONSTARTUP" in os.environ:
        startup_paths.append(os.environ["PYTHONSTARTUP"])

    # --interactive
    if a.interactive and a.args:
        # Note that we shouldn't run PYTHONSTARTUP when -i is given.
        startup_paths = [a.args[0]]
        sys.argv = a.args

    # Add the current directory to `sys.path`.
    if sys.path[0] != "":
        sys.path.insert(0, "")

    # When a file has been given, run that, otherwise start the shell.
    if a.args and not a.interactive:
        sys.argv = a.args
        path = a.args[0]
        with open(path, "rb") as f:
            code = compile(f.read(), path, "exec")
            # NOTE: We have to pass a dict as namespace. Omitting this argument
            #       causes imports to not be found. See issue #326.
            #       However, an empty dict sets __name__ to 'builtins', which
            #       breaks `if __name__ == '__main__'` checks. See issue #444.
            exec(code, {"__name__": "__main__", "__file__": path})

    # Run interactive shell.
    else:
        enable_deprecation_warnings()

        # Apply config file
        def configure(repl: PythonRepl) -> None:
            if os.path.exists(config_file):
                run_config(repl, config_file)

            # Adjust colors if dark/light background flag has been given.
            if a.light_bg:
                repl.min_brightness = 0.0
                repl.max_brightness = 0.60
            elif a.dark_bg:
                repl.min_brightness = 0.60
                repl.max_brightness = 1.0

        import __main__

        embed_result = embed(  # type: ignore
            vi_mode=a.vi,
            history_filename=history_file,
            configure=configure,
            locals=__main__.__dict__,
            globals=__main__.__dict__,
            startup_paths=startup_paths,
            title="Python REPL (ptpython)",
            return_asyncio_coroutine=a.asyncio,
        )

        if a.asyncio:
            print("Starting ptpython asyncio REPL")
            print('Use "await" directly instead of "asyncio.run()".')
            asyncio.run(embed_result)


if __name__ == "__main__":
    run()
