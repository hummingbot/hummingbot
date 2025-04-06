from __future__ import annotations

from typing import Callable

from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.lexers import Lexer, PygmentsLexer
from pygments.lexers import BashLexer
from pygments.lexers import Python3Lexer as PythonLexer

__all__ = ["PtpythonLexer"]


class PtpythonLexer(Lexer):
    """
    Lexer for ptpython input.

    If the input starts with an exclamation mark, use a Bash lexer, otherwise,
    use a Python 3 lexer.
    """

    def __init__(self, python_lexer: Lexer | None = None) -> None:
        self.python_lexer = python_lexer or PygmentsLexer(PythonLexer)
        self.system_lexer = PygmentsLexer(BashLexer)

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:
        if document.text.startswith("!"):
            return self.system_lexer.lex_document(document)

        return self.python_lexer.lex_document(document)
