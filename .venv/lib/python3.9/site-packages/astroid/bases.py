# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains base classes and functions for the nodes and some
inference utils.
"""
from __future__ import annotations

import collections
import collections.abc
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, Literal

from astroid import decorators, nodes
from astroid.const import PY310_PLUS
from astroid.context import (
    CallContext,
    InferenceContext,
    bind_context_to_node,
    copy_context,
)
from astroid.exceptions import (
    AstroidTypeError,
    AttributeInferenceError,
    InferenceError,
    NameInferenceError,
)
from astroid.interpreter import objectmodel
from astroid.typing import (
    InferenceErrorInfo,
    InferenceResult,
    SuccessfulInferenceResult,
)
from astroid.util import Uninferable, UninferableBase, safe_infer

if TYPE_CHECKING:
    from astroid.constraint import Constraint


PROPERTIES = {"builtins.property", "abc.abstractproperty"}
if PY310_PLUS:
    PROPERTIES.add("enum.property")

# List of possible property names. We use this list in order
# to see if a method is a property or not. This should be
# pretty reliable and fast, the alternative being to check each
# decorator to see if its a real property-like descriptor, which
# can be too complicated.
# Also, these aren't qualified, because each project can
# define them, we shouldn't expect to know every possible
# property-like decorator!
POSSIBLE_PROPERTIES = {
    "cached_property",
    "cachedproperty",
    "lazyproperty",
    "lazy_property",
    "reify",
    "lazyattribute",
    "lazy_attribute",
    "LazyProperty",
    "lazy",
    "cache_readonly",
    "DynamicClassAttribute",
}


def _is_property(
    meth: nodes.FunctionDef | UnboundMethod, context: InferenceContext | None = None
) -> bool:
    decoratornames = meth.decoratornames(context=context)
    if PROPERTIES.intersection(decoratornames):
        return True
    stripped = {
        name.split(".")[-1]
        for name in decoratornames
        if not isinstance(name, UninferableBase)
    }
    if any(name in stripped for name in POSSIBLE_PROPERTIES):
        return True

    # Lookup for subclasses of *property*
    if not meth.decorators:
        return False
    for decorator in meth.decorators.nodes or ():
        inferred = safe_infer(decorator, context=context)
        if inferred is None or isinstance(inferred, UninferableBase):
            continue
        if isinstance(inferred, nodes.ClassDef):
            for base_class in inferred.bases:
                if not isinstance(base_class, nodes.Name):
                    continue
                module, _ = base_class.lookup(base_class.name)
                if (
                    isinstance(module, nodes.Module)
                    and module.name == "builtins"
                    and base_class.name == "property"
                ):
                    return True

    return False


class Proxy:
    """A simple proxy object.

    Note:

    Subclasses of this object will need a custom __getattr__
    if new instance attributes are created. See the Const class
    """

    _proxied: nodes.ClassDef | nodes.FunctionDef | nodes.Lambda | UnboundMethod

    def __init__(
        self,
        proxied: (
            nodes.ClassDef | nodes.FunctionDef | nodes.Lambda | UnboundMethod | None
        ) = None,
    ) -> None:
        if proxied is None:
            # This is a hack to allow calling this __init__ during bootstrapping of
            # builtin classes and their docstrings.
            # For Const, Generator, and UnionType nodes the _proxied attribute
            # is set during bootstrapping
            # as we first need to build the ClassDef that they can proxy.
            # Thus, if proxied is None self should be a Const or Generator
            # as that is the only way _proxied will be correctly set as a ClassDef.
            assert isinstance(self, (nodes.Const, Generator, UnionType))
        else:
            self._proxied = proxied

    def __getattr__(self, name: str) -> Any:
        if name == "_proxied":
            return self.__class__._proxied
        if name in self.__dict__:
            return self.__dict__[name]
        return getattr(self._proxied, name)

    def infer(  # type: ignore[return]
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> collections.abc.Generator[InferenceResult, None, InferenceErrorInfo | None]:
        yield self


def _infer_stmts(
    stmts: Iterable[InferenceResult],
    context: InferenceContext | None,
    frame: nodes.NodeNG | BaseInstance | None = None,
) -> collections.abc.Generator[InferenceResult]:
    """Return an iterator on statements inferred by each statement in *stmts*."""
    inferred = False
    constraint_failed = False
    if context is not None:
        name = context.lookupname
        context = context.clone()
        if name is not None:
            constraints = context.constraints.get(name, {})
        else:
            constraints = {}
    else:
        name = None
        constraints = {}
        context = InferenceContext()

    for stmt in stmts:
        if isinstance(stmt, UninferableBase):
            yield stmt
            inferred = True
            continue
        context.lookupname = stmt._infer_name(frame, name)
        try:
            stmt_constraints: set[Constraint] = set()
            for constraint_stmt, potential_constraints in constraints.items():
                if not constraint_stmt.parent_of(stmt):
                    stmt_constraints.update(potential_constraints)
            for inf in stmt.infer(context=context):
                if all(constraint.satisfied_by(inf) for constraint in stmt_constraints):
                    yield inf
                    inferred = True
                else:
                    constraint_failed = True
        except NameInferenceError:
            continue
        except InferenceError:
            yield Uninferable
            inferred = True

    if not inferred and constraint_failed:
        yield Uninferable
    elif not inferred:
        raise InferenceError(
            "Inference failed for all members of {stmts!r}.",
            stmts=stmts,
            frame=frame,
            context=context,
        )


def _infer_method_result_truth(
    instance: Instance, method_name: str, context: InferenceContext
) -> bool | UninferableBase:
    # Get the method from the instance and try to infer
    # its return's truth value.
    meth = next(instance.igetattr(method_name, context=context), None)
    if meth and hasattr(meth, "infer_call_result"):
        if not meth.callable():
            return Uninferable
        try:
            context.callcontext = CallContext(args=[], callee=meth)
            for value in meth.infer_call_result(instance, context=context):
                if isinstance(value, UninferableBase):
                    return value
                try:
                    inferred = next(value.infer(context=context))
                except StopIteration as e:
                    raise InferenceError(context=context) from e
                return inferred.bool_value()
        except InferenceError:
            pass
    return Uninferable


class BaseInstance(Proxy):
    """An instance base class, which provides lookup methods for potential
    instances.
    """

    _proxied: nodes.ClassDef

    special_attributes: objectmodel.ObjectModel

    def display_type(self) -> str:
        return "Instance of"

    def getattr(
        self,
        name: str,
        context: InferenceContext | None = None,
        lookupclass: bool = True,
    ) -> list[InferenceResult]:
        try:
            values = self._proxied.instance_attr(name, context)
        except AttributeInferenceError as exc:
            if self.special_attributes and name in self.special_attributes:
                return [self.special_attributes.lookup(name)]

            if lookupclass:
                # Class attributes not available through the instance
                # unless they are explicitly defined.
                return self._proxied.getattr(name, context, class_context=False)

            raise AttributeInferenceError(
                target=self, attribute=name, context=context
            ) from exc
        # since we've no context information, return matching class members as
        # well
        if lookupclass:
            try:
                return values + self._proxied.getattr(
                    name, context, class_context=False
                )
            except AttributeInferenceError:
                pass
        return values

    def igetattr(
        self, name: str, context: InferenceContext | None = None
    ) -> Iterator[InferenceResult]:
        """Inferred getattr."""
        if not context:
            context = InferenceContext()
        try:
            context.lookupname = name
            # XXX frame should be self._proxied, or not ?
            get_attr = self.getattr(name, context, lookupclass=False)
            yield from _infer_stmts(
                self._wrap_attr(get_attr, context), context, frame=self
            )
        except AttributeInferenceError:
            try:
                # fallback to class.igetattr since it has some logic to handle
                # descriptors
                # But only if the _proxied is the Class.
                if self._proxied.__class__.__name__ != "ClassDef":
                    raise
                attrs = self._proxied.igetattr(name, context, class_context=False)
                yield from self._wrap_attr(attrs, context)
            except AttributeInferenceError as error:
                raise InferenceError(**vars(error)) from error

    def _wrap_attr(
        self, attrs: Iterable[InferenceResult], context: InferenceContext | None = None
    ) -> Iterator[InferenceResult]:
        """Wrap bound methods of attrs in a InstanceMethod proxies."""
        for attr in attrs:
            if isinstance(attr, UnboundMethod):
                if _is_property(attr):
                    yield from attr.infer_call_result(self, context)
                else:
                    yield BoundMethod(attr, self)
            elif isinstance(attr, nodes.Lambda):
                if attr.args.arguments and attr.args.arguments[0].name == "self":
                    yield BoundMethod(attr, self)
                    continue
                yield attr
            else:
                yield attr

    def infer_call_result(
        self,
        caller: SuccessfulInferenceResult | None,
        context: InferenceContext | None = None,
    ) -> Iterator[InferenceResult]:
        """Infer what a class instance is returning when called."""
        context = bind_context_to_node(context, self)
        inferred = False

        # If the call is an attribute on the instance, we infer the attribute itself
        if isinstance(caller, nodes.Call) and isinstance(caller.func, nodes.Attribute):
            for res in self.igetattr(caller.func.attrname, context):
                inferred = True
                yield res

        # Otherwise we infer the call to the __call__ dunder normally
        for node in self._proxied.igetattr("__call__", context):
            if isinstance(node, UninferableBase) or not node.callable():
                continue
            if isinstance(node, BaseInstance) and node._proxied is self._proxied:
                inferred = True
                yield node
                # Prevent recursion.
                continue
            for res in node.infer_call_result(caller, context):
                inferred = True
                yield res
        if not inferred:
            raise InferenceError(node=self, caller=caller, context=context)


class Instance(BaseInstance):
    """A special node representing a class instance."""

    special_attributes = objectmodel.InstanceModel()

    def __init__(self, proxied: nodes.ClassDef | None) -> None:
        super().__init__(proxied)

    @decorators.yes_if_nothing_inferred
    def infer_binary_op(
        self,
        opnode: nodes.AugAssign | nodes.BinOp,
        operator: str,
        other: InferenceResult,
        context: InferenceContext,
        method: SuccessfulInferenceResult,
    ) -> Generator[InferenceResult]:
        return method.infer_call_result(self, context)

    def __repr__(self) -> str:
        return "<Instance of {}.{} at 0x{}>".format(
            self._proxied.root().name, self._proxied.name, id(self)
        )

    def __str__(self) -> str:
        return f"Instance of {self._proxied.root().name}.{self._proxied.name}"

    def callable(self) -> bool:
        try:
            self._proxied.getattr("__call__", class_context=False)
            return True
        except AttributeInferenceError:
            return False

    def pytype(self) -> str:
        return self._proxied.qname()

    def display_type(self) -> str:
        return "Instance of"

    def bool_value(
        self, context: InferenceContext | None = None
    ) -> bool | UninferableBase:
        """Infer the truth value for an Instance.

        The truth value of an instance is determined by these conditions:

           * if it implements __bool__ on Python 3 or __nonzero__
             on Python 2, then its bool value will be determined by
             calling this special method and checking its result.
           * when this method is not defined, __len__() is called, if it
             is defined, and the object is considered true if its result is
             nonzero. If a class defines neither __len__() nor __bool__(),
             all its instances are considered true.
        """
        context = context or InferenceContext()
        context.boundnode = self

        try:
            result = _infer_method_result_truth(self, "__bool__", context)
        except (InferenceError, AttributeInferenceError):
            # Fallback to __len__.
            try:
                result = _infer_method_result_truth(self, "__len__", context)
            except (AttributeInferenceError, InferenceError):
                return True
        return result

    def getitem(
        self, index: nodes.Const, context: InferenceContext | None = None
    ) -> InferenceResult | None:
        new_context = bind_context_to_node(context, self)
        if not context:
            context = new_context
        method = next(self.igetattr("__getitem__", context=context), None)
        # Create a new CallContext for providing index as an argument.
        new_context.callcontext = CallContext(args=[index], callee=method)
        if not isinstance(method, BoundMethod):
            raise InferenceError(
                "Could not find __getitem__ for {node!r}.", node=self, context=context
            )
        if len(method.args.arguments) != 2:  # (self, index)
            raise AstroidTypeError(
                "__getitem__ for {node!r} does not have correct signature",
                node=self,
                context=context,
            )
        return next(method.infer_call_result(self, new_context), None)


class UnboundMethod(Proxy):
    """A special node representing a method not bound to an instance."""

    _proxied: nodes.FunctionDef | UnboundMethod

    special_attributes: (
        objectmodel.BoundMethodModel | objectmodel.UnboundMethodModel
    ) = objectmodel.UnboundMethodModel()

    def __repr__(self) -> str:
        assert self._proxied.parent, "Expected a parent node"
        frame = self._proxied.parent.frame()
        return "<{} {} of {} at 0x{}".format(
            self.__class__.__name__, self._proxied.name, frame.qname(), id(self)
        )

    def implicit_parameters(self) -> Literal[0, 1]:
        return 0

    def is_bound(self) -> bool:
        return False

    def getattr(self, name: str, context: InferenceContext | None = None):
        if name in self.special_attributes:
            return [self.special_attributes.lookup(name)]
        return self._proxied.getattr(name, context)

    def igetattr(
        self, name: str, context: InferenceContext | None = None
    ) -> Iterator[InferenceResult]:
        if name in self.special_attributes:
            return iter((self.special_attributes.lookup(name),))
        return self._proxied.igetattr(name, context)

    def infer_call_result(
        self,
        caller: SuccessfulInferenceResult | None,
        context: InferenceContext | None = None,
    ) -> Iterator[InferenceResult]:
        """
        The boundnode of the regular context with a function called
        on ``object.__new__`` will be of type ``object``,
        which is incorrect for the argument in general.
        If no context is given the ``object.__new__`` call argument will
        be correctly inferred except when inside a call that requires
        the additional context (such as a classmethod) of the boundnode
        to determine which class the method was called from
        """

        # If we're unbound method __new__ of a builtin, the result is an
        # instance of the class given as first argument.
        if self._proxied.name == "__new__":
            assert self._proxied.parent, "Expected a parent node"
            qname = self._proxied.parent.frame().qname()
            # Avoid checking builtins.type: _infer_type_new_call() does more validation
            if qname.startswith("builtins.") and qname != "builtins.type":
                return self._infer_builtin_new(caller, context or InferenceContext())
        return self._proxied.infer_call_result(caller, context)

    def _infer_builtin_new(
        self,
        caller: SuccessfulInferenceResult | None,
        context: InferenceContext,
    ) -> collections.abc.Generator[nodes.Const | Instance | UninferableBase]:
        if not isinstance(caller, nodes.Call):
            return
        if not caller.args:
            return
        # Attempt to create a constant
        if len(caller.args) > 1:
            value = None
            if isinstance(caller.args[1], nodes.Const):
                value = caller.args[1].value
            else:
                inferred_arg = next(caller.args[1].infer(), None)
                if isinstance(inferred_arg, nodes.Const):
                    value = inferred_arg.value
            if value is not None:
                const = nodes.const_factory(value)
                assert not isinstance(const, nodes.EmptyNode)
                yield const
                return

        node_context = context.extra_context.get(caller.args[0])
        for inferred in caller.args[0].infer(context=node_context):
            if isinstance(inferred, UninferableBase):
                yield inferred
            if isinstance(inferred, nodes.ClassDef):
                yield Instance(inferred)
            raise InferenceError

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True


class BoundMethod(UnboundMethod):
    """A special node representing a method bound to an instance."""

    special_attributes = objectmodel.BoundMethodModel()

    def __init__(
        self,
        proxy: nodes.FunctionDef | nodes.Lambda | UnboundMethod,
        bound: SuccessfulInferenceResult,
    ) -> None:
        super().__init__(proxy)
        self.bound = bound

    def implicit_parameters(self) -> Literal[0, 1]:
        if self.name == "__new__":
            # __new__ acts as a classmethod but the class argument is not implicit.
            return 0
        return 1

    def is_bound(self) -> Literal[True]:
        return True

    def _infer_type_new_call(
        self, caller: nodes.Call, context: InferenceContext
    ) -> nodes.ClassDef | None:  # noqa: C901
        """Try to infer what type.__new__(mcs, name, bases, attrs) returns.

        In order for such call to be valid, the metaclass needs to be
        a subtype of ``type``, the name needs to be a string, the bases
        needs to be a tuple of classes
        """
        # pylint: disable=import-outside-toplevel; circular import
        from astroid.nodes import Pass

        # Verify the metaclass
        try:
            mcs = next(caller.args[0].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if not isinstance(mcs, nodes.ClassDef):
            # Not a valid first argument.
            return None
        if not mcs.is_subtype_of("builtins.type"):
            # Not a valid metaclass.
            return None

        # Verify the name
        try:
            name = next(caller.args[1].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if not isinstance(name, nodes.Const):
            # Not a valid name, needs to be a const.
            return None
        if not isinstance(name.value, str):
            # Needs to be a string.
            return None

        # Verify the bases
        try:
            bases = next(caller.args[2].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if not isinstance(bases, nodes.Tuple):
            # Needs to be a tuple.
            return None
        try:
            inferred_bases = [next(elt.infer(context=context)) for elt in bases.elts]
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if any(not isinstance(base, nodes.ClassDef) for base in inferred_bases):
            # All the bases needs to be Classes
            return None

        # Verify the attributes.
        try:
            attrs = next(caller.args[3].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if not isinstance(attrs, nodes.Dict):
            # Needs to be a dictionary.
            return None
        cls_locals: dict[str, list[InferenceResult]] = collections.defaultdict(list)
        for key, value in attrs.items:
            try:
                key = next(key.infer(context=context))
            except StopIteration as e:
                raise InferenceError(context=context) from e
            try:
                value = next(value.infer(context=context))
            except StopIteration as e:
                raise InferenceError(context=context) from e
            # Ignore non string keys
            if isinstance(key, nodes.Const) and isinstance(key.value, str):
                cls_locals[key.value].append(value)

        # Build the class from now.
        cls = mcs.__class__(
            name=name.value,
            lineno=caller.lineno or 0,
            col_offset=caller.col_offset or 0,
            parent=caller,
            end_lineno=caller.end_lineno,
            end_col_offset=caller.end_col_offset,
        )
        empty = Pass(
            parent=cls,
            lineno=caller.lineno,
            col_offset=caller.col_offset,
            end_lineno=caller.end_lineno,
            end_col_offset=caller.end_col_offset,
        )
        cls.postinit(
            bases=bases.elts,
            body=[empty],
            decorators=None,
            newstyle=True,
            metaclass=mcs,
            keywords=[],
        )
        cls.locals = cls_locals
        return cls

    def infer_call_result(
        self,
        caller: SuccessfulInferenceResult | None,
        context: InferenceContext | None = None,
    ) -> Iterator[InferenceResult]:
        context = bind_context_to_node(context, self.bound)
        if (
            isinstance(self.bound, nodes.ClassDef)
            and self.bound.name == "type"
            and self.name == "__new__"
            and isinstance(caller, nodes.Call)
            and len(caller.args) == 4
        ):
            # Check if we have a ``type.__new__(mcs, name, bases, attrs)`` call.
            new_cls = self._infer_type_new_call(caller, context)
            if new_cls:
                return iter((new_cls,))

        return super().infer_call_result(caller, context)

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True


class Generator(BaseInstance):
    """A special node representing a generator.

    Proxied class is set once for all in raw_building.
    """

    # We defer initialization of special_attributes to the __init__ method since the constructor
    # of GeneratorModel requires the raw_building to be complete
    # TODO: This should probably be refactored.
    special_attributes: objectmodel.GeneratorModel

    def __init__(
        self,
        parent: nodes.FunctionDef,
        generator_initial_context: InferenceContext | None = None,
    ) -> None:
        super().__init__()
        self.parent = parent
        self._call_context = copy_context(generator_initial_context)

        # See comment above: this is a deferred initialization.
        Generator.special_attributes = objectmodel.GeneratorModel()

    def infer_yield_types(self) -> Iterator[InferenceResult]:
        yield from self.parent.infer_yield_result(self._call_context)

    def callable(self) -> Literal[False]:
        return False

    def pytype(self) -> str:
        return "builtins.generator"

    def display_type(self) -> str:
        return "Generator"

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True

    def __repr__(self) -> str:
        return f"<Generator({self._proxied.name}) l.{self.lineno} at 0x{id(self)}>"

    def __str__(self) -> str:
        return f"Generator({self._proxied.name})"


class AsyncGenerator(Generator):
    """Special node representing an async generator."""

    def pytype(self) -> Literal["builtins.async_generator"]:
        return "builtins.async_generator"

    def display_type(self) -> str:
        return "AsyncGenerator"

    def __repr__(self) -> str:
        return f"<AsyncGenerator({self._proxied.name}) l.{self.lineno} at 0x{id(self)}>"

    def __str__(self) -> str:
        return f"AsyncGenerator({self._proxied.name})"


class UnionType(BaseInstance):
    """Special node representing new style typing unions.

    Proxied class is set once for all in raw_building.
    """

    def __init__(
        self,
        left: UnionType | nodes.ClassDef | nodes.Const,
        right: UnionType | nodes.ClassDef | nodes.Const,
        parent: nodes.NodeNG | None = None,
    ) -> None:
        super().__init__()
        self.parent = parent
        self.left = left
        self.right = right

    def callable(self) -> Literal[False]:
        return False

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True

    def pytype(self) -> Literal["types.UnionType"]:
        return "types.UnionType"

    def display_type(self) -> str:
        return "UnionType"

    def __repr__(self) -> str:
        return f"<UnionType({self._proxied.name}) l.{self.lineno} at 0x{id(self)}>"

    def __str__(self) -> str:
        return f"UnionType({self._proxied.name})"
