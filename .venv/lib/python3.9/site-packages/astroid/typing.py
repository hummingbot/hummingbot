# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from astroid import bases, exceptions, nodes, transforms, util
    from astroid.context import InferenceContext
    from astroid.interpreter._import import spec


class InferenceErrorInfo(TypedDict):
    """Store additional Inference error information
    raised with StopIteration exception.
    """

    node: nodes.NodeNG
    context: InferenceContext | None


class AstroidManagerBrain(TypedDict):
    """Dictionary to store relevant information for a AstroidManager class."""

    astroid_cache: dict[str, nodes.Module]
    _mod_file_cache: dict[
        tuple[str, str | None], spec.ModuleSpec | exceptions.AstroidImportError
    ]
    _failed_import_hooks: list[Callable[[str], nodes.Module]]
    always_load_extensions: bool
    optimize_ast: bool
    max_inferable_values: int
    extension_package_whitelist: set[str]
    _transform: transforms.TransformVisitor


InferenceResult = Union["nodes.NodeNG", "util.UninferableBase", "bases.Proxy"]
SuccessfulInferenceResult = Union["nodes.NodeNG", "bases.Proxy"]
_SuccessfulInferenceResultT = TypeVar(
    "_SuccessfulInferenceResultT", bound=SuccessfulInferenceResult
)
_SuccessfulInferenceResultT_contra = TypeVar(
    "_SuccessfulInferenceResultT_contra",
    bound=SuccessfulInferenceResult,
    contravariant=True,
)

ConstFactoryResult = Union[
    "nodes.List",
    "nodes.Set",
    "nodes.Tuple",
    "nodes.Dict",
    "nodes.Const",
    "nodes.EmptyNode",
]

InferBinaryOp = Callable[
    [
        _SuccessfulInferenceResultT,
        Union["nodes.AugAssign", "nodes.BinOp"],
        str,
        InferenceResult,
        "InferenceContext",
        SuccessfulInferenceResult,
    ],
    Generator[InferenceResult],
]


class InferFn(Protocol, Generic[_SuccessfulInferenceResultT_contra]):
    def __call__(
        self,
        node: _SuccessfulInferenceResultT_contra,
        context: InferenceContext | None = None,
        **kwargs: Any,
    ) -> Iterator[InferenceResult]: ...  # pragma: no cover


class TransformFn(Protocol, Generic[_SuccessfulInferenceResultT]):
    def __call__(
        self,
        node: _SuccessfulInferenceResultT,
        infer_function: InferFn[_SuccessfulInferenceResultT] = ...,
    ) -> _SuccessfulInferenceResultT | None: ...  # pragma: no cover
