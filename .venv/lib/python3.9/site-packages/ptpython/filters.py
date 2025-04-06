from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Filter

if TYPE_CHECKING:
    from .python_input import PythonInput

__all__ = ["HasSignature", "ShowSidebar", "ShowSignature", "ShowDocstring"]


class PythonInputFilter(Filter):
    def __init__(self, python_input: PythonInput) -> None:
        super().__init__()
        self.python_input = python_input

    def __call__(self) -> bool:
        raise NotImplementedError


class HasSignature(PythonInputFilter):
    def __call__(self) -> bool:
        return bool(self.python_input.signatures)


class ShowSidebar(PythonInputFilter):
    def __call__(self) -> bool:
        return self.python_input.show_sidebar


class ShowSignature(PythonInputFilter):
    def __call__(self) -> bool:
        return self.python_input.show_signature


class ShowDocstring(PythonInputFilter):
    def __call__(self) -> bool:
        return self.python_input.show_docstring
