# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Module for some node classes. More nodes in scoped_nodes.py"""

from __future__ import annotations

import abc
import ast
import itertools
import operator
import sys
import typing
import warnings
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    Optional,
    Union,
)

from astroid import decorators, protocols, util
from astroid.bases import Instance, _infer_stmts
from astroid.const import _EMPTY_OBJECT_MARKER, Context
from astroid.context import CallContext, InferenceContext, copy_context
from astroid.exceptions import (
    AstroidBuildingError,
    AstroidError,
    AstroidIndexError,
    AstroidTypeError,
    AstroidValueError,
    AttributeInferenceError,
    InferenceError,
    NameInferenceError,
    NoDefault,
    ParentMissingError,
    _NonDeducibleTypeHierarchy,
)
from astroid.interpreter import dunder_lookup
from astroid.manager import AstroidManager
from astroid.nodes import _base_nodes
from astroid.nodes.const import OP_PRECEDENCE
from astroid.nodes.node_ng import NodeNG
from astroid.typing import (
    ConstFactoryResult,
    InferenceErrorInfo,
    InferenceResult,
    SuccessfulInferenceResult,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from astroid import nodes
    from astroid.nodes import LocalsDictNodeNG


def _is_const(value) -> bool:
    return isinstance(value, tuple(CONST_CLS))


_NodesT = typing.TypeVar("_NodesT", bound=NodeNG)
_BadOpMessageT = typing.TypeVar("_BadOpMessageT", bound=util.BadOperationMessage)

AssignedStmtsPossibleNode = Union["List", "Tuple", "AssignName", "AssignAttr", None]
AssignedStmtsCall = Callable[
    [
        _NodesT,
        AssignedStmtsPossibleNode,
        Optional[InferenceContext],
        Optional[list[int]],
    ],
    Any,
]
InferBinaryOperation = Callable[
    [_NodesT, Optional[InferenceContext]],
    Generator[Union[InferenceResult, _BadOpMessageT]],
]
InferLHS = Callable[
    [_NodesT, Optional[InferenceContext]],
    Generator[InferenceResult, None, Optional[InferenceErrorInfo]],
]
InferUnaryOp = Callable[[_NodesT, str], ConstFactoryResult]


@decorators.raise_if_nothing_inferred
def unpack_infer(stmt, context: InferenceContext | None = None):
    """recursively generate nodes inferred by the given statement.
    If the inferred value is a list or a tuple, recurse on the elements
    """
    if isinstance(stmt, (List, Tuple)):
        for elt in stmt.elts:
            if elt is util.Uninferable:
                yield elt
                continue
            yield from unpack_infer(elt, context)
        return {"node": stmt, "context": context}
    # if inferred is a final node, return it and stop
    inferred = next(stmt.infer(context), util.Uninferable)
    if inferred is stmt:
        yield inferred
        return {"node": stmt, "context": context}
    # else, infer recursively, except Uninferable object that should be returned as is
    for inferred in stmt.infer(context):
        if isinstance(inferred, util.UninferableBase):
            yield inferred
        else:
            yield from unpack_infer(inferred, context)

    return {"node": stmt, "context": context}


def are_exclusive(stmt1, stmt2, exceptions: list[str] | None = None) -> bool:
    """return true if the two given statements are mutually exclusive

    `exceptions` may be a list of exception names. If specified, discard If
    branches and check one of the statement is in an exception handler catching
    one of the given exceptions.

    algorithm :
     1) index stmt1's parents
     2) climb among stmt2's parents until we find a common parent
     3) if the common parent is a If or Try statement, look if nodes are
        in exclusive branches
    """
    # index stmt1's parents
    stmt1_parents = {}
    children = {}
    previous = stmt1
    for node in stmt1.node_ancestors():
        stmt1_parents[node] = 1
        children[node] = previous
        previous = node
    # climb among stmt2's parents until we find a common parent
    previous = stmt2
    for node in stmt2.node_ancestors():
        if node in stmt1_parents:
            # if the common parent is a If or Try statement, look if
            # nodes are in exclusive branches
            if isinstance(node, If) and exceptions is None:
                c2attr, c2node = node.locate_child(previous)
                c1attr, c1node = node.locate_child(children[node])
                if "test" in (c1attr, c2attr):
                    # If any node is `If.test`, then it must be inclusive with
                    # the other node (`If.body` and `If.orelse`)
                    return False
                if c1attr != c2attr:
                    # different `If` branches (`If.body` and `If.orelse`)
                    return True
            elif isinstance(node, Try):
                c2attr, c2node = node.locate_child(previous)
                c1attr, c1node = node.locate_child(children[node])
                if c1node is not c2node:
                    first_in_body_caught_by_handlers = (
                        c2attr == "handlers"
                        and c1attr == "body"
                        and previous.catch(exceptions)
                    )
                    second_in_body_caught_by_handlers = (
                        c2attr == "body"
                        and c1attr == "handlers"
                        and children[node].catch(exceptions)
                    )
                    first_in_else_other_in_handlers = (
                        c2attr == "handlers" and c1attr == "orelse"
                    )
                    second_in_else_other_in_handlers = (
                        c2attr == "orelse" and c1attr == "handlers"
                    )
                    if any(
                        (
                            first_in_body_caught_by_handlers,
                            second_in_body_caught_by_handlers,
                            first_in_else_other_in_handlers,
                            second_in_else_other_in_handlers,
                        )
                    ):
                        return True
                elif c2attr == "handlers" and c1attr == "handlers":
                    return previous is not children[node]
            return False
        previous = node
    return False


# getitem() helpers.

_SLICE_SENTINEL = object()


def _slice_value(index, context: InferenceContext | None = None):
    """Get the value of the given slice index."""

    if isinstance(index, Const):
        if isinstance(index.value, (int, type(None))):
            return index.value
    elif index is None:
        return None
    else:
        # Try to infer what the index actually is.
        # Since we can't return all the possible values,
        # we'll stop at the first possible value.
        try:
            inferred = next(index.infer(context=context))
        except (InferenceError, StopIteration):
            pass
        else:
            if isinstance(inferred, Const):
                if isinstance(inferred.value, (int, type(None))):
                    return inferred.value

    # Use a sentinel, because None can be a valid
    # value that this function can return,
    # as it is the case for unspecified bounds.
    return _SLICE_SENTINEL


def _infer_slice(node, context: InferenceContext | None = None):
    lower = _slice_value(node.lower, context)
    upper = _slice_value(node.upper, context)
    step = _slice_value(node.step, context)
    if all(elem is not _SLICE_SENTINEL for elem in (lower, upper, step)):
        return slice(lower, upper, step)

    raise AstroidTypeError(
        message="Could not infer slice used in subscript",
        node=node,
        index=node.parent,
        context=context,
    )


def _container_getitem(instance, elts, index, context: InferenceContext | None = None):
    """Get a slice or an item, using the given *index*, for the given sequence."""
    try:
        if isinstance(index, Slice):
            index_slice = _infer_slice(index, context=context)
            new_cls = instance.__class__()
            new_cls.elts = elts[index_slice]
            new_cls.parent = instance.parent
            return new_cls
        if isinstance(index, Const):
            return elts[index.value]
    except ValueError as exc:
        raise AstroidValueError(
            message="Slice {index!r} cannot index container",
            node=instance,
            index=index,
            context=context,
        ) from exc
    except IndexError as exc:
        raise AstroidIndexError(
            message="Index {index!s} out of range",
            node=instance,
            index=index,
            context=context,
        ) from exc
    except TypeError as exc:
        raise AstroidTypeError(
            message="Type error {error!r}", node=instance, index=index, context=context
        ) from exc

    raise AstroidTypeError(f"Could not use {index} as subscript index")


class BaseContainer(_base_nodes.ParentAssignNode, Instance, metaclass=abc.ABCMeta):
    """Base class for Set, FrozenSet, Tuple and List."""

    _astroid_fields = ("elts",)

    def __init__(
        self,
        lineno: int | None,
        col_offset: int | None,
        parent: NodeNG | None,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.elts: list[SuccessfulInferenceResult] = []
        """The elements in the node."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, elts: list[SuccessfulInferenceResult]) -> None:
        self.elts = elts

    @classmethod
    def from_elements(cls, elts: Iterable[Any]) -> Self:
        """Create a node of this type from the given list of elements.

        :param elts: The list of elements that the node should contain.

        :returns: A new node containing the given elements.
        """
        node = cls(
            lineno=None,
            col_offset=None,
            parent=None,
            end_lineno=None,
            end_col_offset=None,
        )
        node.elts = [const_factory(e) if _is_const(e) else e for e in elts]
        return node

    def itered(self):
        """An iterator over the elements this node contains.

        :returns: The contents of this node.
        :rtype: iterable(NodeNG)
        """
        return self.elts

    def bool_value(self, context: InferenceContext | None = None) -> bool:
        """Determine the boolean value of this node.

        :returns: The boolean value of this node.
        """
        return bool(self.elts)

    @abc.abstractmethod
    def pytype(self) -> str:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """

    def get_children(self):
        yield from self.elts

    @decorators.raise_if_nothing_inferred
    def _infer(
        self,
        context: InferenceContext | None = None,
        **kwargs: Any,
    ) -> Iterator[Self]:
        has_starred_named_expr = any(
            isinstance(e, (Starred, NamedExpr)) for e in self.elts
        )
        if has_starred_named_expr:
            values = self._infer_sequence_helper(context)
            new_seq = type(self)(
                lineno=self.lineno,
                col_offset=self.col_offset,
                parent=self.parent,
                end_lineno=self.end_lineno,
                end_col_offset=self.end_col_offset,
            )
            new_seq.postinit(values)

            yield new_seq
        else:
            yield self

    def _infer_sequence_helper(
        self, context: InferenceContext | None = None
    ) -> list[SuccessfulInferenceResult]:
        """Infer all values based on BaseContainer.elts."""
        values = []

        for elt in self.elts:
            if isinstance(elt, Starred):
                starred = util.safe_infer(elt.value, context)
                if not starred:
                    raise InferenceError(node=self, context=context)
                if not hasattr(starred, "elts"):
                    raise InferenceError(node=self, context=context)
                # TODO: fresh context?
                values.extend(starred._infer_sequence_helper(context))
            elif isinstance(elt, NamedExpr):
                value = util.safe_infer(elt.value, context)
                if not value:
                    raise InferenceError(node=self, context=context)
                values.append(value)
            else:
                values.append(elt)
        return values


# Name classes


class AssignName(
    _base_nodes.NoChildrenNode,
    _base_nodes.LookupMixIn,
    _base_nodes.ParentAssignNode,
):
    """Variation of :class:`ast.Assign` representing assignment to a name.

    An :class:`AssignName` is the name of something that is assigned to.
    This includes variables defined in a function signature or in a loop.

    >>> import astroid
    >>> node = astroid.extract_node('variable = range(10)')
    >>> node
    <Assign l.1 at 0x7effe1db8550>
    >>> list(node.get_children())
    [<AssignName.variable l.1 at 0x7effe1db8748>, <Call l.1 at 0x7effe1db8630>]
    >>> list(node.get_children())[0].as_string()
    'variable'
    """

    _other_fields = ("name",)

    def __init__(
        self,
        name: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.name = name
        """The name that is assigned to."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    assigned_stmts = protocols.assend_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """Infer an AssignName: need to inspect the RHS part of the
        assign node.
        """
        if isinstance(self.parent, AugAssign):
            return self.parent.infer(context)

        stmts = list(self.assigned_stmts(context=context))
        return _infer_stmts(stmts, context)

    @decorators.raise_if_nothing_inferred
    def infer_lhs(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """Infer a Name: use name lookup rules.

        Same implementation as Name._infer."""
        # pylint: disable=import-outside-toplevel
        from astroid.constraint import get_constraints
        from astroid.helpers import _higher_function_scope

        frame, stmts = self.lookup(self.name)
        if not stmts:
            # Try to see if the name is enclosed in a nested function
            # and use the higher (first function) scope for searching.
            parent_function = _higher_function_scope(self.scope())
            if parent_function:
                _, stmts = parent_function.lookup(self.name)

            if not stmts:
                raise NameInferenceError(
                    name=self.name, scope=self.scope(), context=context
                )
        context = copy_context(context)
        context.lookupname = self.name
        context.constraints[self.name] = get_constraints(self, frame)

        return _infer_stmts(stmts, context, frame)


class DelName(
    _base_nodes.NoChildrenNode, _base_nodes.LookupMixIn, _base_nodes.ParentAssignNode
):
    """Variation of :class:`ast.Delete` representing deletion of a name.

    A :class:`DelName` is the name of something that is deleted.

    >>> import astroid
    >>> node = astroid.extract_node("del variable #@")
    >>> list(node.get_children())
    [<DelName.variable l.1 at 0x7effe1da4d30>]
    >>> list(node.get_children())[0].as_string()
    'variable'
    """

    _other_fields = ("name",)

    def __init__(
        self,
        name: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.name = name
        """The name that is being deleted."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )


class Name(_base_nodes.LookupMixIn, _base_nodes.NoChildrenNode):
    """Class representing an :class:`ast.Name` node.

    A :class:`Name` node is something that is named, but not covered by
    :class:`AssignName` or :class:`DelName`.

    >>> import astroid
    >>> node = astroid.extract_node('range(10)')
    >>> node
    <Call l.1 at 0x7effe1db8710>
    >>> list(node.get_children())
    [<Name.range l.1 at 0x7effe1db86a0>, <Const.int l.1 at 0x7effe1db8518>]
    >>> list(node.get_children())[0].as_string()
    'range'
    """

    _other_fields = ("name",)

    def __init__(
        self,
        name: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.name = name
        """The name that this node refers to."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def _get_name_nodes(self):
        yield self

        for child_node in self.get_children():
            yield from child_node._get_name_nodes()

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """Infer a Name: use name lookup rules

        Same implementation as AssignName._infer_lhs."""
        # pylint: disable=import-outside-toplevel
        from astroid.constraint import get_constraints
        from astroid.helpers import _higher_function_scope

        frame, stmts = self.lookup(self.name)
        if not stmts:
            # Try to see if the name is enclosed in a nested function
            # and use the higher (first function) scope for searching.
            parent_function = _higher_function_scope(self.scope())
            if parent_function:
                _, stmts = parent_function.lookup(self.name)

            if not stmts:
                raise NameInferenceError(
                    name=self.name, scope=self.scope(), context=context
                )
        context = copy_context(context)
        context.lookupname = self.name
        context.constraints[self.name] = get_constraints(self, frame)

        return _infer_stmts(stmts, context, frame)


DEPRECATED_ARGUMENT_DEFAULT = "DEPRECATED_ARGUMENT_DEFAULT"


class Arguments(
    _base_nodes.AssignTypeNode
):  # pylint: disable=too-many-instance-attributes
    """Class representing an :class:`ast.arguments` node.

    An :class:`Arguments` node represents that arguments in a
    function definition.

    >>> import astroid
    >>> node = astroid.extract_node('def foo(bar): pass')
    >>> node
    <FunctionDef.foo l.1 at 0x7effe1db8198>
    >>> node.args
    <Arguments l.1 at 0x7effe1db82e8>
    """

    # Python 3.4+ uses a different approach regarding annotations,
    # each argument is a new class, _ast.arg, which exposes an
    # 'annotation' attribute. In astroid though, arguments are exposed
    # as is in the Arguments node and the only way to expose annotations
    # is by using something similar with Python 3.3:
    #  - we expose 'varargannotation' and 'kwargannotation' of annotations
    #    of varargs and kwargs.
    #  - we expose 'annotation', a list with annotations for
    #    for each normal argument. If an argument doesn't have an
    #    annotation, its value will be None.
    _astroid_fields = (
        "args",
        "defaults",
        "kwonlyargs",
        "posonlyargs",
        "posonlyargs_annotations",
        "kw_defaults",
        "annotations",
        "varargannotation",
        "kwargannotation",
        "kwonlyargs_annotations",
        "type_comment_args",
        "type_comment_kwonlyargs",
        "type_comment_posonlyargs",
    )

    _other_fields = ("vararg", "kwarg")

    args: list[AssignName] | None
    """The names of the required arguments.

    Can be None if the associated function does not have a retrievable
    signature and the arguments are therefore unknown.
    This can happen with (builtin) functions implemented in C that have
    incomplete signature information.
    """

    defaults: list[NodeNG] | None
    """The default values for arguments that can be passed positionally."""

    kwonlyargs: list[AssignName]
    """The keyword arguments that cannot be passed positionally."""

    posonlyargs: list[AssignName]
    """The arguments that can only be passed positionally."""

    kw_defaults: list[NodeNG | None] | None
    """The default values for keyword arguments that cannot be passed positionally."""

    annotations: list[NodeNG | None]
    """The type annotations of arguments that can be passed positionally."""

    posonlyargs_annotations: list[NodeNG | None]
    """The type annotations of arguments that can only be passed positionally."""

    kwonlyargs_annotations: list[NodeNG | None]
    """The type annotations of arguments that cannot be passed positionally."""

    type_comment_args: list[NodeNG | None]
    """The type annotation, passed by a type comment, of each argument.

    If an argument does not have a type comment,
    the value for that argument will be None.
    """

    type_comment_kwonlyargs: list[NodeNG | None]
    """The type annotation, passed by a type comment, of each keyword only argument.

    If an argument does not have a type comment,
    the value for that argument will be None.
    """

    type_comment_posonlyargs: list[NodeNG | None]
    """The type annotation, passed by a type comment, of each positional argument.

    If an argument does not have a type comment,
    the value for that argument will be None.
    """

    varargannotation: NodeNG | None
    """The type annotation for the variable length arguments."""

    kwargannotation: NodeNG | None
    """The type annotation for the variable length keyword arguments."""

    vararg_node: AssignName | None
    """The node for variable length arguments"""

    kwarg_node: AssignName | None
    """The node for variable keyword arguments"""

    def __init__(
        self,
        vararg: str | None,
        kwarg: str | None,
        parent: NodeNG,
        vararg_node: AssignName | None = None,
        kwarg_node: AssignName | None = None,
    ) -> None:
        """Almost all attributes can be None for living objects where introspection failed."""
        super().__init__(
            parent=parent,
            lineno=None,
            col_offset=None,
            end_lineno=None,
            end_col_offset=None,
        )

        self.vararg = vararg
        """The name of the variable length arguments."""

        self.kwarg = kwarg
        """The name of the variable length keyword arguments."""

        self.vararg_node = vararg_node
        self.kwarg_node = kwarg_node

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def postinit(
        self,
        args: list[AssignName] | None,
        defaults: list[NodeNG] | None,
        kwonlyargs: list[AssignName],
        kw_defaults: list[NodeNG | None] | None,
        annotations: list[NodeNG | None],
        posonlyargs: list[AssignName],
        kwonlyargs_annotations: list[NodeNG | None],
        posonlyargs_annotations: list[NodeNG | None],
        varargannotation: NodeNG | None = None,
        kwargannotation: NodeNG | None = None,
        type_comment_args: list[NodeNG | None] | None = None,
        type_comment_kwonlyargs: list[NodeNG | None] | None = None,
        type_comment_posonlyargs: list[NodeNG | None] | None = None,
    ) -> None:
        self.args = args
        self.defaults = defaults
        self.kwonlyargs = kwonlyargs
        self.posonlyargs = posonlyargs
        self.kw_defaults = kw_defaults
        self.annotations = annotations
        self.kwonlyargs_annotations = kwonlyargs_annotations
        self.posonlyargs_annotations = posonlyargs_annotations

        # Parameters that got added later and need a default
        self.varargannotation = varargannotation
        self.kwargannotation = kwargannotation
        if type_comment_args is None:
            type_comment_args = []
        self.type_comment_args = type_comment_args
        if type_comment_kwonlyargs is None:
            type_comment_kwonlyargs = []
        self.type_comment_kwonlyargs = type_comment_kwonlyargs
        if type_comment_posonlyargs is None:
            type_comment_posonlyargs = []
        self.type_comment_posonlyargs = type_comment_posonlyargs

    assigned_stmts = protocols.arguments_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def _infer_name(self, frame, name):
        if self.parent is frame:
            return name
        return None

    @cached_property
    def fromlineno(self) -> int:
        """The first line that this node appears on in the source code.

        Can also return 0 if the line can not be determined.
        """
        lineno = super().fromlineno
        return max(lineno, self.parent.fromlineno or 0)

    @cached_property
    def arguments(self):
        """Get all the arguments for this node. This includes:
        * Positional only arguments
        * Positional arguments
        * Keyword arguments
        * Variable arguments (.e.g *args)
        * Variable keyword arguments (e.g **kwargs)
        """
        retval = list(itertools.chain((self.posonlyargs or ()), (self.args or ())))
        if self.vararg_node:
            retval.append(self.vararg_node)
        retval += self.kwonlyargs or ()
        if self.kwarg_node:
            retval.append(self.kwarg_node)

        return retval

    def format_args(self, *, skippable_names: set[str] | None = None) -> str:
        """Get the arguments formatted as string.

        :returns: The formatted arguments.
        :rtype: str
        """
        result = []
        positional_only_defaults = []
        positional_or_keyword_defaults = self.defaults
        if self.defaults:
            args = self.args or []
            positional_or_keyword_defaults = self.defaults[-len(args) :]
            positional_only_defaults = self.defaults[: len(self.defaults) - len(args)]

        if self.posonlyargs:
            result.append(
                _format_args(
                    self.posonlyargs,
                    positional_only_defaults,
                    self.posonlyargs_annotations,
                    skippable_names=skippable_names,
                )
            )
            result.append("/")
        if self.args:
            result.append(
                _format_args(
                    self.args,
                    positional_or_keyword_defaults,
                    getattr(self, "annotations", None),
                    skippable_names=skippable_names,
                )
            )
        if self.vararg:
            result.append(f"*{self.vararg}")
        if self.kwonlyargs:
            if not self.vararg:
                result.append("*")
            result.append(
                _format_args(
                    self.kwonlyargs,
                    self.kw_defaults,
                    self.kwonlyargs_annotations,
                    skippable_names=skippable_names,
                )
            )
        if self.kwarg:
            result.append(f"**{self.kwarg}")
        return ", ".join(result)

    def _get_arguments_data(
        self,
    ) -> tuple[
        dict[str, tuple[str | None, str | None]],
        dict[str, tuple[str | None, str | None]],
    ]:
        """Get the arguments as dictionary with information about typing and defaults.

        The return tuple contains a dictionary for positional and keyword arguments with their typing
        and their default value, if any.
        The method follows a similar order as format_args but instead of formatting into a string it
        returns the data that is used to do so.
        """
        pos_only: dict[str, tuple[str | None, str | None]] = {}
        kw_only: dict[str, tuple[str | None, str | None]] = {}

        # Setup and match defaults with arguments
        positional_only_defaults = []
        positional_or_keyword_defaults = self.defaults
        if self.defaults:
            args = self.args or []
            positional_or_keyword_defaults = self.defaults[-len(args) :]
            positional_only_defaults = self.defaults[: len(self.defaults) - len(args)]

        for index, posonly in enumerate(self.posonlyargs):
            annotation, default = self.posonlyargs_annotations[index], None
            if annotation is not None:
                annotation = annotation.as_string()
            if positional_only_defaults:
                default = positional_only_defaults[index].as_string()
            pos_only[posonly.name] = (annotation, default)

        for index, arg in enumerate(self.args):
            annotation, default = self.annotations[index], None
            if annotation is not None:
                annotation = annotation.as_string()
            if positional_or_keyword_defaults:
                defaults_offset = len(self.args) - len(positional_or_keyword_defaults)
                default_index = index - defaults_offset
                if (
                    default_index > -1
                    and positional_or_keyword_defaults[default_index] is not None
                ):
                    default = positional_or_keyword_defaults[default_index].as_string()
            pos_only[arg.name] = (annotation, default)

        if self.vararg:
            annotation = self.varargannotation
            if annotation is not None:
                annotation = annotation.as_string()
            pos_only[self.vararg] = (annotation, None)

        for index, kwarg in enumerate(self.kwonlyargs):
            annotation = self.kwonlyargs_annotations[index]
            if annotation is not None:
                annotation = annotation.as_string()
            default = self.kw_defaults[index]
            if default is not None:
                default = default.as_string()
            kw_only[kwarg.name] = (annotation, default)

        if self.kwarg:
            annotation = self.kwargannotation
            if annotation is not None:
                annotation = annotation.as_string()
            kw_only[self.kwarg] = (annotation, None)

        return pos_only, kw_only

    def default_value(self, argname):
        """Get the default value for an argument.

        :param argname: The name of the argument to get the default value for.
        :type argname: str

        :raises NoDefault: If there is no default value defined for the
            given argument.
        """
        args = [
            arg for arg in self.arguments if arg.name not in [self.vararg, self.kwarg]
        ]

        index = _find_arg(argname, self.kwonlyargs)[0]
        if (index is not None) and (len(self.kw_defaults) > index):
            if self.kw_defaults[index] is not None:
                return self.kw_defaults[index]
            raise NoDefault(func=self.parent, name=argname)

        index = _find_arg(argname, args)[0]
        if index is not None:
            idx = index - (len(args) - len(self.defaults) - len(self.kw_defaults))
            if idx >= 0:
                return self.defaults[idx]

        raise NoDefault(func=self.parent, name=argname)

    def is_argument(self, name) -> bool:
        """Check if the given name is defined in the arguments.

        :param name: The name to check for.
        :type name: str

        :returns: Whether the given name is defined in the arguments,
        """
        if name == self.vararg:
            return True
        if name == self.kwarg:
            return True
        return self.find_argname(name)[1] is not None

    def find_argname(self, argname, rec=DEPRECATED_ARGUMENT_DEFAULT):
        """Get the index and :class:`AssignName` node for given name.

        :param argname: The name of the argument to search for.
        :type argname: str

        :returns: The index and node for the argument.
        :rtype: tuple(str or None, AssignName or None)
        """
        if rec != DEPRECATED_ARGUMENT_DEFAULT:  # pragma: no cover
            warnings.warn(
                "The rec argument will be removed in astroid 3.1.",
                DeprecationWarning,
                stacklevel=2,
            )
        if self.arguments:
            index, argument = _find_arg(argname, self.arguments)
            if argument:
                return index, argument
        return None, None

    def get_children(self):
        yield from self.posonlyargs or ()

        for elt in self.posonlyargs_annotations:
            if elt is not None:
                yield elt

        yield from self.args or ()

        if self.defaults is not None:
            yield from self.defaults
        yield from self.kwonlyargs

        for elt in self.kw_defaults or ():
            if elt is not None:
                yield elt

        for elt in self.annotations:
            if elt is not None:
                yield elt

        if self.varargannotation is not None:
            yield self.varargannotation

        if self.kwargannotation is not None:
            yield self.kwargannotation

        for elt in self.kwonlyargs_annotations:
            if elt is not None:
                yield elt

    @decorators.raise_if_nothing_inferred
    def _infer(
        self: nodes.Arguments, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        # pylint: disable-next=import-outside-toplevel
        from astroid.protocols import _arguments_infer_argname

        if context is None or context.lookupname is None:
            raise InferenceError(node=self, context=context)
        return _arguments_infer_argname(self, context.lookupname, context)


def _find_arg(argname, args):
    for i, arg in enumerate(args):
        if arg.name == argname:
            return i, arg
    return None, None


def _format_args(
    args, defaults=None, annotations=None, skippable_names: set[str] | None = None
) -> str:
    if skippable_names is None:
        skippable_names = set()
    values = []
    if args is None:
        return ""
    if annotations is None:
        annotations = []
    if defaults is not None:
        default_offset = len(args) - len(defaults)
    else:
        default_offset = None
    packed = itertools.zip_longest(args, annotations)
    for i, (arg, annotation) in enumerate(packed):
        if arg.name in skippable_names:
            continue
        if isinstance(arg, Tuple):
            values.append(f"({_format_args(arg.elts)})")
        else:
            argname = arg.name
            default_sep = "="
            if annotation is not None:
                argname += ": " + annotation.as_string()
                default_sep = " = "
            values.append(argname)

            if default_offset is not None and i >= default_offset:
                if defaults[i - default_offset] is not None:
                    values[-1] += default_sep + defaults[i - default_offset].as_string()
    return ", ".join(values)


def _infer_attribute(
    node: nodes.AssignAttr | nodes.Attribute,
    context: InferenceContext | None = None,
    **kwargs: Any,
) -> Generator[InferenceResult, None, InferenceErrorInfo]:
    """Infer an AssignAttr/Attribute node by using getattr on the associated object."""
    # pylint: disable=import-outside-toplevel
    from astroid.constraint import get_constraints
    from astroid.nodes import ClassDef

    for owner in node.expr.infer(context):
        if isinstance(owner, util.UninferableBase):
            yield owner
            continue

        context = copy_context(context)
        old_boundnode = context.boundnode
        try:
            context.boundnode = owner
            if isinstance(owner, (ClassDef, Instance)):
                frame = owner if isinstance(owner, ClassDef) else owner._proxied
                context.constraints[node.attrname] = get_constraints(node, frame=frame)
            if node.attrname == "argv" and owner.name == "sys":
                # sys.argv will never be inferable during static analysis
                # It's value would be the args passed to the linter itself
                yield util.Uninferable
            else:
                yield from owner.igetattr(node.attrname, context)
        except (
            AttributeInferenceError,
            InferenceError,
            AttributeError,
        ):
            pass
        finally:
            context.boundnode = old_boundnode
    return InferenceErrorInfo(node=node, context=context)


class AssignAttr(_base_nodes.LookupMixIn, _base_nodes.ParentAssignNode):
    """Variation of :class:`ast.Assign` representing assignment to an attribute.

    >>> import astroid
    >>> node = astroid.extract_node('self.attribute = range(10)')
    >>> node
    <Assign l.1 at 0x7effe1d521d0>
    >>> list(node.get_children())
    [<AssignAttr.attribute l.1 at 0x7effe1d52320>, <Call l.1 at 0x7effe1d522e8>]
    >>> list(node.get_children())[0].as_string()
    'self.attribute'
    """

    expr: NodeNG

    _astroid_fields = ("expr",)
    _other_fields = ("attrname",)

    def __init__(
        self,
        attrname: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.attrname = attrname
        """The name of the attribute being assigned to."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, expr: NodeNG) -> None:
        self.expr = expr

    assigned_stmts = protocols.assend_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def get_children(self):
        yield self.expr

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """Infer an AssignAttr: need to inspect the RHS part of the
        assign node.
        """
        if isinstance(self.parent, AugAssign):
            return self.parent.infer(context)

        stmts = list(self.assigned_stmts(context=context))
        return _infer_stmts(stmts, context)

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def infer_lhs(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        return _infer_attribute(self, context, **kwargs)


class Assert(_base_nodes.Statement):
    """Class representing an :class:`ast.Assert` node.

    An :class:`Assert` node represents an assert statement.

    >>> import astroid
    >>> node = astroid.extract_node('assert len(things) == 10, "Not enough things"')
    >>> node
    <Assert l.1 at 0x7effe1d527b8>
    """

    _astroid_fields = ("test", "fail")

    test: NodeNG
    """The test that passes or fails the assertion."""

    fail: NodeNG | None
    """The message shown when the assertion fails."""

    def postinit(self, test: NodeNG, fail: NodeNG | None) -> None:
        self.fail = fail
        self.test = test

    def get_children(self):
        yield self.test

        if self.fail is not None:
            yield self.fail


class Assign(_base_nodes.AssignTypeNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Assign` node.

    An :class:`Assign` is a statement where something is explicitly
    asssigned to.

    >>> import astroid
    >>> node = astroid.extract_node('variable = range(10)')
    >>> node
    <Assign l.1 at 0x7effe1db8550>
    """

    targets: list[NodeNG]
    """What is being assigned to."""

    value: NodeNG
    """The value being assigned to the variables."""

    type_annotation: NodeNG | None
    """If present, this will contain the type annotation passed by a type comment"""

    _astroid_fields = ("targets", "value")
    _other_other_fields = ("type_annotation",)

    def postinit(
        self,
        targets: list[NodeNG],
        value: NodeNG,
        type_annotation: NodeNG | None,
    ) -> None:
        self.targets = targets
        self.value = value
        self.type_annotation = type_annotation

    assigned_stmts = protocols.assign_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def get_children(self):
        yield from self.targets

        yield self.value

    @cached_property
    def _assign_nodes_in_scope(self) -> list[nodes.Assign]:
        return [self, *self.value._assign_nodes_in_scope]

    def _get_yield_nodes_skip_functions(self):
        yield from self.value._get_yield_nodes_skip_functions()

    def _get_yield_nodes_skip_lambdas(self):
        yield from self.value._get_yield_nodes_skip_lambdas()


class AnnAssign(_base_nodes.AssignTypeNode, _base_nodes.Statement):
    """Class representing an :class:`ast.AnnAssign` node.

    An :class:`AnnAssign` is an assignment with a type annotation.

    >>> import astroid
    >>> node = astroid.extract_node('variable: List[int] = range(10)')
    >>> node
    <AnnAssign l.1 at 0x7effe1d4c630>
    """

    _astroid_fields = ("target", "annotation", "value")
    _other_fields = ("simple",)

    target: Name | Attribute | Subscript
    """What is being assigned to."""

    annotation: NodeNG
    """The type annotation of what is being assigned to."""

    value: NodeNG | None
    """The value being assigned to the variables."""

    simple: int
    """Whether :attr:`target` is a pure name or a complex statement."""

    def postinit(
        self,
        target: Name | Attribute | Subscript,
        annotation: NodeNG,
        simple: int,
        value: NodeNG | None,
    ) -> None:
        self.target = target
        self.annotation = annotation
        self.value = value
        self.simple = simple

    assigned_stmts = protocols.assign_annassigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def get_children(self):
        yield self.target
        yield self.annotation

        if self.value is not None:
            yield self.value


class AugAssign(
    _base_nodes.AssignTypeNode, _base_nodes.OperatorNode, _base_nodes.Statement
):
    """Class representing an :class:`ast.AugAssign` node.

    An :class:`AugAssign` is an assignment paired with an operator.

    >>> import astroid
    >>> node = astroid.extract_node('variable += 1')
    >>> node
    <AugAssign l.1 at 0x7effe1db4d68>
    """

    _astroid_fields = ("target", "value")
    _other_fields = ("op",)

    target: Name | Attribute | Subscript
    """What is being assigned to."""

    value: NodeNG
    """The value being assigned to the variable."""

    def __init__(
        self,
        op: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.op = op
        """The operator that is being combined with the assignment.

        This includes the equals sign.
        """

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, target: Name | Attribute | Subscript, value: NodeNG) -> None:
        self.target = target
        self.value = value

    assigned_stmts = protocols.assign_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def type_errors(
        self, context: InferenceContext | None = None
    ) -> list[util.BadBinaryOperationMessage]:
        """Get a list of type errors which can occur during inference.

        Each TypeError is represented by a :class:`BadBinaryOperationMessage` ,
        which holds the original exception.

        If any inferred result is uninferable, an empty list is returned.
        """
        bad = []
        try:
            for result in self._infer_augassign(context=context):
                if result is util.Uninferable:
                    raise InferenceError
                if isinstance(result, util.BadBinaryOperationMessage):
                    bad.append(result)
        except InferenceError:
            return []
        return bad

    def get_children(self):
        yield self.target
        yield self.value

    def _get_yield_nodes_skip_functions(self):
        """An AugAssign node can contain a Yield node in the value"""
        yield from self.value._get_yield_nodes_skip_functions()
        yield from super()._get_yield_nodes_skip_functions()

    def _get_yield_nodes_skip_lambdas(self):
        """An AugAssign node can contain a Yield node in the value"""
        yield from self.value._get_yield_nodes_skip_lambdas()
        yield from super()._get_yield_nodes_skip_lambdas()

    def _infer_augassign(
        self, context: InferenceContext | None = None
    ) -> Generator[InferenceResult | util.BadBinaryOperationMessage]:
        """Inference logic for augmented binary operations."""
        context = context or InferenceContext()

        rhs_context = context.clone()

        lhs_iter = self.target.infer_lhs(context=context)
        rhs_iter = self.value.infer(context=rhs_context)

        for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
            if any(isinstance(value, util.UninferableBase) for value in (rhs, lhs)):
                # Don't know how to process this.
                yield util.Uninferable
                return

            try:
                yield from self._infer_binary_operation(
                    left=lhs,
                    right=rhs,
                    binary_opnode=self,
                    context=context,
                    flow_factory=self._get_aug_flow,
                )
            except _NonDeducibleTypeHierarchy:
                yield util.Uninferable

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self: nodes.AugAssign, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        return self._filter_operation_errors(
            self._infer_augassign, context, util.BadBinaryOperationMessage
        )


class BinOp(_base_nodes.OperatorNode):
    """Class representing an :class:`ast.BinOp` node.

    A :class:`BinOp` node is an application of a binary operator.

    >>> import astroid
    >>> node = astroid.extract_node('a + b')
    >>> node
    <BinOp l.1 at 0x7f23b2e8cfd0>
    """

    _astroid_fields = ("left", "right")
    _other_fields = ("op",)

    left: NodeNG
    """What is being applied to the operator on the left side."""

    right: NodeNG
    """What is being applied to the operator on the right side."""

    def __init__(
        self,
        op: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.op = op
        """The operator."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, left: NodeNG, right: NodeNG) -> None:
        self.left = left
        self.right = right

    def type_errors(
        self, context: InferenceContext | None = None
    ) -> list[util.BadBinaryOperationMessage]:
        """Get a list of type errors which can occur during inference.

        Each TypeError is represented by a :class:`BadBinaryOperationMessage`,
        which holds the original exception.

        If any inferred result is uninferable, an empty list is returned.
        """
        bad = []
        try:
            for result in self._infer_binop(context=context):
                if result is util.Uninferable:
                    raise InferenceError
                if isinstance(result, util.BadBinaryOperationMessage):
                    bad.append(result)
        except InferenceError:
            return []
        return bad

    def get_children(self):
        yield self.left
        yield self.right

    def op_precedence(self):
        return OP_PRECEDENCE[self.op]

    def op_left_associative(self) -> bool:
        # 2**3**4 == 2**(3**4)
        return self.op != "**"

    def _infer_binop(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        """Binary operation inference logic."""
        left = self.left
        right = self.right

        # we use two separate contexts for evaluating lhs and rhs because
        # 1. evaluating lhs may leave some undesired entries in context.path
        #    which may not let us infer right value of rhs
        context = context or InferenceContext()
        lhs_context = copy_context(context)
        rhs_context = copy_context(context)
        lhs_iter = left.infer(context=lhs_context)
        rhs_iter = right.infer(context=rhs_context)
        for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
            if any(isinstance(value, util.UninferableBase) for value in (rhs, lhs)):
                # Don't know how to process this.
                yield util.Uninferable
                return

            try:
                yield from self._infer_binary_operation(
                    lhs, rhs, self, context, self._get_binop_flow
                )
            except _NonDeducibleTypeHierarchy:
                yield util.Uninferable

    @decorators.yes_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self: nodes.BinOp, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        return self._filter_operation_errors(
            self._infer_binop, context, util.BadBinaryOperationMessage
        )


class BoolOp(NodeNG):
    """Class representing an :class:`ast.BoolOp` node.

    A :class:`BoolOp` is an application of a boolean operator.

    >>> import astroid
    >>> node = astroid.extract_node('a and b')
    >>> node
    <BinOp l.1 at 0x7f23b2e71c50>
    """

    _astroid_fields = ("values",)
    _other_fields = ("op",)

    def __init__(
        self,
        op: str,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param op: The operator.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.op: str = op
        """The operator."""

        self.values: list[NodeNG] = []
        """The values being applied to the operator."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, values: list[NodeNG] | None = None) -> None:
        """Do some setup after initialisation.

        :param values: The values being applied to the operator.
        """
        if values is not None:
            self.values = values

    def get_children(self):
        yield from self.values

    def op_precedence(self):
        return OP_PRECEDENCE[self.op]

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self: nodes.BoolOp, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """Infer a boolean operation (and / or / not).

        The function will calculate the boolean operation
        for all pairs generated through inference for each component
        node.
        """
        values = self.values
        if self.op == "or":
            predicate = operator.truth
        else:
            predicate = operator.not_

        try:
            inferred_values = [value.infer(context=context) for value in values]
        except InferenceError:
            yield util.Uninferable
            return None

        for pair in itertools.product(*inferred_values):
            if any(isinstance(item, util.UninferableBase) for item in pair):
                # Can't infer the final result, just yield Uninferable.
                yield util.Uninferable
                continue

            bool_values = [item.bool_value() for item in pair]
            if any(isinstance(item, util.UninferableBase) for item in bool_values):
                # Can't infer the final result, just yield Uninferable.
                yield util.Uninferable
                continue

            # Since the boolean operations are short circuited operations,
            # this code yields the first value for which the predicate is True
            # and if no value respected the predicate, then the last value will
            # be returned (or Uninferable if there was no last value).
            # This is conforming to the semantics of `and` and `or`:
            #   1 and 0 -> 1
            #   0 and 1 -> 0
            #   1 or 0 -> 1
            #   0 or 1 -> 1
            value = util.Uninferable
            for value, bool_value in zip(pair, bool_values):
                if predicate(bool_value):
                    yield value
                    break
            else:
                yield value

        return InferenceErrorInfo(node=self, context=context)


class Break(_base_nodes.NoChildrenNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Break` node.

    >>> import astroid
    >>> node = astroid.extract_node('break')
    >>> node
    <Break l.1 at 0x7f23b2e9e5c0>
    """


class Call(NodeNG):
    """Class representing an :class:`ast.Call` node.

    A :class:`Call` node is a call to a function, method, etc.

    >>> import astroid
    >>> node = astroid.extract_node('function()')
    >>> node
    <Call l.1 at 0x7f23b2e71eb8>
    """

    _astroid_fields = ("func", "args", "keywords")

    func: NodeNG
    """What is being called."""

    args: list[NodeNG]
    """The positional arguments being given to the call."""

    keywords: list[Keyword]
    """The keyword arguments being given to the call."""

    def postinit(
        self, func: NodeNG, args: list[NodeNG], keywords: list[Keyword]
    ) -> None:
        self.func = func
        self.args = args
        self.keywords = keywords

    @property
    def starargs(self) -> list[Starred]:
        """The positional arguments that unpack something."""
        return [arg for arg in self.args if isinstance(arg, Starred)]

    @property
    def kwargs(self) -> list[Keyword]:
        """The keyword arguments that unpack something."""
        return [keyword for keyword in self.keywords if keyword.arg is None]

    def get_children(self):
        yield self.func

        yield from self.args

        yield from self.keywords

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo]:
        """Infer a Call node by trying to guess what the function returns."""
        callcontext = copy_context(context)
        callcontext.boundnode = None
        if context is not None:
            callcontext.extra_context = self._populate_context_lookup(context.clone())

        for callee in self.func.infer(context):
            if isinstance(callee, util.UninferableBase):
                yield callee
                continue
            try:
                if hasattr(callee, "infer_call_result"):
                    callcontext.callcontext = CallContext(
                        args=self.args, keywords=self.keywords, callee=callee
                    )
                    yield from callee.infer_call_result(
                        caller=self, context=callcontext
                    )
            except InferenceError:
                continue
        return InferenceErrorInfo(node=self, context=context)

    def _populate_context_lookup(self, context: InferenceContext | None):
        """Allows context to be saved for later for inference inside a function."""
        context_lookup: dict[InferenceResult, InferenceContext] = {}
        if context is None:
            return context_lookup
        for arg in self.args:
            if isinstance(arg, Starred):
                context_lookup[arg.value] = context
            else:
                context_lookup[arg] = context
        keywords = self.keywords if self.keywords is not None else []
        for keyword in keywords:
            context_lookup[keyword.value] = context
        return context_lookup


COMPARE_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}
UNINFERABLE_OPS = {
    "is",
    "is not",
}


class Compare(NodeNG):
    """Class representing an :class:`ast.Compare` node.

    A :class:`Compare` node indicates a comparison.

    >>> import astroid
    >>> node = astroid.extract_node('a <= b <= c')
    >>> node
    <Compare l.1 at 0x7f23b2e9e6d8>
    >>> node.ops
    [('<=', <Name.b l.1 at 0x7f23b2e9e2b0>), ('<=', <Name.c l.1 at 0x7f23b2e9e390>)]
    """

    _astroid_fields = ("left", "ops")

    left: NodeNG
    """The value at the left being applied to a comparison operator."""

    ops: list[tuple[str, NodeNG]]
    """The remainder of the operators and their relevant right hand value."""

    def postinit(self, left: NodeNG, ops: list[tuple[str, NodeNG]]) -> None:
        self.left = left
        self.ops = ops

    def get_children(self):
        """Get the child nodes below this node.

        Overridden to handle the tuple fields and skip returning the operator
        strings.

        :returns: The children.
        :rtype: iterable(NodeNG)
        """
        yield self.left
        for _, comparator in self.ops:
            yield comparator  # we don't want the 'op'

    def last_child(self):
        """An optimized version of list(get_children())[-1]

        :returns: The last child.
        :rtype: NodeNG
        """
        # XXX maybe if self.ops:
        return self.ops[-1][1]
        # return self.left

    # TODO: move to util?
    @staticmethod
    def _to_literal(node: SuccessfulInferenceResult) -> Any:
        # Can raise SyntaxError or ValueError from ast.literal_eval
        # Can raise AttributeError from node.as_string() as not all nodes have a visitor
        # Is this the stupidest idea or the simplest idea?
        return ast.literal_eval(node.as_string())

    def _do_compare(
        self,
        left_iter: Iterable[InferenceResult],
        op: str,
        right_iter: Iterable[InferenceResult],
    ) -> bool | util.UninferableBase:
        """
        If all possible combinations are either True or False, return that:
        >>> _do_compare([1, 2], '<=', [3, 4])
        True
        >>> _do_compare([1, 2], '==', [3, 4])
        False

        If any item is uninferable, or if some combinations are True and some
        are False, return Uninferable:
        >>> _do_compare([1, 3], '<=', [2, 4])
        util.Uninferable
        """
        retval: bool | None = None
        if op in UNINFERABLE_OPS:
            return util.Uninferable
        op_func = COMPARE_OPS[op]

        for left, right in itertools.product(left_iter, right_iter):
            if isinstance(left, util.UninferableBase) or isinstance(
                right, util.UninferableBase
            ):
                return util.Uninferable

            try:
                left, right = self._to_literal(left), self._to_literal(right)
            except (SyntaxError, ValueError, AttributeError):
                return util.Uninferable

            try:
                expr = op_func(left, right)
            except TypeError as exc:
                raise AstroidTypeError from exc

            if retval is None:
                retval = expr
            elif retval != expr:
                return util.Uninferable
                # (or both, but "True | False" is basically the same)

        assert retval is not None
        return retval  # it was all the same value

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[nodes.Const | util.UninferableBase]:
        """Chained comparison inference logic."""
        retval: bool | util.UninferableBase = True

        ops = self.ops
        left_node = self.left
        lhs = list(left_node.infer(context=context))
        # should we break early if first element is uninferable?
        for op, right_node in ops:
            # eagerly evaluate rhs so that values can be re-used as lhs
            rhs = list(right_node.infer(context=context))
            try:
                retval = self._do_compare(lhs, op, rhs)
            except AstroidTypeError:
                retval = util.Uninferable
                break
            if retval is not True:
                break  # short-circuit
            lhs = rhs  # continue
        if retval is util.Uninferable:
            yield retval  # type: ignore[misc]
        else:
            yield Const(retval)


class Comprehension(NodeNG):
    """Class representing an :class:`ast.comprehension` node.

    A :class:`Comprehension` indicates the loop inside any type of
    comprehension including generator expressions.

    >>> import astroid
    >>> node = astroid.extract_node('[x for x in some_values]')
    >>> list(node.get_children())
    [<Name.x l.1 at 0x7f23b2e352b0>, <Comprehension l.1 at 0x7f23b2e35320>]
    >>> list(node.get_children())[1].as_string()
    'for x in some_values'
    """

    _astroid_fields = ("target", "iter", "ifs")
    _other_fields = ("is_async",)

    optional_assign = True
    """Whether this node optionally assigns a variable."""

    target: NodeNG
    """What is assigned to by the comprehension."""

    iter: NodeNG
    """What is iterated over by the comprehension."""

    ifs: list[NodeNG]
    """The contents of any if statements that filter the comprehension."""

    is_async: bool
    """Whether this is an asynchronous comprehension or not."""

    def postinit(
        self,
        target: NodeNG,
        iter: NodeNG,  # pylint: disable = redefined-builtin
        ifs: list[NodeNG],
        is_async: bool,
    ) -> None:
        self.target = target
        self.iter = iter
        self.ifs = ifs
        self.is_async = is_async

    assigned_stmts = protocols.for_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def assign_type(self):
        """The type of assignment that this node performs.

        :returns: The assignment type.
        :rtype: NodeNG
        """
        return self

    def _get_filtered_stmts(
        self, lookup_node, node, stmts, mystmt: _base_nodes.Statement | None
    ):
        """method used in filter_stmts"""
        if self is mystmt:
            if isinstance(lookup_node, (Const, Name)):
                return [lookup_node], True

        elif self.statement() is mystmt:
            # original node's statement is the assignment, only keeps
            # current node (gen exp, list comp)

            return [node], True

        return stmts, False

    def get_children(self):
        yield self.target
        yield self.iter

        yield from self.ifs


class Const(_base_nodes.NoChildrenNode, Instance):
    """Class representing any constant including num, str, bool, None, bytes.

    >>> import astroid
    >>> node = astroid.extract_node('(5, "This is a string.", True, None, b"bytes")')
    >>> node
    <Tuple.tuple l.1 at 0x7f23b2e358d0>
    >>> list(node.get_children())
    [<Const.int l.1 at 0x7f23b2e35940>,
    <Const.str l.1 at 0x7f23b2e35978>,
    <Const.bool l.1 at 0x7f23b2e359b0>,
    <Const.NoneType l.1 at 0x7f23b2e359e8>,
    <Const.bytes l.1 at 0x7f23b2e35a20>]
    """

    _other_fields = ("value", "kind")

    def __init__(
        self,
        value: Any,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        kind: str | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param value: The value that the constant represents.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param kind: The string prefix. "u" for u-prefixed strings and ``None`` otherwise. Python 3.8+ only.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.value: Any = value
        """The value that the constant represents."""

        self.kind: str | None = kind  # can be None
        """"The string prefix. "u" for u-prefixed strings and ``None`` otherwise. Python 3.8+ only."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

        Instance.__init__(self, None)

    infer_unary_op = protocols.const_infer_unary_op
    infer_binary_op = protocols.const_infer_binary_op

    def __getattr__(self, name):
        # This is needed because of Proxy's __getattr__ method.
        # Calling object.__new__ on this class without calling
        # __init__ would result in an infinite loop otherwise
        # since __getattr__ is called when an attribute doesn't
        # exist and self._proxied indirectly calls self.value
        # and Proxy __getattr__ calls self.value
        if name == "value":
            raise AttributeError
        return super().__getattr__(name)

    def getitem(self, index, context: InferenceContext | None = None):
        """Get an item from this node if subscriptable.

        :param index: The node to use as a subscript index.
        :type index: Const or Slice

        :raises AstroidTypeError: When the given index cannot be used as a
            subscript index, or if this node is not subscriptable.
        """
        if isinstance(index, Const):
            index_value = index.value
        elif isinstance(index, Slice):
            index_value = _infer_slice(index, context=context)

        else:
            raise AstroidTypeError(
                f"Could not use type {type(index)} as subscript index"
            )

        try:
            if isinstance(self.value, (str, bytes)):
                return Const(self.value[index_value])
        except ValueError as exc:
            raise AstroidValueError(
                f"Could not index {self.value!r} with {index_value!r}"
            ) from exc
        except IndexError as exc:
            raise AstroidIndexError(
                message="Index {index!r} out of range",
                node=self,
                index=index,
                context=context,
            ) from exc
        except TypeError as exc:
            raise AstroidTypeError(
                message="Type error {error!r}", node=self, index=index, context=context
            ) from exc

        raise AstroidTypeError(f"{self!r} (value={self.value})")

    def has_dynamic_getattr(self) -> bool:
        """Check if the node has a custom __getattr__ or __getattribute__.

        :returns: Whether the class has a custom __getattr__ or __getattribute__.
            For a :class:`Const` this is always ``False``.
        """
        return False

    def itered(self):
        """An iterator over the elements this node contains.

        :returns: The contents of this node.
        :rtype: iterable(Const)

        :raises TypeError: If this node does not represent something that is iterable.
        """
        if isinstance(self.value, str):
            return [const_factory(elem) for elem in self.value]
        raise TypeError(f"Cannot iterate over type {type(self.value)!r}")

    def pytype(self) -> str:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """
        return self._proxied.qname()

    def bool_value(self, context: InferenceContext | None = None):
        """Determine the boolean value of this node.

        :returns: The boolean value of this node.
        :rtype: bool
        """
        return bool(self.value)

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[Const]:
        yield self


class Continue(_base_nodes.NoChildrenNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Continue` node.

    >>> import astroid
    >>> node = astroid.extract_node('continue')
    >>> node
    <Continue l.1 at 0x7f23b2e35588>
    """


class Decorators(NodeNG):
    """A node representing a list of decorators.

    A :class:`Decorators` is the decorators that are applied to
    a method or function.

    >>> import astroid
    >>> node = astroid.extract_node('''
    @property
    def my_property(self):
        return 3
    ''')
    >>> node
    <FunctionDef.my_property l.2 at 0x7f23b2e35d30>
    >>> list(node.get_children())[0]
    <Decorators l.1 at 0x7f23b2e35d68>
    """

    _astroid_fields = ("nodes",)

    nodes: list[NodeNG]
    """The decorators that this node contains."""

    def postinit(self, nodes: list[NodeNG]) -> None:
        self.nodes = nodes

    def scope(self) -> LocalsDictNodeNG:
        """The first parent node defining a new scope.
        These can be Module, FunctionDef, ClassDef, Lambda, or GeneratorExp nodes.

        :returns: The first parent scope node.
        """
        # skip the function node to go directly to the upper level scope
        if not self.parent:
            raise ParentMissingError(target=self)
        if not self.parent.parent:
            raise ParentMissingError(target=self.parent)
        return self.parent.parent.scope()

    def get_children(self):
        yield from self.nodes


class DelAttr(_base_nodes.ParentAssignNode):
    """Variation of :class:`ast.Delete` representing deletion of an attribute.

    >>> import astroid
    >>> node = astroid.extract_node('del self.attr')
    >>> node
    <Delete l.1 at 0x7f23b2e35f60>
    >>> list(node.get_children())[0]
    <DelAttr.attr l.1 at 0x7f23b2e411d0>
    """

    _astroid_fields = ("expr",)
    _other_fields = ("attrname",)

    expr: NodeNG
    """The name that this node represents."""

    def __init__(
        self,
        attrname: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.attrname = attrname
        """The name of the attribute that is being deleted."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, expr: NodeNG) -> None:
        self.expr = expr

    def get_children(self):
        yield self.expr


class Delete(_base_nodes.AssignTypeNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Delete` node.

    A :class:`Delete` is a ``del`` statement this is deleting something.

    >>> import astroid
    >>> node = astroid.extract_node('del self.attr')
    >>> node
    <Delete l.1 at 0x7f23b2e35f60>
    """

    _astroid_fields = ("targets",)

    def __init__(
        self,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.targets: list[NodeNG] = []
        """What is being deleted."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, targets: list[NodeNG]) -> None:
        self.targets = targets

    def get_children(self):
        yield from self.targets


class Dict(NodeNG, Instance):
    """Class representing an :class:`ast.Dict` node.

    A :class:`Dict` is a dictionary that is created with ``{}`` syntax.

    >>> import astroid
    >>> node = astroid.extract_node('{1: "1"}')
    >>> node
    <Dict.dict l.1 at 0x7f23b2e35cc0>
    """

    _astroid_fields = ("items",)

    def __init__(
        self,
        lineno: int | None,
        col_offset: int | None,
        parent: NodeNG | None,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.items: list[tuple[InferenceResult, InferenceResult]] = []
        """The key-value pairs contained in the dictionary."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, items: list[tuple[InferenceResult, InferenceResult]]) -> None:
        """Do some setup after initialisation.

        :param items: The key-value pairs contained in the dictionary.
        """
        self.items = items

    infer_unary_op = protocols.dict_infer_unary_op

    def pytype(self) -> Literal["builtins.dict"]:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """
        return "builtins.dict"

    def get_children(self):
        """Get the key and value nodes below this node.

        Children are returned in the order that they are defined in the source
        code, key first then the value.

        :returns: The children.
        :rtype: iterable(NodeNG)
        """
        for key, value in self.items:
            yield key
            yield value

    def last_child(self):
        """An optimized version of list(get_children())[-1]

        :returns: The last child, or None if no children exist.
        :rtype: NodeNG or None
        """
        if self.items:
            return self.items[-1][1]
        return None

    def itered(self):
        """An iterator over the keys this node contains.

        :returns: The keys of this node.
        :rtype: iterable(NodeNG)
        """
        return [key for (key, _) in self.items]

    def getitem(
        self, index: Const | Slice, context: InferenceContext | None = None
    ) -> NodeNG:
        """Get an item from this node.

        :param index: The node to use as a subscript index.

        :raises AstroidTypeError: When the given index cannot be used as a
            subscript index, or if this node is not subscriptable.
        :raises AstroidIndexError: If the given index does not exist in the
            dictionary.
        """
        for key, value in self.items:
            # TODO(cpopa): no support for overriding yet, {1:2, **{1: 3}}.
            if isinstance(key, DictUnpack):
                inferred_value = util.safe_infer(value, context)
                if not isinstance(inferred_value, Dict):
                    continue

                try:
                    return inferred_value.getitem(index, context)
                except (AstroidTypeError, AstroidIndexError):
                    continue

            for inferredkey in key.infer(context):
                if isinstance(inferredkey, util.UninferableBase):
                    continue
                if isinstance(inferredkey, Const) and isinstance(index, Const):
                    if inferredkey.value == index.value:
                        return value

        raise AstroidIndexError(index)

    def bool_value(self, context: InferenceContext | None = None):
        """Determine the boolean value of this node.

        :returns: The boolean value of this node.
        :rtype: bool
        """
        return bool(self.items)

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[nodes.Dict]:
        if not any(isinstance(k, DictUnpack) for k, _ in self.items):
            yield self
        else:
            items = self._infer_map(context)
            new_seq = type(self)(
                lineno=self.lineno,
                col_offset=self.col_offset,
                parent=self.parent,
                end_lineno=self.end_lineno,
                end_col_offset=self.end_col_offset,
            )
            new_seq.postinit(list(items.items()))
            yield new_seq

    @staticmethod
    def _update_with_replacement(
        lhs_dict: dict[SuccessfulInferenceResult, SuccessfulInferenceResult],
        rhs_dict: dict[SuccessfulInferenceResult, SuccessfulInferenceResult],
    ) -> dict[SuccessfulInferenceResult, SuccessfulInferenceResult]:
        """Delete nodes that equate to duplicate keys.

        Since an astroid node doesn't 'equal' another node with the same value,
        this function uses the as_string method to make sure duplicate keys
        don't get through

        Note that both the key and the value are astroid nodes

        Fixes issue with DictUnpack causing duplicate keys
        in inferred Dict items

        :param lhs_dict: Dictionary to 'merge' nodes into
        :param rhs_dict: Dictionary with nodes to pull from
        :return : merged dictionary of nodes
        """
        combined_dict = itertools.chain(lhs_dict.items(), rhs_dict.items())
        # Overwrite keys which have the same string values
        string_map = {key.as_string(): (key, value) for key, value in combined_dict}
        # Return to dictionary
        return dict(string_map.values())

    def _infer_map(
        self, context: InferenceContext | None
    ) -> dict[SuccessfulInferenceResult, SuccessfulInferenceResult]:
        """Infer all values based on Dict.items."""
        values: dict[SuccessfulInferenceResult, SuccessfulInferenceResult] = {}
        for name, value in self.items:
            if isinstance(name, DictUnpack):
                double_starred = util.safe_infer(value, context)
                if not double_starred:
                    raise InferenceError
                if not isinstance(double_starred, Dict):
                    raise InferenceError(node=self, context=context)
                unpack_items = double_starred._infer_map(context)
                values = self._update_with_replacement(values, unpack_items)
            else:
                key = util.safe_infer(name, context=context)
                safe_value = util.safe_infer(value, context=context)
                if any(not elem for elem in (key, safe_value)):
                    raise InferenceError(node=self, context=context)
                # safe_value is SuccessfulInferenceResult as bool(Uninferable) == False
                values = self._update_with_replacement(values, {key: safe_value})
        return values


class Expr(_base_nodes.Statement):
    """Class representing an :class:`ast.Expr` node.

    An :class:`Expr` is any expression that does not have its value used or
    stored.

    >>> import astroid
    >>> node = astroid.extract_node('method()')
    >>> node
    <Call l.1 at 0x7f23b2e352b0>
    >>> node.parent
    <Expr l.1 at 0x7f23b2e35278>
    """

    _astroid_fields = ("value",)

    value: NodeNG
    """What the expression does."""

    def postinit(self, value: NodeNG) -> None:
        self.value = value

    def get_children(self):
        yield self.value

    def _get_yield_nodes_skip_functions(self):
        if not self.value.is_function:
            yield from self.value._get_yield_nodes_skip_functions()

    def _get_yield_nodes_skip_lambdas(self):
        if not self.value.is_lambda:
            yield from self.value._get_yield_nodes_skip_lambdas()


class EmptyNode(_base_nodes.NoChildrenNode):
    """Holds an arbitrary object in the :attr:`LocalsDictNodeNG.locals`."""

    object = None

    def __init__(
        self,
        lineno: None = None,
        col_offset: None = None,
        parent: None = None,
        *,
        end_lineno: None = None,
        end_col_offset: None = None,
    ) -> None:
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def has_underlying_object(self) -> bool:
        return self.object is not None and self.object is not _EMPTY_OBJECT_MARKER

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        if not self.has_underlying_object():
            yield util.Uninferable
        else:
            try:
                yield from AstroidManager().infer_ast_from_something(
                    self.object, context=context
                )
            except AstroidError:
                yield util.Uninferable


class ExceptHandler(
    _base_nodes.MultiLineBlockNode, _base_nodes.AssignTypeNode, _base_nodes.Statement
):
    """Class representing an :class:`ast.ExceptHandler`. node.

    An :class:`ExceptHandler` is an ``except`` block on a try-except.

    >>> import astroid
    >>> node = astroid.extract_node('''
        try:
            do_something()
        except Exception as error:
            print("Error!")
        ''')
    >>> node
    <Try l.2 at 0x7f23b2e9d908>
    >>> node.handlers
    [<ExceptHandler l.4 at 0x7f23b2e9e860>]
    """

    _astroid_fields = ("type", "name", "body")
    _multi_line_block_fields = ("body",)

    type: NodeNG | None
    """The types that the block handles."""

    name: AssignName | None
    """The name that the caught exception is assigned to."""

    body: list[NodeNG]
    """The contents of the block."""

    assigned_stmts = protocols.excepthandler_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def postinit(
        self,
        type: NodeNG | None,  # pylint: disable = redefined-builtin
        name: AssignName | None,
        body: list[NodeNG],
    ) -> None:
        self.type = type
        self.name = name
        self.body = body

    def get_children(self):
        if self.type is not None:
            yield self.type

        if self.name is not None:
            yield self.name

        yield from self.body

    @cached_property
    def blockstart_tolineno(self):
        """The line on which the beginning of this block ends.

        :type: int
        """
        if self.name:
            return self.name.tolineno
        if self.type:
            return self.type.tolineno
        return self.lineno

    def catch(self, exceptions: list[str] | None) -> bool:
        """Check if this node handles any of the given

        :param exceptions: The names of the exceptions to check for.
        """
        if self.type is None or exceptions is None:
            return True
        return any(node.name in exceptions for node in self.type._get_name_nodes())


class For(
    _base_nodes.MultiLineWithElseBlockNode,
    _base_nodes.AssignTypeNode,
    _base_nodes.Statement,
):
    """Class representing an :class:`ast.For` node.

    >>> import astroid
    >>> node = astroid.extract_node('for thing in things: print(thing)')
    >>> node
    <For l.1 at 0x7f23b2e8cf28>
    """

    _astroid_fields = ("target", "iter", "body", "orelse")
    _other_other_fields = ("type_annotation",)
    _multi_line_block_fields = ("body", "orelse")

    optional_assign = True
    """Whether this node optionally assigns a variable.

    This is always ``True`` for :class:`For` nodes.
    """

    target: NodeNG
    """What the loop assigns to."""

    iter: NodeNG
    """What the loop iterates over."""

    body: list[NodeNG]
    """The contents of the body of the loop."""

    orelse: list[NodeNG]
    """The contents of the ``else`` block of the loop."""

    type_annotation: NodeNG | None
    """If present, this will contain the type annotation passed by a type comment"""

    def postinit(
        self,
        target: NodeNG,
        iter: NodeNG,  # pylint: disable = redefined-builtin
        body: list[NodeNG],
        orelse: list[NodeNG],
        type_annotation: NodeNG | None,
    ) -> None:
        self.target = target
        self.iter = iter
        self.body = body
        self.orelse = orelse
        self.type_annotation = type_annotation

    assigned_stmts = protocols.for_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    @cached_property
    def blockstart_tolineno(self):
        """The line on which the beginning of this block ends.

        :type: int
        """
        return self.iter.tolineno

    def get_children(self):
        yield self.target
        yield self.iter

        yield from self.body
        yield from self.orelse


class AsyncFor(For):
    """Class representing an :class:`ast.AsyncFor` node.

    An :class:`AsyncFor` is an asynchronous :class:`For` built with
    the ``async`` keyword.

    >>> import astroid
    >>> node = astroid.extract_node('''
    async def func(things):
        async for thing in things:
            print(thing)
    ''')
    >>> node
    <AsyncFunctionDef.func l.2 at 0x7f23b2e416d8>
    >>> node.body[0]
    <AsyncFor l.3 at 0x7f23b2e417b8>
    """


class Await(NodeNG):
    """Class representing an :class:`ast.Await` node.

    An :class:`Await` is the ``await`` keyword.

    >>> import astroid
    >>> node = astroid.extract_node('''
    async def func(things):
        await other_func()
    ''')
    >>> node
    <AsyncFunctionDef.func l.2 at 0x7f23b2e41748>
    >>> node.body[0]
    <Expr l.3 at 0x7f23b2e419e8>
    >>> list(node.body[0].get_children())[0]
    <Await l.3 at 0x7f23b2e41a20>
    """

    _astroid_fields = ("value",)

    value: NodeNG
    """What to wait for."""

    def postinit(self, value: NodeNG) -> None:
        self.value = value

    def get_children(self):
        yield self.value


class ImportFrom(_base_nodes.ImportNode):
    """Class representing an :class:`ast.ImportFrom` node.

    >>> import astroid
    >>> node = astroid.extract_node('from my_package import my_module')
    >>> node
    <ImportFrom l.1 at 0x7f23b2e415c0>
    """

    _other_fields = ("modname", "names", "level")

    def __init__(
        self,
        fromname: str | None,
        names: list[tuple[str, str | None]],
        level: int | None = 0,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param fromname: The module that is being imported from.

        :param names: What is being imported from the module.

        :param level: The level of relative import.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.modname: str | None = fromname  # can be None
        """The module that is being imported from.

        This is ``None`` for relative imports.
        """

        self.names: list[tuple[str, str | None]] = names
        """What is being imported from the module.

        Each entry is a :class:`tuple` of the name being imported,
        and the alias that the name is assigned to (if any).
        """

        # TODO When is 'level' None?
        self.level: int | None = level  # can be None
        """The level of relative import.

        Essentially this is the number of dots in the import.
        This is always 0 for absolute imports.
        """

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self,
        context: InferenceContext | None = None,
        asname: bool = True,
        **kwargs: Any,
    ) -> Generator[InferenceResult]:
        """Infer a ImportFrom node: return the imported module/object."""
        context = context or InferenceContext()
        name = context.lookupname
        if name is None:
            raise InferenceError(node=self, context=context)
        if asname:
            try:
                name = self.real_name(name)
            except AttributeInferenceError as exc:
                # See https://github.com/pylint-dev/pylint/issues/4692
                raise InferenceError(node=self, context=context) from exc
        try:
            module = self.do_import_module()
        except AstroidBuildingError as exc:
            raise InferenceError(node=self, context=context) from exc

        try:
            context = copy_context(context)
            context.lookupname = name
            stmts = module.getattr(name, ignore_locals=module is self.root())
            return _infer_stmts(stmts, context)
        except AttributeInferenceError as error:
            raise InferenceError(
                str(error), target=self, attribute=name, context=context
            ) from error


class Attribute(NodeNG):
    """Class representing an :class:`ast.Attribute` node."""

    expr: NodeNG

    _astroid_fields = ("expr",)
    _other_fields = ("attrname",)

    def __init__(
        self,
        attrname: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.attrname = attrname
        """The name of the attribute."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, expr: NodeNG) -> None:
        self.expr = expr

    def get_children(self):
        yield self.expr

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo]:
        return _infer_attribute(self, context, **kwargs)


class Global(_base_nodes.NoChildrenNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Global` node.

    >>> import astroid
    >>> node = astroid.extract_node('global a_global')
    >>> node
    <Global l.1 at 0x7f23b2e9de10>
    """

    _other_fields = ("names",)

    def __init__(
        self,
        names: list[str],
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param names: The names being declared as global.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.names: list[str] = names
        """The names being declared as global."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def _infer_name(self, frame, name):
        return name

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        if context is None or context.lookupname is None:
            raise InferenceError(node=self, context=context)
        try:
            # pylint: disable-next=no-member
            return _infer_stmts(self.root().getattr(context.lookupname), context)
        except AttributeInferenceError as error:
            raise InferenceError(
                str(error), target=self, attribute=context.lookupname, context=context
            ) from error


class If(_base_nodes.MultiLineWithElseBlockNode, _base_nodes.Statement):
    """Class representing an :class:`ast.If` node.

    >>> import astroid
    >>> node = astroid.extract_node('if condition: print(True)')
    >>> node
    <If l.1 at 0x7f23b2e9dd30>
    """

    _astroid_fields = ("test", "body", "orelse")
    _multi_line_block_fields = ("body", "orelse")

    test: NodeNG
    """The condition that the statement tests."""

    body: list[NodeNG]
    """The contents of the block."""

    orelse: list[NodeNG]
    """The contents of the ``else`` block."""

    def postinit(self, test: NodeNG, body: list[NodeNG], orelse: list[NodeNG]) -> None:
        self.test = test
        self.body = body
        self.orelse = orelse

    @cached_property
    def blockstart_tolineno(self):
        """The line on which the beginning of this block ends.

        :type: int
        """
        return self.test.tolineno

    def block_range(self, lineno: int) -> tuple[int, int]:
        """Get a range from the given line number to where this node ends.

        :param lineno: The line number to start the range at.

        :returns: The range of line numbers that this node belongs to,
            starting at the given line number.
        """
        if lineno == self.body[0].fromlineno:
            return lineno, lineno
        if lineno <= self.body[-1].tolineno:
            return lineno, self.body[-1].tolineno
        return self._elsed_block_range(lineno, self.orelse, self.body[0].fromlineno - 1)

    def get_children(self):
        yield self.test

        yield from self.body
        yield from self.orelse

    def has_elif_block(self):
        return len(self.orelse) == 1 and isinstance(self.orelse[0], If)

    def _get_yield_nodes_skip_functions(self):
        """An If node can contain a Yield node in the test"""
        yield from self.test._get_yield_nodes_skip_functions()
        yield from super()._get_yield_nodes_skip_functions()

    def _get_yield_nodes_skip_lambdas(self):
        """An If node can contain a Yield node in the test"""
        yield from self.test._get_yield_nodes_skip_lambdas()
        yield from super()._get_yield_nodes_skip_lambdas()


class IfExp(NodeNG):
    """Class representing an :class:`ast.IfExp` node.
    >>> import astroid
    >>> node = astroid.extract_node('value if condition else other')
    >>> node
    <IfExp l.1 at 0x7f23b2e9dbe0>
    """

    _astroid_fields = ("test", "body", "orelse")

    test: NodeNG
    """The condition that the statement tests."""

    body: NodeNG
    """The contents of the block."""

    orelse: NodeNG
    """The contents of the ``else`` block."""

    def postinit(self, test: NodeNG, body: NodeNG, orelse: NodeNG) -> None:
        self.test = test
        self.body = body
        self.orelse = orelse

    def get_children(self):
        yield self.test
        yield self.body
        yield self.orelse

    def op_left_associative(self) -> Literal[False]:
        # `1 if True else 2 if False else 3` is parsed as
        # `1 if True else (2 if False else 3)`
        return False

    @decorators.raise_if_nothing_inferred
    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        """Support IfExp inference.

        If we can't infer the truthiness of the condition, we default
        to inferring both branches. Otherwise, we infer either branch
        depending on the condition.
        """
        both_branches = False
        # We use two separate contexts for evaluating lhs and rhs because
        # evaluating lhs may leave some undesired entries in context.path
        # which may not let us infer right value of rhs.

        context = context or InferenceContext()
        lhs_context = copy_context(context)
        rhs_context = copy_context(context)
        try:
            test = next(self.test.infer(context=context.clone()))
        except (InferenceError, StopIteration):
            both_branches = True
        else:
            if not isinstance(test, util.UninferableBase):
                if test.bool_value():
                    yield from self.body.infer(context=lhs_context)
                else:
                    yield from self.orelse.infer(context=rhs_context)
            else:
                both_branches = True
        if both_branches:
            yield from self.body.infer(context=lhs_context)
            yield from self.orelse.infer(context=rhs_context)


class Import(_base_nodes.ImportNode):
    """Class representing an :class:`ast.Import` node.
    >>> import astroid
    >>> node = astroid.extract_node('import astroid')
    >>> node
    <Import l.1 at 0x7f23b2e4e5c0>
    """

    _other_fields = ("names",)

    def __init__(
        self,
        names: list[tuple[str, str | None]],
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param names: The names being imported.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.names: list[tuple[str, str | None]] = names
        """The names being imported.

        Each entry is a :class:`tuple` of the name being imported,
        and the alias that the name is assigned to (if any).
        """

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self,
        context: InferenceContext | None = None,
        asname: bool = True,
        **kwargs: Any,
    ) -> Generator[nodes.Module]:
        """Infer an Import node: return the imported module/object."""
        context = context or InferenceContext()
        name = context.lookupname
        if name is None:
            raise InferenceError(node=self, context=context)

        try:
            if asname:
                yield self.do_import_module(self.real_name(name))
            else:
                yield self.do_import_module(name)
        except AstroidBuildingError as exc:
            raise InferenceError(node=self, context=context) from exc


class Keyword(NodeNG):
    """Class representing an :class:`ast.keyword` node.

    >>> import astroid
    >>> node = astroid.extract_node('function(a_kwarg=True)')
    >>> node
    <Call l.1 at 0x7f23b2e9e320>
    >>> node.keywords
    [<Keyword l.1 at 0x7f23b2e9e9b0>]
    """

    _astroid_fields = ("value",)
    _other_fields = ("arg",)

    value: NodeNG
    """The value being assigned to the keyword argument."""

    def __init__(
        self,
        arg: str | None,
        lineno: int | None,
        col_offset: int | None,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.arg = arg
        """The argument being assigned to."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, value: NodeNG) -> None:
        self.value = value

    def get_children(self):
        yield self.value


class List(BaseContainer):
    """Class representing an :class:`ast.List` node.

    >>> import astroid
    >>> node = astroid.extract_node('[1, 2, 3]')
    >>> node
    <List.list l.1 at 0x7f23b2e9e128>
    """

    _other_fields = ("ctx",)

    def __init__(
        self,
        ctx: Context | None = None,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param ctx: Whether the list is assigned to or loaded from.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.ctx: Context | None = ctx
        """Whether the list is assigned to or loaded from."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    assigned_stmts = protocols.sequence_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    infer_unary_op = protocols.list_infer_unary_op
    infer_binary_op = protocols.tl_infer_binary_op

    def pytype(self) -> Literal["builtins.list"]:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """
        return "builtins.list"

    def getitem(self, index, context: InferenceContext | None = None):
        """Get an item from this node.

        :param index: The node to use as a subscript index.
        :type index: Const or Slice
        """
        return _container_getitem(self, self.elts, index, context=context)


class Nonlocal(_base_nodes.NoChildrenNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Nonlocal` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    def function():
        nonlocal var
    ''')
    >>> node
    <FunctionDef.function l.2 at 0x7f23b2e9e208>
    >>> node.body[0]
    <Nonlocal l.3 at 0x7f23b2e9e908>
    """

    _other_fields = ("names",)

    def __init__(
        self,
        names: list[str],
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param names: The names being declared as not local.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.names: list[str] = names
        """The names being declared as not local."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def _infer_name(self, frame, name):
        return name


class ParamSpec(_base_nodes.AssignTypeNode):
    """Class representing a :class:`ast.ParamSpec` node.

    >>> import astroid
    >>> node = astroid.extract_node('type Alias[**P] = Callable[P, int]')
    >>> node.type_params[0]
    <ParamSpec l.1 at 0x7f23b2e4e198>
    """

    _astroid_fields = ("name",)

    name: AssignName

    def __init__(
        self,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int,
        end_col_offset: int,
    ) -> None:
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, name: AssignName) -> None:
        self.name = name

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[ParamSpec]:
        yield self

    assigned_stmts = protocols.generic_type_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """


class Pass(_base_nodes.NoChildrenNode, _base_nodes.Statement):
    """Class representing an :class:`ast.Pass` node.

    >>> import astroid
    >>> node = astroid.extract_node('pass')
    >>> node
    <Pass l.1 at 0x7f23b2e9e748>
    """


class Raise(_base_nodes.Statement):
    """Class representing an :class:`ast.Raise` node.

    >>> import astroid
    >>> node = astroid.extract_node('raise RuntimeError("Something bad happened!")')
    >>> node
    <Raise l.1 at 0x7f23b2e9e828>
    """

    _astroid_fields = ("exc", "cause")

    exc: NodeNG | None
    """What is being raised."""

    cause: NodeNG | None
    """The exception being used to raise this one."""

    def postinit(
        self,
        exc: NodeNG | None,
        cause: NodeNG | None,
    ) -> None:
        self.exc = exc
        self.cause = cause

    def raises_not_implemented(self) -> bool:
        """Check if this node raises a :class:`NotImplementedError`.

        :returns: Whether this node raises a :class:`NotImplementedError`.
        """
        if not self.exc:
            return False
        return any(
            name.name == "NotImplementedError" for name in self.exc._get_name_nodes()
        )

    def get_children(self):
        if self.exc is not None:
            yield self.exc

        if self.cause is not None:
            yield self.cause


class Return(_base_nodes.Statement):
    """Class representing an :class:`ast.Return` node.

    >>> import astroid
    >>> node = astroid.extract_node('return True')
    >>> node
    <Return l.1 at 0x7f23b8211908>
    """

    _astroid_fields = ("value",)

    value: NodeNG | None
    """The value being returned."""

    def postinit(self, value: NodeNG | None) -> None:
        self.value = value

    def get_children(self):
        if self.value is not None:
            yield self.value

    def is_tuple_return(self):
        return isinstance(self.value, Tuple)

    def _get_return_nodes_skip_functions(self):
        yield self


class Set(BaseContainer):
    """Class representing an :class:`ast.Set` node.

    >>> import astroid
    >>> node = astroid.extract_node('{1, 2, 3}')
    >>> node
    <Set.set l.1 at 0x7f23b2e71d68>
    """

    infer_unary_op = protocols.set_infer_unary_op

    def pytype(self) -> Literal["builtins.set"]:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """
        return "builtins.set"


class Slice(NodeNG):
    """Class representing an :class:`ast.Slice` node.

    >>> import astroid
    >>> node = astroid.extract_node('things[1:3]')
    >>> node
    <Subscript l.1 at 0x7f23b2e71f60>
    >>> node.slice
    <Slice l.1 at 0x7f23b2e71e80>
    """

    _astroid_fields = ("lower", "upper", "step")

    lower: NodeNG | None
    """The lower index in the slice."""

    upper: NodeNG | None
    """The upper index in the slice."""

    step: NodeNG | None
    """The step to take between indexes."""

    def postinit(
        self,
        lower: NodeNG | None,
        upper: NodeNG | None,
        step: NodeNG | None,
    ) -> None:
        self.lower = lower
        self.upper = upper
        self.step = step

    def _wrap_attribute(self, attr):
        """Wrap the empty attributes of the Slice in a Const node."""
        if not attr:
            const = const_factory(attr)
            const.parent = self
            return const
        return attr

    @cached_property
    def _proxied(self) -> nodes.ClassDef:
        builtins = AstroidManager().builtins_module
        return builtins.getattr("slice")[0]

    def pytype(self) -> Literal["builtins.slice"]:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """
        return "builtins.slice"

    def display_type(self) -> Literal["Slice"]:
        """A human readable type of this node.

        :returns: The type of this node.
        """
        return "Slice"

    def igetattr(
        self, attrname: str, context: InferenceContext | None = None
    ) -> Iterator[SuccessfulInferenceResult]:
        """Infer the possible values of the given attribute on the slice.

        :param attrname: The name of the attribute to infer.

        :returns: The inferred possible values.
        """
        if attrname == "start":
            yield self._wrap_attribute(self.lower)
        elif attrname == "stop":
            yield self._wrap_attribute(self.upper)
        elif attrname == "step":
            yield self._wrap_attribute(self.step)
        else:
            yield from self.getattr(attrname, context=context)

    def getattr(self, attrname, context: InferenceContext | None = None):
        return self._proxied.getattr(attrname, context)

    def get_children(self):
        if self.lower is not None:
            yield self.lower

        if self.upper is not None:
            yield self.upper

        if self.step is not None:
            yield self.step

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[Slice]:
        yield self


class Starred(_base_nodes.ParentAssignNode):
    """Class representing an :class:`ast.Starred` node.

    >>> import astroid
    >>> node = astroid.extract_node('*args')
    >>> node
    <Starred l.1 at 0x7f23b2e41978>
    """

    _astroid_fields = ("value",)
    _other_fields = ("ctx",)

    value: NodeNG
    """What is being unpacked."""

    def __init__(
        self,
        ctx: Context,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.ctx = ctx
        """Whether the starred item is assigned to or loaded from."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, value: NodeNG) -> None:
        self.value = value

    assigned_stmts = protocols.starred_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def get_children(self):
        yield self.value


class Subscript(NodeNG):
    """Class representing an :class:`ast.Subscript` node.

    >>> import astroid
    >>> node = astroid.extract_node('things[1:3]')
    >>> node
    <Subscript l.1 at 0x7f23b2e71f60>
    """

    _SUBSCRIPT_SENTINEL = object()
    _astroid_fields = ("value", "slice")
    _other_fields = ("ctx",)

    value: NodeNG
    """What is being indexed."""

    slice: NodeNG
    """The slice being used to lookup."""

    def __init__(
        self,
        ctx: Context,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.ctx = ctx
        """Whether the subscripted item is assigned to or loaded from."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    # pylint: disable=redefined-builtin; had to use the same name as builtin ast module.
    def postinit(self, value: NodeNG, slice: NodeNG) -> None:
        self.value = value
        self.slice = slice

    def get_children(self):
        yield self.value
        yield self.slice

    def _infer_subscript(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """Inference for subscripts.

        We're understanding if the index is a Const
        or a slice, passing the result of inference
        to the value's `getitem` method, which should
        handle each supported index type accordingly.
        """
        from astroid import helpers  # pylint: disable=import-outside-toplevel

        found_one = False
        for value in self.value.infer(context):
            if isinstance(value, util.UninferableBase):
                yield util.Uninferable
                return None
            for index in self.slice.infer(context):
                if isinstance(index, util.UninferableBase):
                    yield util.Uninferable
                    return None

                # Try to deduce the index value.
                index_value = self._SUBSCRIPT_SENTINEL
                if value.__class__ == Instance:
                    index_value = index
                elif index.__class__ == Instance:
                    instance_as_index = helpers.class_instance_as_index(index)
                    if instance_as_index:
                        index_value = instance_as_index
                else:
                    index_value = index

                if index_value is self._SUBSCRIPT_SENTINEL:
                    raise InferenceError(node=self, context=context)

                try:
                    assigned = value.getitem(index_value, context)
                except (
                    AstroidTypeError,
                    AstroidIndexError,
                    AstroidValueError,
                    AttributeInferenceError,
                    AttributeError,
                ) as exc:
                    raise InferenceError(node=self, context=context) from exc

                # Prevent inferring if the inferred subscript
                # is the same as the original subscripted object.
                if self is assigned or isinstance(assigned, util.UninferableBase):
                    yield util.Uninferable
                    return None
                yield from assigned.infer(context)
                found_one = True

        if found_one:
            return InferenceErrorInfo(node=self, context=context)
        return None

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(self, context: InferenceContext | None = None, **kwargs: Any):
        return self._infer_subscript(context, **kwargs)

    @decorators.raise_if_nothing_inferred
    def infer_lhs(self, context: InferenceContext | None = None, **kwargs: Any):
        return self._infer_subscript(context, **kwargs)


class Try(_base_nodes.MultiLineWithElseBlockNode, _base_nodes.Statement):
    """Class representing a :class:`ast.Try` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
        try:
            do_something()
        except Exception as error:
            print("Error!")
        finally:
            print("Cleanup!")
        ''')
    >>> node
    <Try l.2 at 0x7f23b2e41d68>
    """

    _astroid_fields = ("body", "handlers", "orelse", "finalbody")
    _multi_line_block_fields = ("body", "handlers", "orelse", "finalbody")

    def __init__(
        self,
        *,
        lineno: int,
        col_offset: int,
        end_lineno: int,
        end_col_offset: int,
        parent: NodeNG,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.body: list[NodeNG] = []
        """The contents of the block to catch exceptions from."""

        self.handlers: list[ExceptHandler] = []
        """The exception handlers."""

        self.orelse: list[NodeNG] = []
        """The contents of the ``else`` block."""

        self.finalbody: list[NodeNG] = []
        """The contents of the ``finally`` block."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        body: list[NodeNG],
        handlers: list[ExceptHandler],
        orelse: list[NodeNG],
        finalbody: list[NodeNG],
    ) -> None:
        """Do some setup after initialisation.

        :param body: The contents of the block to catch exceptions from.

        :param handlers: The exception handlers.

        :param orelse: The contents of the ``else`` block.

        :param finalbody: The contents of the ``finally`` block.
        """
        self.body = body
        self.handlers = handlers
        self.orelse = orelse
        self.finalbody = finalbody

    def _infer_name(self, frame, name):
        return name

    def block_range(self, lineno: int) -> tuple[int, int]:
        """Get a range from a given line number to where this node ends."""
        if lineno == self.fromlineno:
            return lineno, lineno
        if self.body and self.body[0].fromlineno <= lineno <= self.body[-1].tolineno:
            # Inside try body - return from lineno till end of try body
            return lineno, self.body[-1].tolineno
        for exhandler in self.handlers:
            if exhandler.type and lineno == exhandler.type.fromlineno:
                return lineno, lineno
            if exhandler.body[0].fromlineno <= lineno <= exhandler.body[-1].tolineno:
                return lineno, exhandler.body[-1].tolineno
        if self.orelse:
            if self.orelse[0].fromlineno - 1 == lineno:
                return lineno, lineno
            if self.orelse[0].fromlineno <= lineno <= self.orelse[-1].tolineno:
                return lineno, self.orelse[-1].tolineno
        if self.finalbody:
            if self.finalbody[0].fromlineno - 1 == lineno:
                return lineno, lineno
            if self.finalbody[0].fromlineno <= lineno <= self.finalbody[-1].tolineno:
                return lineno, self.finalbody[-1].tolineno
        return lineno, self.tolineno

    def get_children(self):
        yield from self.body
        yield from self.handlers
        yield from self.orelse
        yield from self.finalbody


class TryStar(_base_nodes.MultiLineWithElseBlockNode, _base_nodes.Statement):
    """Class representing an :class:`ast.TryStar` node."""

    _astroid_fields = ("body", "handlers", "orelse", "finalbody")
    _multi_line_block_fields = ("body", "handlers", "orelse", "finalbody")

    def __init__(
        self,
        *,
        lineno: int | None = None,
        col_offset: int | None = None,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
        parent: NodeNG | None = None,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.
        :param col_offset: The column that this node appears on in the
            source code.
        :param parent: The parent node in the syntax tree.
        :param end_lineno: The last line this node appears on in the source code.
        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.body: list[NodeNG] = []
        """The contents of the block to catch exceptions from."""

        self.handlers: list[ExceptHandler] = []
        """The exception handlers."""

        self.orelse: list[NodeNG] = []
        """The contents of the ``else`` block."""

        self.finalbody: list[NodeNG] = []
        """The contents of the ``finally`` block."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        body: list[NodeNG] | None = None,
        handlers: list[ExceptHandler] | None = None,
        orelse: list[NodeNG] | None = None,
        finalbody: list[NodeNG] | None = None,
    ) -> None:
        """Do some setup after initialisation.
        :param body: The contents of the block to catch exceptions from.
        :param handlers: The exception handlers.
        :param orelse: The contents of the ``else`` block.
        :param finalbody: The contents of the ``finally`` block.
        """
        if body:
            self.body = body
        if handlers:
            self.handlers = handlers
        if orelse:
            self.orelse = orelse
        if finalbody:
            self.finalbody = finalbody

    def _infer_name(self, frame, name):
        return name

    def block_range(self, lineno: int) -> tuple[int, int]:
        """Get a range from a given line number to where this node ends."""
        if lineno == self.fromlineno:
            return lineno, lineno
        if self.body and self.body[0].fromlineno <= lineno <= self.body[-1].tolineno:
            # Inside try body - return from lineno till end of try body
            return lineno, self.body[-1].tolineno
        for exhandler in self.handlers:
            if exhandler.type and lineno == exhandler.type.fromlineno:
                return lineno, lineno
            if exhandler.body[0].fromlineno <= lineno <= exhandler.body[-1].tolineno:
                return lineno, exhandler.body[-1].tolineno
        if self.orelse:
            if self.orelse[0].fromlineno - 1 == lineno:
                return lineno, lineno
            if self.orelse[0].fromlineno <= lineno <= self.orelse[-1].tolineno:
                return lineno, self.orelse[-1].tolineno
        if self.finalbody:
            if self.finalbody[0].fromlineno - 1 == lineno:
                return lineno, lineno
            if self.finalbody[0].fromlineno <= lineno <= self.finalbody[-1].tolineno:
                return lineno, self.finalbody[-1].tolineno
        return lineno, self.tolineno

    def get_children(self):
        yield from self.body
        yield from self.handlers
        yield from self.orelse
        yield from self.finalbody


class Tuple(BaseContainer):
    """Class representing an :class:`ast.Tuple` node.

    >>> import astroid
    >>> node = astroid.extract_node('(1, 2, 3)')
    >>> node
    <Tuple.tuple l.1 at 0x7f23b2e41780>
    """

    _other_fields = ("ctx",)

    def __init__(
        self,
        ctx: Context | None = None,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param ctx: Whether the tuple is assigned to or loaded from.

        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.ctx: Context | None = ctx
        """Whether the tuple is assigned to or loaded from."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    assigned_stmts = protocols.sequence_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    infer_unary_op = protocols.tuple_infer_unary_op
    infer_binary_op = protocols.tl_infer_binary_op

    def pytype(self) -> Literal["builtins.tuple"]:
        """Get the name of the type that this node represents.

        :returns: The name of the type.
        """
        return "builtins.tuple"

    def getitem(self, index, context: InferenceContext | None = None):
        """Get an item from this node.

        :param index: The node to use as a subscript index.
        :type index: Const or Slice
        """
        return _container_getitem(self, self.elts, index, context=context)


class TypeAlias(_base_nodes.AssignTypeNode, _base_nodes.Statement):
    """Class representing a :class:`ast.TypeAlias` node.

    >>> import astroid
    >>> node = astroid.extract_node('type Point = tuple[float, float]')
    >>> node
    <TypeAlias l.1 at 0x7f23b2e4e198>
    """

    _astroid_fields = ("name", "type_params", "value")

    name: AssignName
    type_params: list[TypeVar | ParamSpec | TypeVarTuple]
    value: NodeNG

    def __init__(
        self,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int,
        end_col_offset: int,
    ) -> None:
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        name: AssignName,
        type_params: list[TypeVar | ParamSpec | TypeVarTuple],
        value: NodeNG,
    ) -> None:
        self.name = name
        self.type_params = type_params
        self.value = value

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[TypeAlias]:
        yield self

    assigned_stmts: ClassVar[
        Callable[
            [
                TypeAlias,
                AssignName,
                InferenceContext | None,
                None,
            ],
            Generator[NodeNG],
        ]
    ] = protocols.assign_assigned_stmts


class TypeVar(_base_nodes.AssignTypeNode):
    """Class representing a :class:`ast.TypeVar` node.

    >>> import astroid
    >>> node = astroid.extract_node('type Point[T] = tuple[float, float]')
    >>> node.type_params[0]
    <TypeVar l.1 at 0x7f23b2e4e198>
    """

    _astroid_fields = ("name", "bound")

    name: AssignName
    bound: NodeNG | None

    def __init__(
        self,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int,
        end_col_offset: int,
    ) -> None:
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, name: AssignName, bound: NodeNG | None) -> None:
        self.name = name
        self.bound = bound

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[TypeVar]:
        yield self

    assigned_stmts = protocols.generic_type_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """


class TypeVarTuple(_base_nodes.AssignTypeNode):
    """Class representing a :class:`ast.TypeVarTuple` node.

    >>> import astroid
    >>> node = astroid.extract_node('type Alias[*Ts] = tuple[*Ts]')
    >>> node.type_params[0]
    <TypeVarTuple l.1 at 0x7f23b2e4e198>
    """

    _astroid_fields = ("name",)

    name: AssignName

    def __init__(
        self,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int,
        end_col_offset: int,
    ) -> None:
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, name: AssignName) -> None:
        self.name = name

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Iterator[TypeVarTuple]:
        yield self

    assigned_stmts = protocols.generic_type_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """


UNARY_OP_METHOD = {
    "+": "__pos__",
    "-": "__neg__",
    "~": "__invert__",
    "not": None,  # XXX not '__nonzero__'
}


class UnaryOp(_base_nodes.OperatorNode):
    """Class representing an :class:`ast.UnaryOp` node.

    >>> import astroid
    >>> node = astroid.extract_node('-5')
    >>> node
    <UnaryOp l.1 at 0x7f23b2e4e198>
    """

    _astroid_fields = ("operand",)
    _other_fields = ("op",)

    operand: NodeNG
    """What the unary operator is applied to."""

    def __init__(
        self,
        op: str,
        lineno: int,
        col_offset: int,
        parent: NodeNG,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.op = op
        """The operator."""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, operand: NodeNG) -> None:
        self.operand = operand

    def type_errors(
        self, context: InferenceContext | None = None
    ) -> list[util.BadUnaryOperationMessage]:
        """Get a list of type errors which can occur during inference.

        Each TypeError is represented by a :class:`BadUnaryOperationMessage`,
        which holds the original exception.

        If any inferred result is uninferable, an empty list is returned.
        """
        bad = []
        try:
            for result in self._infer_unaryop(context=context):
                if result is util.Uninferable:
                    raise InferenceError
                if isinstance(result, util.BadUnaryOperationMessage):
                    bad.append(result)
        except InferenceError:
            return []
        return bad

    def get_children(self):
        yield self.operand

    def op_precedence(self):
        if self.op == "not":
            return OP_PRECEDENCE[self.op]

        return super().op_precedence()

    def _infer_unaryop(
        self: nodes.UnaryOp, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[
        InferenceResult | util.BadUnaryOperationMessage, None, InferenceErrorInfo
    ]:
        """Infer what an UnaryOp should return when evaluated."""
        from astroid.nodes import ClassDef  # pylint: disable=import-outside-toplevel

        for operand in self.operand.infer(context):
            try:
                yield operand.infer_unary_op(self.op)
            except TypeError as exc:
                # The operand doesn't support this operation.
                yield util.BadUnaryOperationMessage(operand, self.op, exc)
            except AttributeError as exc:
                meth = UNARY_OP_METHOD[self.op]
                if meth is None:
                    # `not node`. Determine node's boolean
                    # value and negate its result, unless it is
                    # Uninferable, which will be returned as is.
                    bool_value = operand.bool_value()
                    if not isinstance(bool_value, util.UninferableBase):
                        yield const_factory(not bool_value)
                    else:
                        yield util.Uninferable
                else:
                    if not isinstance(operand, (Instance, ClassDef)):
                        # The operation was used on something which
                        # doesn't support it.
                        yield util.BadUnaryOperationMessage(operand, self.op, exc)
                        continue

                    try:
                        try:
                            methods = dunder_lookup.lookup(operand, meth)
                        except AttributeInferenceError:
                            yield util.BadUnaryOperationMessage(operand, self.op, exc)
                            continue

                        meth = methods[0]
                        inferred = next(meth.infer(context=context), None)
                        if (
                            isinstance(inferred, util.UninferableBase)
                            or not inferred.callable()
                        ):
                            continue

                        context = copy_context(context)
                        context.boundnode = operand
                        context.callcontext = CallContext(args=[], callee=inferred)

                        call_results = inferred.infer_call_result(self, context=context)
                        result = next(call_results, None)
                        if result is None:
                            # Failed to infer, return the same type.
                            yield operand
                        else:
                            yield result
                    except AttributeInferenceError as inner_exc:
                        # The unary operation special method was not found.
                        yield util.BadUnaryOperationMessage(operand, self.op, inner_exc)
                    except InferenceError:
                        yield util.Uninferable

    @decorators.raise_if_nothing_inferred
    @decorators.path_wrapper
    def _infer(
        self: nodes.UnaryOp, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo]:
        """Infer what an UnaryOp should return when evaluated."""
        yield from self._filter_operation_errors(
            self._infer_unaryop, context, util.BadUnaryOperationMessage
        )
        return InferenceErrorInfo(node=self, context=context)


class While(_base_nodes.MultiLineWithElseBlockNode, _base_nodes.Statement):
    """Class representing an :class:`ast.While` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    while condition():
        print("True")
    ''')
    >>> node
    <While l.2 at 0x7f23b2e4e390>
    """

    _astroid_fields = ("test", "body", "orelse")
    _multi_line_block_fields = ("body", "orelse")

    test: NodeNG
    """The condition that the loop tests."""

    body: list[NodeNG]
    """The contents of the loop."""

    orelse: list[NodeNG]
    """The contents of the ``else`` block."""

    def postinit(
        self,
        test: NodeNG,
        body: list[NodeNG],
        orelse: list[NodeNG],
    ) -> None:
        self.test = test
        self.body = body
        self.orelse = orelse

    @cached_property
    def blockstart_tolineno(self):
        """The line on which the beginning of this block ends.

        :type: int
        """
        return self.test.tolineno

    def block_range(self, lineno: int) -> tuple[int, int]:
        """Get a range from the given line number to where this node ends.

        :param lineno: The line number to start the range at.

        :returns: The range of line numbers that this node belongs to,
            starting at the given line number.
        """
        return self._elsed_block_range(lineno, self.orelse)

    def get_children(self):
        yield self.test

        yield from self.body
        yield from self.orelse

    def _get_yield_nodes_skip_functions(self):
        """A While node can contain a Yield node in the test"""
        yield from self.test._get_yield_nodes_skip_functions()
        yield from super()._get_yield_nodes_skip_functions()

    def _get_yield_nodes_skip_lambdas(self):
        """A While node can contain a Yield node in the test"""
        yield from self.test._get_yield_nodes_skip_lambdas()
        yield from super()._get_yield_nodes_skip_lambdas()


class With(
    _base_nodes.MultiLineWithElseBlockNode,
    _base_nodes.AssignTypeNode,
    _base_nodes.Statement,
):
    """Class representing an :class:`ast.With` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    with open(file_path) as file_:
        print(file_.read())
    ''')
    >>> node
    <With l.2 at 0x7f23b2e4e710>
    """

    _astroid_fields = ("items", "body")
    _other_other_fields = ("type_annotation",)
    _multi_line_block_fields = ("body",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.items: list[tuple[NodeNG, NodeNG | None]] = []
        """The pairs of context managers and the names they are assigned to."""

        self.body: list[NodeNG] = []
        """The contents of the ``with`` block."""

        self.type_annotation: NodeNG | None = None  # can be None
        """If present, this will contain the type annotation passed by a type comment"""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        items: list[tuple[NodeNG, NodeNG | None]] | None = None,
        body: list[NodeNG] | None = None,
        type_annotation: NodeNG | None = None,
    ) -> None:
        """Do some setup after initialisation.

        :param items: The pairs of context managers and the names
            they are assigned to.

        :param body: The contents of the ``with`` block.
        """
        if items is not None:
            self.items = items
        if body is not None:
            self.body = body
        self.type_annotation = type_annotation

    assigned_stmts = protocols.with_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    @cached_property
    def blockstart_tolineno(self):
        """The line on which the beginning of this block ends.

        :type: int
        """
        return self.items[-1][0].tolineno

    def get_children(self):
        """Get the child nodes below this node.

        :returns: The children.
        :rtype: iterable(NodeNG)
        """
        for expr, var in self.items:
            yield expr
            if var:
                yield var
        yield from self.body


class AsyncWith(With):
    """Asynchronous ``with`` built with the ``async`` keyword."""


class Yield(NodeNG):
    """Class representing an :class:`ast.Yield` node.

    >>> import astroid
    >>> node = astroid.extract_node('yield True')
    >>> node
    <Yield l.1 at 0x7f23b2e4e5f8>
    """

    _astroid_fields = ("value",)

    value: NodeNG | None
    """The value to yield."""

    def postinit(self, value: NodeNG | None) -> None:
        self.value = value

    def get_children(self):
        if self.value is not None:
            yield self.value

    def _get_yield_nodes_skip_functions(self):
        yield self

    def _get_yield_nodes_skip_lambdas(self):
        yield self


class YieldFrom(Yield):  # TODO value is required, not optional
    """Class representing an :class:`ast.YieldFrom` node."""


class DictUnpack(_base_nodes.NoChildrenNode):
    """Represents the unpacking of dicts into dicts using :pep:`448`."""


class FormattedValue(NodeNG):
    """Class representing an :class:`ast.FormattedValue` node.

    Represents a :pep:`498` format string.

    >>> import astroid
    >>> node = astroid.extract_node('f"Format {type_}"')
    >>> node
    <JoinedStr l.1 at 0x7f23b2e4ed30>
    >>> node.values
    [<Const.str l.1 at 0x7f23b2e4eda0>, <FormattedValue l.1 at 0x7f23b2e4edd8>]
    """

    _astroid_fields = ("value", "format_spec")
    _other_fields = ("conversion",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.value: NodeNG
        """The value to be formatted into the string."""

        self.conversion: int
        """The type of formatting to be applied to the value.

        .. seealso::
            :class:`ast.FormattedValue`
        """

        self.format_spec: JoinedStr | None = None
        """The formatting to be applied to the value.

        .. seealso::
            :class:`ast.FormattedValue`
        """

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        value: NodeNG,
        conversion: int,
        format_spec: JoinedStr | None = None,
    ) -> None:
        """Do some setup after initialisation.

        :param value: The value to be formatted into the string.

        :param conversion: The type of formatting to be applied to the value.

        :param format_spec: The formatting to be applied to the value.
        :type format_spec: JoinedStr or None
        """
        self.value = value
        self.conversion = conversion
        self.format_spec = format_spec

    def get_children(self):
        yield self.value

        if self.format_spec is not None:
            yield self.format_spec

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        format_specs = Const("") if self.format_spec is None else self.format_spec
        uninferable_already_generated = False
        for format_spec in format_specs.infer(context, **kwargs):
            if not isinstance(format_spec, Const):
                if not uninferable_already_generated:
                    yield util.Uninferable
                    uninferable_already_generated = True
                continue
            for value in self.value.infer(context, **kwargs):
                value_to_format = value
                if isinstance(value, Const):
                    value_to_format = value.value
                try:
                    formatted = format(value_to_format, format_spec.value)
                    yield Const(
                        formatted,
                        lineno=self.lineno,
                        col_offset=self.col_offset,
                        end_lineno=self.end_lineno,
                        end_col_offset=self.end_col_offset,
                    )
                    continue
                except (ValueError, TypeError):
                    # happens when format_spec.value is invalid
                    yield util.Uninferable
                    uninferable_already_generated = True
                continue


MISSING_VALUE = "{MISSING_VALUE}"


class JoinedStr(NodeNG):
    """Represents a list of string expressions to be joined.

    >>> import astroid
    >>> node = astroid.extract_node('f"Format {type_}"')
    >>> node
    <JoinedStr l.1 at 0x7f23b2e4ed30>
    """

    _astroid_fields = ("values",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.values: list[NodeNG] = []
        """The string expressions to be joined.

        :type: list(FormattedValue or Const)
        """

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, values: list[NodeNG] | None = None) -> None:
        """Do some setup after initialisation.

        :param value: The string expressions to be joined.

        :type: list(FormattedValue or Const)
        """
        if values is not None:
            self.values = values

    def get_children(self):
        yield from self.values

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        yield from self._infer_from_values(self.values, context)

    @classmethod
    def _infer_from_values(
        cls, nodes: list[NodeNG], context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        if not nodes:
            yield
            return
        if len(nodes) == 1:
            yield from nodes[0]._infer(context, **kwargs)
            return
        uninferable_already_generated = False
        for prefix in nodes[0]._infer(context, **kwargs):
            for suffix in cls._infer_from_values(nodes[1:], context, **kwargs):
                result = ""
                for node in (prefix, suffix):
                    if isinstance(node, Const):
                        result += str(node.value)
                        continue
                    result += MISSING_VALUE
                if MISSING_VALUE in result:
                    if not uninferable_already_generated:
                        uninferable_already_generated = True
                        yield util.Uninferable
                else:
                    yield Const(result)


class NamedExpr(_base_nodes.AssignTypeNode):
    """Represents the assignment from the assignment expression

    >>> import astroid
    >>> module = astroid.parse('if a := 1: pass')
    >>> module.body[0].test
    <NamedExpr l.1 at 0x7f23b2e4ed30>
    """

    _astroid_fields = ("target", "value")

    optional_assign = True
    """Whether this node optionally assigns a variable.

    Since NamedExpr are not always called they do not always assign."""

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.target: NodeNG
        """The assignment target

        :type: Name
        """

        self.value: NodeNG
        """The value that gets assigned in the expression"""

        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, target: NodeNG, value: NodeNG) -> None:
        self.target = target
        self.value = value

    assigned_stmts = protocols.named_expr_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """

    def frame(
        self, *, future: Literal[None, True] = None
    ) -> nodes.FunctionDef | nodes.Module | nodes.ClassDef | nodes.Lambda:
        """The first parent frame node.

        A frame node is a :class:`Module`, :class:`FunctionDef`,
        or :class:`ClassDef`.

        :returns: The first parent frame node.
        """
        if future is not None:
            warnings.warn(
                "The future arg will be removed in astroid 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )
        if not self.parent:
            raise ParentMissingError(target=self)

        # For certain parents NamedExpr evaluate to the scope of the parent
        if isinstance(self.parent, (Arguments, Keyword, Comprehension)):
            if not self.parent.parent:
                raise ParentMissingError(target=self.parent)
            if not self.parent.parent.parent:
                raise ParentMissingError(target=self.parent.parent)
            return self.parent.parent.parent.frame()

        return self.parent.frame()

    def scope(self) -> LocalsDictNodeNG:
        """The first parent node defining a new scope.
        These can be Module, FunctionDef, ClassDef, Lambda, or GeneratorExp nodes.

        :returns: The first parent scope node.
        """
        if not self.parent:
            raise ParentMissingError(target=self)

        # For certain parents NamedExpr evaluate to the scope of the parent
        if isinstance(self.parent, (Arguments, Keyword, Comprehension)):
            if not self.parent.parent:
                raise ParentMissingError(target=self.parent)
            if not self.parent.parent.parent:
                raise ParentMissingError(target=self.parent.parent)
            return self.parent.parent.parent.scope()

        return self.parent.scope()

    def set_local(self, name: str, stmt: NodeNG) -> None:
        """Define that the given name is declared in the given statement node.
        NamedExpr's in Arguments, Keyword or Comprehension are evaluated in their
        parent's parent scope. So we add to their frame's locals.

        .. seealso:: :meth:`scope`

        :param name: The name that is being defined.

        :param stmt: The statement that defines the given name.
        """
        self.frame().set_local(name, stmt)


class Unknown(_base_nodes.AssignTypeNode):
    """This node represents a node in a constructed AST where
    introspection is not possible.  At the moment, it's only used in
    the args attribute of FunctionDef nodes where function signature
    introspection failed.
    """

    name = "Unknown"

    def __init__(
        self,
        lineno: None = None,
        col_offset: None = None,
        parent: None = None,
        *,
        end_lineno: None = None,
        end_col_offset: None = None,
    ) -> None:
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def qname(self) -> Literal["Unknown"]:
        return "Unknown"

    def _infer(self, context: InferenceContext | None = None, **kwargs):
        """Inference on an Unknown node immediately terminates."""
        yield util.Uninferable


class EvaluatedObject(NodeNG):
    """Contains an object that has already been inferred

    This class is useful to pre-evaluate a particular node,
    with the resulting class acting as the non-evaluated node.
    """

    name = "EvaluatedObject"
    _astroid_fields = ("original",)
    _other_fields = ("value",)

    def __init__(
        self, original: SuccessfulInferenceResult, value: InferenceResult
    ) -> None:
        self.original: SuccessfulInferenceResult = original
        """The original node that has already been evaluated"""

        self.value: InferenceResult = value
        """The inferred value"""

        super().__init__(
            lineno=self.original.lineno,
            col_offset=self.original.col_offset,
            parent=self.original.parent,
            end_lineno=self.original.end_lineno,
            end_col_offset=self.original.end_col_offset,
        )

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[NodeNG | util.UninferableBase]:
        yield self.value


# Pattern matching #######################################################


class Match(_base_nodes.Statement, _base_nodes.MultiLineBlockNode):
    """Class representing a :class:`ast.Match` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case 200:
            ...
        case _:
            ...
    ''')
    >>> node
    <Match l.2 at 0x10c24e170>
    """

    _astroid_fields = ("subject", "cases")
    _multi_line_block_fields = ("cases",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.subject: NodeNG
        self.cases: list[MatchCase]
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        subject: NodeNG,
        cases: list[MatchCase],
    ) -> None:
        self.subject = subject
        self.cases = cases


class Pattern(NodeNG):
    """Base class for all Pattern nodes."""


class MatchCase(_base_nodes.MultiLineBlockNode):
    """Class representing a :class:`ast.match_case` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case 200:
            ...
    ''')
    >>> node.cases[0]
    <MatchCase l.3 at 0x10c24e590>
    """

    _astroid_fields = ("pattern", "guard", "body")
    _multi_line_block_fields = ("body",)

    lineno: None
    col_offset: None
    end_lineno: None
    end_col_offset: None

    def __init__(self, *, parent: NodeNG | None = None) -> None:
        self.pattern: Pattern
        self.guard: NodeNG | None
        self.body: list[NodeNG]
        super().__init__(
            parent=parent,
            lineno=None,
            col_offset=None,
            end_lineno=None,
            end_col_offset=None,
        )

    def postinit(
        self,
        *,
        pattern: Pattern,
        guard: NodeNG | None,
        body: list[NodeNG],
    ) -> None:
        self.pattern = pattern
        self.guard = guard
        self.body = body


class MatchValue(Pattern):
    """Class representing a :class:`ast.MatchValue` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case 200:
            ...
    ''')
    >>> node.cases[0].pattern
    <MatchValue l.3 at 0x10c24e200>
    """

    _astroid_fields = ("value",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.value: NodeNG
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, value: NodeNG) -> None:
        self.value = value


class MatchSingleton(Pattern):
    """Class representing a :class:`ast.MatchSingleton` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case True:
            ...
        case False:
            ...
        case None:
            ...
    ''')
    >>> node.cases[0].pattern
    <MatchSingleton l.3 at 0x10c2282e0>
    >>> node.cases[1].pattern
    <MatchSingleton l.5 at 0x10c228af0>
    >>> node.cases[2].pattern
    <MatchSingleton l.7 at 0x10c229f90>
    """

    _other_fields = ("value",)

    def __init__(
        self,
        *,
        value: Literal[True, False, None],
        lineno: int | None = None,
        col_offset: int | None = None,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
        parent: NodeNG | None = None,
    ) -> None:
        self.value = value
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )


class MatchSequence(Pattern):
    """Class representing a :class:`ast.MatchSequence` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case [1, 2]:
            ...
        case (1, 2, *_):
            ...
    ''')
    >>> node.cases[0].pattern
    <MatchSequence l.3 at 0x10ca80d00>
    >>> node.cases[1].pattern
    <MatchSequence l.5 at 0x10ca80b20>
    """

    _astroid_fields = ("patterns",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.patterns: list[Pattern]
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, patterns: list[Pattern]) -> None:
        self.patterns = patterns


class MatchMapping(_base_nodes.AssignTypeNode, Pattern):
    """Class representing a :class:`ast.MatchMapping` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case {1: "Hello", 2: "World", 3: _, **rest}:
            ...
    ''')
    >>> node.cases[0].pattern
    <MatchMapping l.3 at 0x10c8a8850>
    """

    _astroid_fields = ("keys", "patterns", "rest")

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.keys: list[NodeNG]
        self.patterns: list[Pattern]
        self.rest: AssignName | None
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        keys: list[NodeNG],
        patterns: list[Pattern],
        rest: AssignName | None,
    ) -> None:
        self.keys = keys
        self.patterns = patterns
        self.rest = rest

    assigned_stmts = protocols.match_mapping_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """


class MatchClass(Pattern):
    """Class representing a :class:`ast.MatchClass` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case Point2D(0, 0):
            ...
        case Point3D(x=0, y=0, z=0):
            ...
    ''')
    >>> node.cases[0].pattern
    <MatchClass l.3 at 0x10ca83940>
    >>> node.cases[1].pattern
    <MatchClass l.5 at 0x10ca80880>
    """

    _astroid_fields = ("cls", "patterns", "kwd_patterns")
    _other_fields = ("kwd_attrs",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.cls: NodeNG
        self.patterns: list[Pattern]
        self.kwd_attrs: list[str]
        self.kwd_patterns: list[Pattern]
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        cls: NodeNG,
        patterns: list[Pattern],
        kwd_attrs: list[str],
        kwd_patterns: list[Pattern],
    ) -> None:
        self.cls = cls
        self.patterns = patterns
        self.kwd_attrs = kwd_attrs
        self.kwd_patterns = kwd_patterns


class MatchStar(_base_nodes.AssignTypeNode, Pattern):
    """Class representing a :class:`ast.MatchStar` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case [1, *_]:
            ...
    ''')
    >>> node.cases[0].pattern.patterns[1]
    <MatchStar l.3 at 0x10ca809a0>
    """

    _astroid_fields = ("name",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.name: AssignName | None
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, name: AssignName | None) -> None:
        self.name = name

    assigned_stmts = protocols.match_star_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """


class MatchAs(_base_nodes.AssignTypeNode, Pattern):
    """Class representing a :class:`ast.MatchAs` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case [1, a]:
            ...
        case {'key': b}:
            ...
        case Point2D(0, 0) as c:
            ...
        case d:
            ...
    ''')
    >>> node.cases[0].pattern.patterns[1]
    <MatchAs l.3 at 0x10d0b2da0>
    >>> node.cases[1].pattern.patterns[0]
    <MatchAs l.5 at 0x10d0b2920>
    >>> node.cases[2].pattern
    <MatchAs l.7 at 0x10d0b06a0>
    >>> node.cases[3].pattern
    <MatchAs l.9 at 0x10d09b880>
    """

    _astroid_fields = ("pattern", "name")

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.pattern: Pattern | None
        self.name: AssignName | None
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(
        self,
        *,
        pattern: Pattern | None,
        name: AssignName | None,
    ) -> None:
        self.pattern = pattern
        self.name = name

    assigned_stmts = protocols.match_as_assigned_stmts
    """Returns the assigned statement (non inferred) according to the assignment type.
    See astroid/protocols.py for actual implementation.
    """


class MatchOr(Pattern):
    """Class representing a :class:`ast.MatchOr` node.

    >>> import astroid
    >>> node = astroid.extract_node('''
    match x:
        case 400 | 401 | 402:
            ...
    ''')
    >>> node.cases[0].pattern
    <MatchOr l.3 at 0x10d0b0b50>
    """

    _astroid_fields = ("patterns",)

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.patterns: list[Pattern]
        super().__init__(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )

    def postinit(self, *, patterns: list[Pattern]) -> None:
        self.patterns = patterns


# constants ##############################################################

# The _proxied attribute of all container types (List, Tuple, etc.)
# are set during bootstrapping by _astroid_bootstrapping().
CONST_CLS: dict[type, type[NodeNG]] = {
    list: List,
    tuple: Tuple,
    dict: Dict,
    set: Set,
    type(None): Const,
    type(NotImplemented): Const,
    type(...): Const,
    bool: Const,
    int: Const,
    float: Const,
    complex: Const,
    str: Const,
    bytes: Const,
}


def _create_basic_elements(
    value: Iterable[Any], node: List | Set | Tuple
) -> list[NodeNG]:
    """Create a list of nodes to function as the elements of a new node."""
    elements: list[NodeNG] = []
    for element in value:
        # NOTE: avoid accessing any attributes of element in the loop.
        element_node = const_factory(element)
        element_node.parent = node
        elements.append(element_node)
    return elements


def _create_dict_items(
    values: Mapping[Any, Any], node: Dict
) -> list[tuple[SuccessfulInferenceResult, SuccessfulInferenceResult]]:
    """Create a list of node pairs to function as the items of a new dict node."""
    elements: list[tuple[SuccessfulInferenceResult, SuccessfulInferenceResult]] = []
    for key, value in values.items():
        # NOTE: avoid accessing any attributes of both key and value in the loop.
        key_node = const_factory(key)
        key_node.parent = node
        value_node = const_factory(value)
        value_node.parent = node
        elements.append((key_node, value_node))
    return elements


def const_factory(value: Any) -> ConstFactoryResult:
    """Return an astroid node for a python value."""
    # NOTE: avoid accessing any attributes of value until it is known that value
    # is of a const type, to avoid possibly triggering code for a live object.
    # Accesses include value.__class__ and isinstance(value, ...), but not type(value).
    # See: https://github.com/pylint-dev/astroid/issues/2686
    value_type = type(value)
    assert not issubclass(value_type, NodeNG)

    # This only handles instances of the CONST types. Any
    # subclasses get inferred as EmptyNode.
    # TODO: See if we should revisit these with the normal builder.
    if value_type not in CONST_CLS:
        node = EmptyNode()
        node.object = value
        return node

    instance: List | Set | Tuple | Dict
    initializer_cls = CONST_CLS[value_type]
    if issubclass(initializer_cls, (List, Set, Tuple)):
        instance = initializer_cls(
            lineno=None,
            col_offset=None,
            parent=None,
            end_lineno=None,
            end_col_offset=None,
        )
        instance.postinit(_create_basic_elements(value, instance))
        return instance
    if issubclass(initializer_cls, Dict):
        instance = initializer_cls(
            lineno=None,
            col_offset=None,
            parent=None,
            end_lineno=None,
            end_col_offset=None,
        )
        instance.postinit(_create_dict_items(value, instance))
        return instance
    return Const(value)
