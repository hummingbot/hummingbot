# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt


from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Final, Literal

from astroid.exceptions import InferenceError

if TYPE_CHECKING:
    from astroid import bases, nodes
    from astroid.context import InferenceContext
    from astroid.typing import InferenceResult


class UninferableBase:
    """Special inference object, which is returned when inference fails.

    This is meant to be used as a singleton. Use astroid.util.Uninferable to access it.
    """

    def __repr__(self) -> Literal["Uninferable"]:
        return "Uninferable"

    __str__ = __repr__

    def __getattribute__(self, name: str) -> Any:
        if name == "next":
            raise AttributeError("next method should not be called")
        if name.startswith("__") and name.endswith("__"):
            return object.__getattribute__(self, name)
        if name == "accept":
            return object.__getattribute__(self, name)
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> UninferableBase:
        return self

    def __bool__(self) -> Literal[False]:
        return False

    __nonzero__ = __bool__

    def accept(self, visitor):
        return visitor.visit_uninferable(self)


Uninferable: Final = UninferableBase()


class BadOperationMessage:
    """Object which describes a TypeError occurred somewhere in the inference chain.

    This is not an exception, but a container object which holds the types and
    the error which occurred.
    """


class BadUnaryOperationMessage(BadOperationMessage):
    """Object which describes operational failures on UnaryOps."""

    def __init__(self, operand, op, error):
        self.operand = operand
        self.op = op
        self.error = error

    @property
    def _object_type_helper(self):
        from astroid import helpers  # pylint: disable=import-outside-toplevel

        return helpers.object_type

    def _object_type(self, obj):
        objtype = self._object_type_helper(obj)
        if isinstance(objtype, UninferableBase):
            return None

        return objtype

    def __str__(self) -> str:
        if hasattr(self.operand, "name"):
            operand_type = self.operand.name
        else:
            object_type = self._object_type(self.operand)
            if hasattr(object_type, "name"):
                operand_type = object_type.name
            else:
                # Just fallback to as_string
                operand_type = object_type.as_string()

        msg = "bad operand type for unary {}: {}"
        return msg.format(self.op, operand_type)


class BadBinaryOperationMessage(BadOperationMessage):
    """Object which describes type errors for BinOps."""

    def __init__(self, left_type, op, right_type):
        self.left_type = left_type
        self.right_type = right_type
        self.op = op

    def __str__(self) -> str:
        msg = "unsupported operand type(s) for {}: {!r} and {!r}"
        return msg.format(self.op, self.left_type.name, self.right_type.name)


def _instancecheck(cls, other) -> bool:
    wrapped = cls.__wrapped__
    other_cls = other.__class__
    is_instance_of = wrapped is other_cls or issubclass(other_cls, wrapped)
    warnings.warn(
        "%r is deprecated and slated for removal in astroid "
        "2.0, use %r instead" % (cls.__class__.__name__, wrapped.__name__),
        PendingDeprecationWarning,
        stacklevel=2,
    )
    return is_instance_of


def check_warnings_filter() -> bool:
    """Return True if any other than the default DeprecationWarning filter is enabled.

    https://docs.python.org/3/library/warnings.html#default-warning-filter
    """
    return any(
        issubclass(DeprecationWarning, filter[2])
        and filter[0] != "ignore"
        and filter[3] != "__main__"
        for filter in warnings.filters
    )


def safe_infer(
    node: nodes.NodeNG | bases.Proxy | UninferableBase,
    context: InferenceContext | None = None,
) -> InferenceResult | None:
    """Return the inferred value for the given node.

    Return None if inference failed or if there is some ambiguity (more than
    one node has been inferred).
    """
    if isinstance(node, UninferableBase):
        return node
    try:
        inferit = node.infer(context=context)
        value = next(inferit)
    except (InferenceError, StopIteration):
        return None
    try:
        next(inferit)
        return None  # None if there is ambiguity on the inferred node
    except InferenceError:
        return None  # there is some kind of ambiguity
    except StopIteration:
        return value
