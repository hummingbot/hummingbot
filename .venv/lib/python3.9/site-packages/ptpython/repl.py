"""
Utility for creating a Python repl.

::

    from ptpython.repl import embed
    embed(globals(), locals(), vi_mode=False)

"""

from __future__ import annotations

import asyncio
import builtins
import os
import signal
import sys
import traceback
import types
import warnings
from dis import COMPILER_FLAG_NAMES
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterable, NoReturn, Sequence

from prompt_toolkit.formatted_text import OneStyleAndTextTuple
from prompt_toolkit.patch_stdout import patch_stdout as patch_stdout_context
from prompt_toolkit.shortcuts import (
    clear_title,
    set_title,
)
from prompt_toolkit.utils import DummyContext
from pygments.lexers import PythonTracebackLexer  # noqa: F401

from .printer import OutputPrinter
from .python_input import PythonInput

PyCF_ALLOW_TOP_LEVEL_AWAIT: int
try:
    from ast import PyCF_ALLOW_TOP_LEVEL_AWAIT  # type: ignore
except ImportError:
    PyCF_ALLOW_TOP_LEVEL_AWAIT = 0


__all__ = [
    "PythonRepl",
    "enable_deprecation_warnings",
    "run_config",
    "embed",
    "exit",
    "ReplExit",
]


def _get_coroutine_flag() -> int | None:
    for k, v in COMPILER_FLAG_NAMES.items():
        if v == "COROUTINE":
            return k

    # Flag not found.
    return None


COROUTINE_FLAG: int | None = _get_coroutine_flag()


def _has_coroutine_flag(code: types.CodeType) -> bool:
    if COROUTINE_FLAG is None:
        # Not supported on this Python version.
        return False

    return bool(code.co_flags & COROUTINE_FLAG)


class PythonRepl(PythonInput):
    def __init__(self, *a, **kw) -> None:
        self._startup_paths: Sequence[str | Path] | None = kw.pop("startup_paths", None)
        super().__init__(*a, **kw)
        self._load_start_paths()

    def _load_start_paths(self) -> None:
        "Start the Read-Eval-Print Loop."
        if self._startup_paths:
            for path in self._startup_paths:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        code = compile(f.read(), path, "exec")
                        exec(code, self.get_globals(), self.get_locals())
                else:
                    output = self.app.output
                    output.write(f"WARNING | File not found: {path}\n\n")

    def run_and_show_expression(self, expression: str) -> None:
        try:
            # Eval.
            try:
                result = self.eval(expression)
            except KeyboardInterrupt:
                # KeyboardInterrupt doesn't inherit from Exception.
                raise
            except SystemExit:
                raise
            except ReplExit:
                raise
            except BaseException as e:
                self._handle_exception(e)
            else:
                if isinstance(result, exit):
                    # When `exit` is evaluated without parentheses.
                    # Automatically trigger the `ReplExit` exception.
                    raise ReplExit

                # Print.
                if result is not None:
                    self._show_result(result)
                    if self.insert_blank_line_after_output:
                        self.app.output.write("\n")

                # Loop.
                self.current_statement_index += 1
                self.signatures = []

        except KeyboardInterrupt as e:
            # Handle all possible `KeyboardInterrupt` errors. This can
            # happen during the `eval`, but also during the
            # `show_result` if something takes too long.
            # (Try/catch is around the whole block, because we want to
            # prevent that a Control-C keypress terminates the REPL in
            # any case.)
            self._handle_keyboard_interrupt(e)

    def _get_output_printer(self) -> OutputPrinter:
        return OutputPrinter(
            output=self.app.output,
            input=self.app.input,
            style=self._current_style,
            style_transformation=self.style_transformation,
            title=self.title,
        )

    def _show_result(self, result: object) -> None:
        self._get_output_printer().display_result(
            result=result,
            out_prompt=self.get_output_prompt(),
            reformat=self.enable_output_formatting,
            highlight=self.enable_syntax_highlighting,
            paginate=self.enable_pager,
        )

    def run(self) -> None:
        """
        Run the REPL loop.
        """
        if self.terminal_title:
            set_title(self.terminal_title)

        self._add_to_namespace()

        try:
            while True:
                # Pull text from the user.
                try:
                    text = self.read()
                except EOFError:
                    return
                except BaseException:
                    # Something went wrong while reading input.
                    # (E.g., a bug in the completer that propagates. Don't
                    # crash the REPL.)
                    traceback.print_exc()
                    continue

                # Run it; display the result (or errors if applicable).
                try:
                    self.run_and_show_expression(text)
                except ReplExit:
                    return
        finally:
            if self.terminal_title:
                clear_title()
            self._remove_from_namespace()

    async def run_and_show_expression_async(self, text: str) -> Any:
        loop = asyncio.get_running_loop()
        system_exit: SystemExit | None = None

        try:
            try:
                # Create `eval` task. Ensure that control-c will cancel this
                # task.
                async def eval() -> Any:
                    nonlocal system_exit
                    try:
                        return await self.eval_async(text)
                    except SystemExit as e:
                        # Don't propagate SystemExit in `create_task()`. That
                        # will kill the event loop. We want to handle it
                        # gracefully.
                        system_exit = e

                task = asyncio.create_task(eval())
                loop.add_signal_handler(signal.SIGINT, lambda *_: task.cancel())
                result = await task

                if system_exit is not None:
                    raise system_exit
            except KeyboardInterrupt:
                # KeyboardInterrupt doesn't inherit from Exception.
                raise
            except SystemExit:
                raise
            except BaseException as e:
                self._handle_exception(e)
            else:
                # Print.
                if result is not None:
                    await loop.run_in_executor(None, lambda: self._show_result(result))

                # Loop.
                self.current_statement_index += 1
                self.signatures = []
                # Return the result for future consumers.
                return result
            finally:
                loop.remove_signal_handler(signal.SIGINT)

        except KeyboardInterrupt as e:
            # Handle all possible `KeyboardInterrupt` errors. This can
            # happen during the `eval`, but also during the
            # `show_result` if something takes too long.
            # (Try/catch is around the whole block, because we want to
            # prevent that a Control-C keypress terminates the REPL in
            # any case.)
            self._handle_keyboard_interrupt(e)

    async def run_async(self) -> None:
        """
        Run the REPL loop, but run the blocking parts in an executor, so that
        we don't block the event loop. Both the input and output (which can
        display a pager) will run in a separate thread with their own event
        loop, this way ptpython's own event loop won't interfere with the
        asyncio event loop from where this is called.

        The "eval" however happens in the current thread, which is important.
        (Both for control-C to work, as well as for the code to see the right
        thread in which it was embedded).
        """
        loop = asyncio.get_running_loop()

        if self.terminal_title:
            set_title(self.terminal_title)

        self._add_to_namespace()

        try:
            while True:
                try:
                    # Read.
                    try:
                        text = await loop.run_in_executor(None, self.read)
                    except EOFError:
                        return
                    except BaseException:
                        # Something went wrong while reading input.
                        # (E.g., a bug in the completer that propagates. Don't
                        # crash the REPL.)
                        traceback.print_exc()
                        continue

                    # Eval.
                    await self.run_and_show_expression_async(text)

                except KeyboardInterrupt as e:
                    # XXX: This does not yet work properly. In some situations,
                    # `KeyboardInterrupt` exceptions can end up in the event
                    # loop selector.
                    self._handle_keyboard_interrupt(e)
                except SystemExit:
                    return
        finally:
            if self.terminal_title:
                clear_title()
            self._remove_from_namespace()

    def eval(self, line: str) -> object:
        """
        Evaluate the line and print the result.
        """
        # WORKAROUND: Due to a bug in Jedi, the current directory is removed
        # from sys.path. See: https://github.com/davidhalter/jedi/issues/1148
        if "" not in sys.path:
            sys.path.insert(0, "")

        if line.lstrip().startswith("!"):
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                code = self._compile_with_flags(line, "eval")
            except SyntaxError:
                pass
            else:
                # No syntax errors for eval. Do eval.
                result = eval(code, self.get_globals(), self.get_locals())

                if _has_coroutine_flag(code):
                    result = asyncio.get_running_loop().run_until_complete(result)

                self._store_eval_result(result)
                return result

            # If not a valid `eval` expression, run using `exec` instead.
            # Note that we shouldn't run this in the `except SyntaxError` block
            # above, then `sys.exc_info()` would not report the right error.
            # See issue: https://github.com/prompt-toolkit/ptpython/issues/435
            code = self._compile_with_flags(line, "exec")
            result = eval(code, self.get_globals(), self.get_locals())

            if _has_coroutine_flag(code):
                result = asyncio.get_running_loop().run_until_complete(result)

        return None

    async def eval_async(self, line: str) -> object:
        """
        Evaluate the line and print the result.
        """
        # WORKAROUND: Due to a bug in Jedi, the current directory is removed
        # from sys.path. See: https://github.com/davidhalter/jedi/issues/1148
        if "" not in sys.path:
            sys.path.insert(0, "")

        if line.lstrip().startswith("!"):
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                code = self._compile_with_flags(line, "eval")
            except SyntaxError:
                pass
            else:
                # No syntax errors for eval. Do eval.
                result = eval(code, self.get_globals(), self.get_locals())

                if _has_coroutine_flag(code):
                    result = await result

                self._store_eval_result(result)
                return result

            # If not a valid `eval` expression, compile as `exec` expression
            # but still run with eval to get an awaitable in case of a
            # awaitable expression.
            code = self._compile_with_flags(line, "exec")
            result = eval(code, self.get_globals(), self.get_locals())

            if _has_coroutine_flag(code):
                result = await result

        return None

    def _store_eval_result(self, result: object) -> None:
        locals: dict[str, Any] = self.get_locals()
        locals["_"] = locals["_%i" % self.current_statement_index] = result

    def get_compiler_flags(self) -> int:
        return super().get_compiler_flags() | PyCF_ALLOW_TOP_LEVEL_AWAIT

    def _compile_with_flags(self, code: str, mode: str) -> Any:
        "Compile code with the right compiler flags."
        return compile(
            code,
            "<stdin>",
            mode,
            flags=self.get_compiler_flags(),
            dont_inherit=True,
        )

    def _handle_exception(self, e: BaseException) -> None:
        self._get_output_printer().display_exception(
            e,
            highlight=self.enable_syntax_highlighting,
            paginate=self.enable_pager,
        )

    def _handle_keyboard_interrupt(self, e: KeyboardInterrupt) -> None:
        output = self.app.output

        output.write("\rKeyboardInterrupt\n\n")
        output.flush()

    def _add_to_namespace(self) -> None:
        """
        Add ptpython built-ins to global namespace.
        """
        globals = self.get_globals()

        # Add a 'get_ptpython', similar to 'get_ipython'
        def get_ptpython() -> PythonInput:
            return self

        globals["get_ptpython"] = get_ptpython
        globals["exit"] = exit()

    def _remove_from_namespace(self) -> None:
        """
        Remove added symbols from the globals.
        """
        globals = self.get_globals()
        del globals["get_ptpython"]

    def print_paginated_formatted_text(
        self,
        formatted_text: Iterable[OneStyleAndTextTuple],
        end: str = "\n",
    ) -> None:
        # Warning: This is mainly here backwards-compatibility. Some projects
        # call `print_paginated_formatted_text` on the Repl object.
        self._get_output_printer().display_style_and_text_tuples(
            formatted_text, paginate=True
        )


def enable_deprecation_warnings() -> None:
    """
    Show deprecation warnings, when they are triggered directly by actions in
    the REPL. This is recommended to call, before calling `embed`.

    e.g. This will show an error message when the user imports the 'sha'
         library on Python 2.7.
    """
    warnings.filterwarnings("default", category=DeprecationWarning, module="__main__")


DEFAULT_CONFIG_FILE = "~/.config/ptpython/config.py"


def run_config(repl: PythonInput, config_file: str | None = None) -> None:
    """
    Execute REPL config file.

    :param repl: `PythonInput` instance.
    :param config_file: Path of the configuration file.
    """
    explicit_config_file = config_file is not None

    # Expand tildes.
    config_file = os.path.expanduser(
        config_file if config_file is not None else DEFAULT_CONFIG_FILE
    )

    def enter_to_continue() -> None:
        input("\nPress ENTER to continue...")

    # Check whether this file exists.
    if not os.path.exists(config_file):
        if explicit_config_file:
            print(f"Impossible to read {config_file}")
            enter_to_continue()
        return

    # Run the config file in an empty namespace.
    try:
        namespace: dict[str, Any] = {}

        with open(config_file, "rb") as f:
            code = compile(f.read(), config_file, "exec")
            exec(code, namespace, namespace)

        # Now we should have a 'configure' method in this namespace. We call this
        # method with the repl as an argument.
        if "configure" in namespace:
            namespace["configure"](repl)

    except Exception:
        traceback.print_exc()
        enter_to_continue()


class exit:
    """
    Exit the ptpython REPL.
    """

    # This custom exit function ensures that the `embed` function returns from
    # where we are embedded, and Python doesn't close `sys.stdin` like
    # the default `exit` from `_sitebuiltins.Quitter` does.

    def __call__(self) -> NoReturn:
        raise ReplExit

    def __repr__(self) -> str:
        # (Same message as the built-in Python REPL.)
        return "Use exit() or Ctrl-D (i.e. EOF) to exit"


class ReplExit(Exception):
    """
    Exception raised by ptpython's exit function.
    """


def embed(
    globals: dict[str, Any] | None = None,
    locals: dict[str, Any] | None = None,
    configure: Callable[[PythonRepl], None] | None = None,
    vi_mode: bool = False,
    history_filename: str | None = None,
    title: str | None = None,
    startup_paths: Sequence[str | Path] | None = None,
    patch_stdout: bool = False,
    return_asyncio_coroutine: bool = False,
) -> None:
    """
    Call this to embed  Python shell at the current point in your program.
    It's similar to `IPython.embed` and `bpython.embed`. ::

        from prompt_toolkit.contrib.repl import embed
        embed(globals(), locals())

    :param vi_mode: Boolean. Use Vi instead of Emacs key bindings.
    :param configure: Callable that will be called with the `PythonRepl` as a first
                      argument, to trigger configuration.
    :param title: Title to be displayed in the terminal titlebar. (None or string.)
    :param patch_stdout:  When true, patch `sys.stdout` so that background
        threads that are printing will print nicely above the prompt.
    """
    # Default globals/locals
    if globals is None:
        globals = {
            "__name__": "__main__",
            "__package__": None,
            "__doc__": None,
            "__builtins__": builtins,
        }

    locals = locals or globals

    def get_globals() -> dict[str, Any]:
        return globals

    def get_locals() -> dict[str, Any]:
        return locals

    # Create REPL.
    repl = PythonRepl(
        get_globals=get_globals,
        get_locals=get_locals,
        vi_mode=vi_mode,
        history_filename=history_filename,
        startup_paths=startup_paths,
    )

    if title:
        repl.terminal_title = title

    if configure:
        configure(repl)

    # Start repl.
    patch_context: ContextManager[None] = (
        patch_stdout_context() if patch_stdout else DummyContext()
    )

    if return_asyncio_coroutine:

        async def coroutine() -> None:
            with patch_context:
                await repl.run_async()

        return coroutine()  # type: ignore
    else:
        with patch_context:
            repl.run()
