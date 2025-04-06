"""
Tool for embedding a REPL inside a Python 3 asyncio process.
See ./examples/asyncio-ssh-python-embed.py for a demo.

Note that the code in this file is Python 3 only. However, we
should make sure not to use Python 3-only syntax, because this
package should be installable in Python 2 as well!
"""

from __future__ import annotations

import asyncio
from typing import Any, AnyStr, TextIO, cast

import asyncssh
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output

from ptpython.python_input import _GetNamespace, _Namespace
from ptpython.repl import PythonRepl

__all__ = ["ReplSSHServerSession"]


class ReplSSHServerSession(asyncssh.SSHServerSession[str]):
    """
    SSH server session that runs a Python REPL.

    :param get_globals: callable that returns the current globals.
    :param get_locals: (optional) callable that returns the current locals.
    """

    def __init__(
        self, get_globals: _GetNamespace, get_locals: _GetNamespace | None = None
    ) -> None:
        self._chan: Any = None

        def _globals() -> _Namespace:
            data = get_globals()
            data.setdefault("print", self._print)
            return data

        # PipInput object, for sending input in the CLI.
        # (This is something that we can use in the prompt_toolkit event loop,
        # but still write date in manually.)
        self._input_pipe = create_pipe_input()

        # Output object. Don't render to the real stdout, but write everything
        # in the SSH channel.
        class Stdout:
            def write(s, data: str) -> None:
                if self._chan is not None:
                    data = data.replace("\n", "\r\n")
                    self._chan.write(data)

            def flush(s) -> None:
                pass

        self.repl = PythonRepl(
            get_globals=_globals,
            get_locals=get_locals or _globals,
            input=self._input_pipe,
            output=Vt100_Output(cast(TextIO, Stdout()), self._get_size),
        )

        # Disable open-in-editor and system prompt. Because it would run and
        # display these commands on the server side, rather than in the SSH
        # client.
        self.repl.enable_open_in_editor = False
        self.repl.enable_system_bindings = False

    def _get_size(self) -> Size:
        """
        Callable that returns the current `Size`, required by Vt100_Output.
        """
        if self._chan is None:
            return Size(rows=20, columns=79)
        else:
            width, height, pixwidth, pixheight = self._chan.get_terminal_size()
            return Size(rows=height, columns=width)

    def connection_made(self, chan: Any) -> None:
        """
        Client connected, run repl in coroutine.
        """
        self._chan = chan

        # Run REPL interface.
        f = asyncio.ensure_future(self.repl.run_async())

        # Close channel when done.
        def done(_: object) -> None:
            chan.close()
            self._chan = None

        f.add_done_callback(done)

    def shell_requested(self) -> bool:
        return True

    def terminal_size_changed(
        self, width: int, height: int, pixwidth: int, pixheight: int
    ) -> None:
        """
        When the terminal size changes, report back to CLI.
        """
        self.repl.app._on_resize()

    def data_received(self, data: AnyStr, datatype: int | None) -> None:
        """
        When data is received, send to inputstream of the CLI and repaint.
        """
        self._input_pipe.send(data)  # type: ignore

    def _print(
        self, *data: object, sep: str = " ", end: str = "\n", file: Any = None
    ) -> None:
        """
        Alternative 'print' function that prints back into the SSH channel.
        """
        # Pop keyword-only arguments. (We cannot use the syntax from the
        # signature. Otherwise, Python2 will give a syntax error message when
        # installing.)
        data_as_str = sep.join(map(str, data))
        self._chan.write(data_as_str + end)
