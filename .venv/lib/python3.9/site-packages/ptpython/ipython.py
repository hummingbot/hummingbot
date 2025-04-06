"""

Adaptor for using the input system of `prompt_toolkit` with the IPython
backend.

This gives a powerful interactive shell that has a nice user interface, but
also the power of for instance all the %-magic functions that IPython has to
offer.

"""

from __future__ import annotations

from typing import Iterable
from warnings import warn

from IPython import utils as ipy_utils
from IPython.core.inputtransformer2 import TransformerManager
from IPython.terminal.embed import InteractiveShellEmbed as _InteractiveShellEmbed
from IPython.terminal.ipapp import load_default_config
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
    WordCompleter,
)
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.contrib.regular_languages.compiler import compile
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.contrib.regular_languages.lexer import GrammarLexer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import AnyFormattedText, PygmentsTokens
from prompt_toolkit.lexers import PygmentsLexer, SimpleLexer
from prompt_toolkit.styles import Style
from pygments.lexers import BashLexer, PythonLexer

from ptpython.prompt_style import PromptStyle

from .completer import PythonCompleter
from .python_input import PythonInput
from .repl import PyCF_ALLOW_TOP_LEVEL_AWAIT
from .style import default_ui_style
from .validator import PythonValidator

__all__ = ["embed"]


class IPythonPrompt(PromptStyle):
    """
    Style for IPython >5.0, use the prompt_toolkit tokens directly.
    """

    def __init__(self, prompts):
        self.prompts = prompts

    def in_prompt(self) -> AnyFormattedText:
        return PygmentsTokens(self.prompts.in_prompt_tokens())

    def in2_prompt(self, width: int) -> AnyFormattedText:
        return PygmentsTokens(self.prompts.continuation_prompt_tokens())

    def out_prompt(self) -> AnyFormattedText:
        return []


class IPythonValidator(PythonValidator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.isp = TransformerManager()

    def validate(self, document: Document) -> None:
        document = Document(text=self.isp.transform_cell(document.text))
        super().validate(document)


def create_ipython_grammar():
    """
    Return compiled IPython grammar.
    """
    return compile(
        r"""
        \s*
        (
            (?P<percent>%)(
                (?P<magic>pycat|run|loadpy|load)  \s+ (?P<py_filename>[^\s]+)  |
                (?P<magic>cat)                    \s+ (?P<filename>[^\s]+)     |
                (?P<magic>pushd|cd|ls)            \s+ (?P<directory>[^\s]+)    |
                (?P<magic>pdb)                    \s+ (?P<pdb_arg>[^\s]+)      |
                (?P<magic>autocall)               \s+ (?P<autocall_arg>[^\s]+) |
                (?P<magic>time|timeit|prun)       \s+ (?P<python>.+)           |
                (?P<magic>psource|pfile|pinfo|pinfo2) \s+ (?P<python>.+)       |
                (?P<magic>system)                 \s+ (?P<system>.+)           |
                (?P<magic>unalias)                \s+ (?P<alias_name>.+)       |
                (?P<magic>[^\s]+)   .* |
            ) .*            |
            !(?P<system>.+) |
            (?![%!]) (?P<python>.+)
        )
        \s*
    """
    )


def create_completer(
    get_globals,
    get_locals,
    magics_manager,
    alias_manager,
    get_enable_dictionary_completion,
):
    g = create_ipython_grammar()

    return GrammarCompleter(
        g,
        {
            "python": PythonCompleter(
                get_globals, get_locals, get_enable_dictionary_completion
            ),
            "magic": MagicsCompleter(magics_manager),
            "alias_name": AliasCompleter(alias_manager),
            "pdb_arg": WordCompleter(["on", "off"], ignore_case=True),
            "autocall_arg": WordCompleter(["0", "1", "2"], ignore_case=True),
            "py_filename": PathCompleter(
                only_directories=False, file_filter=lambda name: name.endswith(".py")
            ),
            "filename": PathCompleter(only_directories=False),
            "directory": PathCompleter(only_directories=True),
            "system": SystemCompleter(),
        },
    )


def create_lexer():
    g = create_ipython_grammar()

    return GrammarLexer(
        g,
        lexers={
            "percent": SimpleLexer("class:pygments.operator"),
            "magic": SimpleLexer("class:pygments.keyword"),
            "filename": SimpleLexer("class:pygments.name"),
            "python": PygmentsLexer(PythonLexer),
            "system": PygmentsLexer(BashLexer),
        },
    )


class MagicsCompleter(Completer):
    def __init__(self, magics_manager):
        self.magics_manager = magics_manager

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()

        for m in sorted(self.magics_manager.magics["line"]):
            if m.startswith(text):
                yield Completion(f"{m}", -len(text))


class AliasCompleter(Completer):
    def __init__(self, alias_manager):
        self.alias_manager = alias_manager

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()
        # aliases = [a for a, _ in self.alias_manager.aliases]
        aliases = self.alias_manager.aliases

        for a, cmd in sorted(aliases, key=lambda a: a[0]):
            if a.startswith(text):
                yield Completion(f"{a}", -len(text), display_meta=cmd)


class IPythonInput(PythonInput):
    """
    Override our `PythonCommandLineInterface` to add IPython specific stuff.
    """

    def __init__(self, ipython_shell, *a, **kw):
        kw["_completer"] = create_completer(
            kw["get_globals"],
            kw["get_globals"],
            ipython_shell.magics_manager,
            ipython_shell.alias_manager,
            lambda: self.enable_dictionary_completion,
        )
        kw["_lexer"] = create_lexer()
        kw["_validator"] = IPythonValidator(get_compiler_flags=self.get_compiler_flags)

        super().__init__(*a, **kw)
        self.ipython_shell = ipython_shell

        self.all_prompt_styles["ipython"] = IPythonPrompt(ipython_shell.prompts)
        self.prompt_style = "ipython"

        # UI style for IPython. Add tokens that are used by IPython>5.0
        style_dict = {}
        style_dict.update(default_ui_style)
        style_dict.update(
            {
                "pygments.prompt": "#009900",
                "pygments.prompt-num": "#00ff00 bold",
                "pygments.out-prompt": "#990000",
                "pygments.out-prompt-num": "#ff0000 bold",
            }
        )

        self.ui_styles = {"default": Style.from_dict(style_dict)}
        self.use_ui_colorscheme("default")

    def get_compiler_flags(self):
        flags = super().get_compiler_flags()
        if self.ipython_shell.autoawait:
            flags |= PyCF_ALLOW_TOP_LEVEL_AWAIT
        return flags


class InteractiveShellEmbed(_InteractiveShellEmbed):
    """
    Override the `InteractiveShellEmbed` from IPython, to replace the front-end
    with our input shell.

    :param configure: Callable for configuring the repl.
    """

    def __init__(self, *a, **kw):
        vi_mode = kw.pop("vi_mode", False)
        history_filename = kw.pop("history_filename", None)
        configure = kw.pop("configure", None)
        title = kw.pop("title", None)

        # Don't ask IPython to confirm for exit. We have our own exit prompt.
        self.confirm_exit = False

        super().__init__(*a, **kw)

        def get_globals():
            return self.user_ns

        python_input = IPythonInput(
            self,
            get_globals=get_globals,
            vi_mode=vi_mode,
            history_filename=history_filename,
        )

        if title:
            python_input.terminal_title = title

        if configure:
            configure(python_input)
            python_input.prompt_style = "ipython"  # Don't take from config.

        self.python_input = python_input

    def prompt_for_code(self) -> str:
        try:
            return self.python_input.app.run()
        except KeyboardInterrupt:
            self.python_input.default_buffer.document = Document()
            return ""


def initialize_extensions(shell, extensions):
    """
    Partial copy of `InteractiveShellApp.init_extensions` from IPython.
    """
    try:
        iter(extensions)
    except TypeError:
        pass  # no extensions found
    else:
        for ext in extensions:
            try:
                shell.extension_manager.load_extension(ext)
            except:
                warn(
                    f"Error in loading extension: {ext}"
                    + f"\nCheck your config files in {ipy_utils.path.get_ipython_dir()}"
                )
                shell.showtraceback()


def run_exec_lines(shell, exec_lines):
    """
    Partial copy of  run_exec_lines code from IPython.core.shellapp .
    """
    try:
        iter(exec_lines)
    except TypeError:
        pass
    else:
        try:
            for line in exec_lines:
                try:
                    shell.run_cell(line, store_history=False)
                except:
                    shell.showtraceback()
        except:
            shell.showtraceback()


def embed(**kwargs):
    """
    Copied from `IPython/terminal/embed.py`, but using our `InteractiveShellEmbed` instead.
    """
    config = kwargs.get("config")
    header = kwargs.pop("header", "")
    compile_flags = kwargs.pop("compile_flags", None)
    if config is None:
        config = load_default_config()
        config.InteractiveShellEmbed = config.TerminalInteractiveShell
        kwargs["config"] = config
    shell = InteractiveShellEmbed.instance(**kwargs)
    initialize_extensions(shell, config["InteractiveShellApp"]["extensions"])
    run_exec_lines(shell, config["InteractiveShellApp"]["exec_lines"])
    run_startup_scripts(shell)
    shell(header=header, stack_depth=2, compile_flags=compile_flags)


def run_startup_scripts(shell):
    """
    Contributed by linyuxu:
    https://github.com/prompt-toolkit/ptpython/issues/126#issue-161242480
    """
    import glob
    import os

    startup_dir = shell.profile_dir.startup_dir
    startup_files = []
    startup_files += glob.glob(os.path.join(startup_dir, "*.py"))
    startup_files += glob.glob(os.path.join(startup_dir, "*.ipy"))
    for file in startup_files:
        shell.run_cell(open(file).read())
