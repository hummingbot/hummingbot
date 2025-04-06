"""Provide asynchronous equivalent to input, exec and interact.

It also includes an interactive event loop, and a command line interface.
"""

from .execute import aexec, aeval
from .console import AsynchronousConsole, interact
from .stream import ainput, aprint, get_standard_streams
from .events import InteractiveEventLoop, InteractiveEventLoopPolicy
from .events import set_interactive_policy, run_console
from .command import AsynchronousCli
from .server import start_interactive_server
from .apython import run_apython


__version__ = "0.8.1"

__all__ = [
    "aexec",
    "aeval",
    "ainput",
    "aprint",
    "AsynchronousConsole",
    "interact",
    "InteractiveEventLoop",
    "InteractiveEventLoopPolicy",
    "set_interactive_policy",
    "run_console",
    "AsynchronousCli",
    "start_interactive_server",
    "get_standard_streams",
    "run_apython",
]
