# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""Variables checkers for Python code."""

from __future__ import annotations

import collections
import copy
import itertools
import math
import os
import re
from collections import defaultdict
from collections.abc import Generator, Iterable, Iterator
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Any, NamedTuple

import astroid
import astroid.exceptions
from astroid import bases, extract_node, nodes, util
from astroid.nodes import _base_nodes
from astroid.typing import InferenceResult

from pylint.checkers import BaseChecker, utils
from pylint.checkers.utils import (
    in_type_checking_block,
    is_module_ignored,
    is_postponed_evaluation_enabled,
    is_sys_guard,
    overridden_method,
)
from pylint.constants import TYPING_NEVER, TYPING_NORETURN
from pylint.interfaces import CONTROL_FLOW, HIGH, INFERENCE, INFERENCE_FAILURE
from pylint.typing import MessageDefinitionTuple

if TYPE_CHECKING:
    from pylint.lint import PyLinter

SPECIAL_OBJ = re.compile("^_{2}[a-z]+_{2}$")
FUTURE = "__future__"
# regexp for ignored argument name
IGNORED_ARGUMENT_NAMES = re.compile("_.*|^ignored_|^unused_")
# In Python 3.7 abc has a Python implementation which is preferred
# by astroid. Unfortunately this also messes up our explicit checks
# for `abc`
METACLASS_NAME_TRANSFORMS = {"_py_abc": "abc"}
BUILTIN_RANGE = "builtins.range"
TYPING_MODULE = "typing"
TYPING_NAMES = frozenset(
    {
        "Any",
        "Callable",
        "ClassVar",
        "Generic",
        "Optional",
        "Tuple",
        "Type",
        "TypeVar",
        "Union",
        "AbstractSet",
        "ByteString",
        "Container",
        "ContextManager",
        "Hashable",
        "ItemsView",
        "Iterable",
        "Iterator",
        "KeysView",
        "Mapping",
        "MappingView",
        "MutableMapping",
        "MutableSequence",
        "MutableSet",
        "Sequence",
        "Sized",
        "ValuesView",
        "Awaitable",
        "AsyncIterator",
        "AsyncIterable",
        "Coroutine",
        "Collection",
        "AsyncGenerator",
        "AsyncContextManager",
        "Reversible",
        "SupportsAbs",
        "SupportsBytes",
        "SupportsComplex",
        "SupportsFloat",
        "SupportsInt",
        "SupportsRound",
        "Counter",
        "Deque",
        "Dict",
        "DefaultDict",
        "List",
        "Set",
        "FrozenSet",
        "NamedTuple",
        "Generator",
        "AnyStr",
        "Text",
        "Pattern",
        "BinaryIO",
    }
)

DICT_TYPES = (
    astroid.objects.DictValues,
    astroid.objects.DictKeys,
    astroid.objects.DictItems,
    astroid.nodes.node_classes.Dict,
)

NODES_WITH_VALUE_ATTR = (
    nodes.Assign,
    nodes.AnnAssign,
    nodes.AugAssign,
    nodes.Expr,
    nodes.Return,
    nodes.Match,
    nodes.TypeAlias,
)


class VariableVisitConsumerAction(Enum):
    """Reported by _check_consumer() and its sub-methods to determine the
    subsequent action to take in _undefined_and_used_before_checker().

    Continue -> continue loop to next consumer
    Return -> return and thereby break the loop
    """

    CONTINUE = 0
    RETURN = 1


def _is_from_future_import(stmt: nodes.ImportFrom, name: str) -> bool | None:
    """Check if the name is a future import from another module."""
    try:
        module = stmt.do_import_module(stmt.modname)
    except astroid.AstroidBuildingError:
        return None

    for local_node in module.locals.get(name, []):
        if isinstance(local_node, nodes.ImportFrom) and local_node.modname == FUTURE:
            return True
    return None


def _get_unpacking_extra_info(node: nodes.Assign, inferred: InferenceResult) -> str:
    """Return extra information to add to the message for unpacking-non-sequence
    and unbalanced-tuple/dict-unpacking errors.
    """
    more = ""
    if isinstance(inferred, DICT_TYPES):
        if isinstance(node, nodes.Assign):
            more = node.value.as_string()
        elif isinstance(node, nodes.For):
            more = node.iter.as_string()
        return more

    inferred_module = inferred.root().name
    if node.root().name == inferred_module:
        if node.lineno == inferred.lineno:
            more = f"'{inferred.as_string()}'"
        elif inferred.lineno:
            more = f"defined at line {inferred.lineno}"
    elif inferred.lineno:
        more = f"defined at line {inferred.lineno} of {inferred_module}"
    return more


def _detect_global_scope(
    node: nodes.Name, frame: nodes.LocalsDictNodeNG, defframe: nodes.LocalsDictNodeNG
) -> bool:
    """Detect that the given frames share a global scope.

    Two frames share a global scope when neither
    of them are hidden under a function scope, as well
    as any parent scope of them, until the root scope.
    In this case, depending from something defined later on
    will only work if guarded by a nested function definition.

    Example:
        class A:
            # B has the same global scope as `C`, leading to a NameError.
            # Return True to indicate a shared scope.
            class B(C): ...
        class C: ...

    Whereas this does not lead to a NameError:
        class A:
            def guard():
                # Return False to indicate no scope sharing.
                class B(C): ...
        class C: ...
    """
    def_scope = scope = None
    if frame and frame.parent:
        scope = frame.parent.scope()
    if defframe and defframe.parent:
        def_scope = defframe.parent.scope()
    if (
        isinstance(frame, nodes.ClassDef)
        and scope is not def_scope
        and scope is utils.get_node_first_ancestor_of_type(node, nodes.FunctionDef)
    ):
        # If the current node's scope is a class nested under a function,
        # and the def_scope is something else, then they aren't shared.
        return False
    if isinstance(frame, nodes.FunctionDef):
        # If the parent of the current node is a
        # function, then it can be under its scope (defined in); or
        # the `->` part of annotations. The same goes
        # for annotations of function arguments, they'll have
        # their parent the Arguments node.
        if frame.parent_of(defframe):
            return node.lineno < defframe.lineno  # type: ignore[no-any-return]
        if not isinstance(node.parent, (nodes.FunctionDef, nodes.Arguments)):
            return False

    break_scopes = []
    for current_scope in (scope or frame, def_scope):
        # Look for parent scopes. If there is anything different
        # than a module or a class scope, then the frames don't
        # share a global scope.
        parent_scope = current_scope
        while parent_scope:
            if not isinstance(parent_scope, (nodes.ClassDef, nodes.Module)):
                break_scopes.append(parent_scope)
                break
            if parent_scope.parent:
                parent_scope = parent_scope.parent.scope()
            else:
                break
    if len(set(break_scopes)) > 1:
        # Store different scopes than expected.
        # If the stored scopes are, in fact, the very same, then it means
        # that the two frames (frame and defframe) share the same scope,
        # and we could apply our lineno analysis over them.
        # For instance, this works when they are inside a function, the node
        # that uses a definition and the definition itself.
        return False
    # At this point, we are certain that frame and defframe share a scope
    # and the definition of the first depends on the second.
    return frame.lineno < defframe.lineno  # type: ignore[no-any-return]


def _infer_name_module(node: nodes.Import, name: str) -> Generator[InferenceResult]:
    context = astroid.context.InferenceContext()
    context.lookupname = name
    return node.infer(context, asname=False)  # type: ignore[no-any-return]


def _fix_dot_imports(
    not_consumed: dict[str, list[nodes.NodeNG]]
) -> list[tuple[str, _base_nodes.ImportNode]]:
    """Try to fix imports with multiple dots, by returning a dictionary
    with the import names expanded.

    The function unflattens root imports,
    like 'xml' (when we have both 'xml.etree' and 'xml.sax'), to 'xml.etree'
    and 'xml.sax' respectively.
    """
    names: dict[str, _base_nodes.ImportNode] = {}
    for name, stmts in not_consumed.items():
        if any(
            isinstance(stmt, nodes.AssignName)
            and isinstance(stmt.assign_type(), nodes.AugAssign)
            for stmt in stmts
        ):
            continue
        for stmt in stmts:
            if not isinstance(stmt, (nodes.ImportFrom, nodes.Import)):
                continue
            for imports in stmt.names:
                second_name = None
                import_module_name = imports[0]
                if import_module_name == "*":
                    # In case of wildcard imports,
                    # pick the name from inside the imported module.
                    second_name = name
                else:
                    name_matches_dotted_import = False
                    if (
                        import_module_name.startswith(name)
                        and import_module_name.find(".") > -1
                    ):
                        name_matches_dotted_import = True

                    if name_matches_dotted_import or name in imports:
                        # Most likely something like 'xml.etree',
                        # which will appear in the .locals as 'xml'.
                        # Only pick the name if it wasn't consumed.
                        second_name = import_module_name
                if second_name and second_name not in names:
                    names[second_name] = stmt
    return sorted(names.items(), key=lambda a: a[1].fromlineno)


def _find_frame_imports(name: str, frame: nodes.LocalsDictNodeNG) -> bool:
    """Detect imports in the frame, with the required *name*.

    Such imports can be considered assignments if they are not globals.
    Returns True if an import for the given name was found.
    """
    if name in _flattened_scope_names(frame.nodes_of_class(nodes.Global)):
        return False

    imports = frame.nodes_of_class((nodes.Import, nodes.ImportFrom))
    for import_node in imports:
        for import_name, import_alias in import_node.names:
            # If the import uses an alias, check only that.
            # Otherwise, check only the import name.
            if import_alias:
                if import_alias == name:
                    return True
            elif import_name and import_name == name:
                return True
    return False


def _import_name_is_global(
    stmt: nodes.Global | _base_nodes.ImportNode, global_names: set[str]
) -> bool:
    for import_name, import_alias in stmt.names:
        # If the import uses an alias, check only that.
        # Otherwise, check only the import name.
        if import_alias:
            if import_alias in global_names:
                return True
        elif import_name in global_names:
            return True
    return False


def _flattened_scope_names(
    iterator: Iterator[nodes.Global | nodes.Nonlocal],
) -> set[str]:
    values = (set(stmt.names) for stmt in iterator)
    return set(itertools.chain.from_iterable(values))


def _assigned_locally(name_node: nodes.Name) -> bool:
    """Checks if name_node has corresponding assign statement in same scope."""
    name_node_scope = name_node.scope()
    assign_stmts = name_node_scope.nodes_of_class(nodes.AssignName)
    return any(a.name == name_node.name for a in assign_stmts) or _find_frame_imports(
        name_node.name, name_node_scope
    )


def _has_locals_call_after_node(stmt: nodes.NodeNG, scope: nodes.FunctionDef) -> bool:
    skip_nodes = (
        nodes.FunctionDef,
        nodes.ClassDef,
        nodes.Import,
        nodes.ImportFrom,
    )
    for call in scope.nodes_of_class(nodes.Call, skip_klass=skip_nodes):
        inferred = utils.safe_infer(call.func)
        if (
            utils.is_builtin_object(inferred)
            and getattr(inferred, "name", None) == "locals"
        ):
            if stmt.lineno < call.lineno:
                return True
    return False


MSGS: dict[str, MessageDefinitionTuple] = {
    "E0601": (
        "Using variable %r before assignment",
        "used-before-assignment",
        "Emitted when a local variable is accessed before its assignment took place. "
        "Assignments in try blocks are assumed not to have occurred when evaluating "
        "associated except/finally blocks. Assignments in except blocks are assumed "
        "not to have occurred when evaluating statements outside the block, except "
        "when the associated try block contains a return statement.",
    ),
    "E0602": (
        "Undefined variable %r",
        "undefined-variable",
        "Used when an undefined variable is accessed.",
    ),
    "E0603": (
        "Undefined variable name %r in __all__",
        "undefined-all-variable",
        "Used when an undefined variable name is referenced in __all__.",
    ),
    "E0604": (
        "Invalid object %r in __all__, must contain only strings",
        "invalid-all-object",
        "Used when an invalid (non-string) object occurs in __all__.",
    ),
    "E0605": (
        "Invalid format for __all__, must be tuple or list",
        "invalid-all-format",
        "Used when __all__ has an invalid format.",
    ),
    "E0606": (
        "Possibly using variable %r before assignment",
        "possibly-used-before-assignment",
        "Emitted when a local variable is accessed before its assignment took place "
        "in both branches of an if/else switch.",
    ),
    "E0611": (
        "No name %r in module %r",
        "no-name-in-module",
        "Used when a name cannot be found in a module.",
    ),
    "W0601": (
        "Global variable %r undefined at the module level",
        "global-variable-undefined",
        'Used when a variable is defined through the "global" statement '
        "but the variable is not defined in the module scope.",
    ),
    "W0602": (
        "Using global for %r but no assignment is done",
        "global-variable-not-assigned",
        "When a variable defined in the global scope is modified in an inner scope, "
        "the 'global' keyword is required in the inner scope only if there is an "
        "assignment operation done in the inner scope.",
    ),
    "W0603": (
        "Using the global statement",  # W0121
        "global-statement",
        'Used when you use the "global" statement to update a global '
        "variable. Pylint discourages its usage. That doesn't mean you cannot "
        "use it!",
    ),
    "W0604": (
        "Using the global statement at the module level",  # W0103
        "global-at-module-level",
        'Used when you use the "global" statement at the module level '
        "since it has no effect.",
    ),
    "W0611": (
        "Unused %s",
        "unused-import",
        "Used when an imported module or variable is not used.",
    ),
    "W0612": (
        "Unused variable %r",
        "unused-variable",
        "Used when a variable is defined but not used.",
    ),
    "W0613": (
        "Unused argument %r",
        "unused-argument",
        "Used when a function or method argument is not used.",
    ),
    "W0614": (
        "Unused import(s) %s from wildcard import of %s",
        "unused-wildcard-import",
        "Used when an imported module or variable is not used from a "
        "`'from X import *'` style import.",
    ),
    "W0621": (
        "Redefining name %r from outer scope (line %s)",
        "redefined-outer-name",
        "Used when a variable's name hides a name defined in an outer scope or except handler.",
    ),
    "W0622": (
        "Redefining built-in %r",
        "redefined-builtin",
        "Used when a variable or function override a built-in.",
    ),
    "W0631": (
        "Using possibly undefined loop variable %r",
        "undefined-loop-variable",
        "Used when a loop variable (i.e. defined by a for loop or "
        "a list comprehension or a generator expression) is used outside "
        "the loop.",
    ),
    "W0632": (
        "Possible unbalanced tuple unpacking with sequence %s: left side has %d "
        "label%s, right side has %d value%s",
        "unbalanced-tuple-unpacking",
        "Used when there is an unbalanced tuple unpacking in assignment",
        {"old_names": [("E0632", "old-unbalanced-tuple-unpacking")]},
    ),
    "E0633": (
        "Attempting to unpack a non-sequence%s",
        "unpacking-non-sequence",
        "Used when something which is not a sequence is used in an unpack assignment",
        {"old_names": [("W0633", "old-unpacking-non-sequence")]},
    ),
    "W0640": (
        "Cell variable %s defined in loop",
        "cell-var-from-loop",
        "A variable used in a closure is defined in a loop. "
        "This will result in all closures using the same value for "
        "the closed-over variable.",
    ),
    "W0641": (
        "Possibly unused variable %r",
        "possibly-unused-variable",
        "Used when a variable is defined but might not be used. "
        "The possibility comes from the fact that locals() might be used, "
        "which could consume or not the said variable",
    ),
    "W0642": (
        "Invalid assignment to %s in method",
        "self-cls-assignment",
        "Invalid assignment to self or cls in instance or class method "
        "respectively.",
    ),
    "E0643": (
        "Invalid index for iterable length",
        "potential-index-error",
        "Emitted when an index used on an iterable goes beyond the length of that "
        "iterable.",
    ),
    "W0644": (
        "Possible unbalanced dict unpacking with %s: "
        "left side has %d label%s, right side has %d value%s",
        "unbalanced-dict-unpacking",
        "Used when there is an unbalanced dict unpacking in assignment or for loop",
    ),
}


class ScopeConsumer(NamedTuple):
    """Store nodes and their consumption states."""

    to_consume: dict[str, list[nodes.NodeNG]]
    consumed: dict[str, list[nodes.NodeNG]]
    consumed_uncertain: defaultdict[str, list[nodes.NodeNG]]
    scope_type: str


class NamesConsumer:
    """A simple class to handle consumed, to consume and scope type info of node locals."""

    def __init__(self, node: nodes.NodeNG, scope_type: str) -> None:
        self._atomic = ScopeConsumer(
            copy.copy(node.locals), {}, collections.defaultdict(list), scope_type
        )
        self.node = node
        self.names_under_always_false_test: set[str] = set()
        self.names_defined_under_one_branch_only: set[str] = set()

    def __repr__(self) -> str:
        _to_consumes = [f"{k}->{v}" for k, v in self._atomic.to_consume.items()]
        _consumed = [f"{k}->{v}" for k, v in self._atomic.consumed.items()]
        _consumed_uncertain = [
            f"{k}->{v}" for k, v in self._atomic.consumed_uncertain.items()
        ]
        to_consumes = ", ".join(_to_consumes)
        consumed = ", ".join(_consumed)
        consumed_uncertain = ", ".join(_consumed_uncertain)
        return f"""
to_consume : {to_consumes}
consumed : {consumed}
consumed_uncertain: {consumed_uncertain}
scope_type : {self._atomic.scope_type}
"""

    def __iter__(self) -> Iterator[Any]:
        return iter(self._atomic)

    @property
    def to_consume(self) -> dict[str, list[nodes.NodeNG]]:
        return self._atomic.to_consume

    @property
    def consumed(self) -> dict[str, list[nodes.NodeNG]]:
        return self._atomic.consumed

    @property
    def consumed_uncertain(self) -> defaultdict[str, list[nodes.NodeNG]]:
        """Retrieves nodes filtered out by get_next_to_consume() that may not
        have executed.

        These include nodes such as statements in except blocks, or statements
        in try blocks (when evaluating their corresponding except and finally
        blocks). Checkers that want to treat the statements as executed
        (e.g. for unused-variable) may need to add them back.
        """
        return self._atomic.consumed_uncertain

    @property
    def scope_type(self) -> str:
        return self._atomic.scope_type

    def mark_as_consumed(self, name: str, consumed_nodes: list[nodes.NodeNG]) -> None:
        """Mark the given nodes as consumed for the name.

        If all of the nodes for the name were consumed, delete the name from
        the to_consume dictionary
        """
        unconsumed = [n for n in self.to_consume[name] if n not in set(consumed_nodes)]
        self.consumed[name] = consumed_nodes

        if unconsumed:
            self.to_consume[name] = unconsumed
        else:
            del self.to_consume[name]

    def get_next_to_consume(self, node: nodes.Name) -> list[nodes.NodeNG] | None:
        """Return a list of the nodes that define `node` from this scope.

        If it is uncertain whether a node will be consumed, such as for statements in
        except blocks, add it to self.consumed_uncertain instead of returning it.
        Return None to indicate a special case that needs to be handled by the caller.
        """
        name = node.name
        parent_node = node.parent
        found_nodes = self.to_consume.get(name)
        node_statement = node.statement()
        if (
            found_nodes
            and isinstance(parent_node, nodes.Assign)
            and parent_node == found_nodes[0].parent
        ):
            lhs = found_nodes[0].parent.targets[0]
            if (
                isinstance(lhs, nodes.AssignName) and lhs.name == name
            ):  # this name is defined in this very statement
                found_nodes = None

        if (
            found_nodes
            and isinstance(parent_node, nodes.For)
            and parent_node.iter == node
            and parent_node.target in found_nodes
        ):
            found_nodes = None

        # Before filtering, check that this node's name is not a nonlocal
        if any(
            isinstance(child, nodes.Nonlocal) and node.name in child.names
            for child in node.frame().get_children()
        ):
            return found_nodes

        # And no comprehension is under the node's frame
        if VariablesChecker._comprehension_between_frame_and_node(node):
            return found_nodes

        # Filter out assignments in ExceptHandlers that node is not contained in
        if found_nodes:
            found_nodes = [
                n
                for n in found_nodes
                if not isinstance(n.statement(), nodes.ExceptHandler)
                or n.statement().parent_of(node)
            ]

        # Filter out assignments guarded by always false conditions
        if found_nodes:
            uncertain_nodes = self._uncertain_nodes_if_tests(found_nodes, node)
            self.consumed_uncertain[node.name] += uncertain_nodes
            uncertain_nodes_set = set(uncertain_nodes)
            found_nodes = [n for n in found_nodes if n not in uncertain_nodes_set]

        # Filter out assignments in an Except clause that the node is not
        # contained in, assuming they may fail
        if found_nodes:
            uncertain_nodes = self._uncertain_nodes_in_except_blocks(
                found_nodes, node, node_statement
            )
            self.consumed_uncertain[node.name] += uncertain_nodes
            uncertain_nodes_set = set(uncertain_nodes)
            found_nodes = [n for n in found_nodes if n not in uncertain_nodes_set]

        # If this node is in a Finally block of a Try/Finally,
        # filter out assignments in the try portion, assuming they may fail
        if found_nodes:
            uncertain_nodes = (
                self._uncertain_nodes_in_try_blocks_when_evaluating_finally_blocks(
                    found_nodes, node_statement, name
                )
            )
            self.consumed_uncertain[node.name] += uncertain_nodes
            uncertain_nodes_set = set(uncertain_nodes)
            found_nodes = [n for n in found_nodes if n not in uncertain_nodes_set]

        # If this node is in an ExceptHandler,
        # filter out assignments in the try portion, assuming they may fail
        if found_nodes:
            uncertain_nodes = (
                self._uncertain_nodes_in_try_blocks_when_evaluating_except_blocks(
                    found_nodes, node_statement
                )
            )
            self.consumed_uncertain[node.name] += uncertain_nodes
            uncertain_nodes_set = set(uncertain_nodes)
            found_nodes = [n for n in found_nodes if n not in uncertain_nodes_set]

        return found_nodes

    def _inferred_to_define_name_raise_or_return(
        self, name: str, node: nodes.NodeNG
    ) -> bool:
        """Return True if there is a path under this `if_node`
        that is inferred to define `name`, raise, or return.
        """
        # Handle try and with
        if isinstance(node, nodes.Try):
            # Allow either a path through try/else/finally OR a path through ALL except handlers
            try_except_node = node
            if node.finalbody:
                try_except_node = next(
                    (child for child in node.nodes_of_class(nodes.Try)),
                    None,
                )
            handlers = try_except_node.handlers if try_except_node else []
            return NamesConsumer._defines_name_raises_or_returns_recursive(
                name, node
            ) or all(
                NamesConsumer._defines_name_raises_or_returns_recursive(name, handler)
                for handler in handlers
            )

        if isinstance(node, (nodes.With, nodes.For, nodes.While)):
            return NamesConsumer._defines_name_raises_or_returns_recursive(name, node)

        if not isinstance(node, nodes.If):
            return False

        # Be permissive if there is a break or a continue
        if any(node.nodes_of_class(nodes.Break, nodes.Continue)):
            return True

        # Is there an assignment in this node itself, e.g. in named expression?
        if NamesConsumer._defines_name_raises_or_returns(name, node):
            return True

        test = node.test.value if isinstance(node.test, nodes.NamedExpr) else node.test
        all_inferred = utils.infer_all(test)
        only_search_if = False
        only_search_else = True

        for inferred in all_inferred:
            if not isinstance(inferred, nodes.Const):
                only_search_else = False
                continue
            val = inferred.value
            only_search_if = only_search_if or (val != NotImplemented and val)
            only_search_else = only_search_else and not val

        # Only search else branch when test condition is inferred to be false
        if all_inferred and only_search_else:
            self.names_under_always_false_test.add(name)
            return self._branch_handles_name(name, node.orelse)
        # Search both if and else branches
        if_branch_handles = self._branch_handles_name(name, node.body)
        else_branch_handles = self._branch_handles_name(name, node.orelse)
        if if_branch_handles ^ else_branch_handles:
            self.names_defined_under_one_branch_only.add(name)
        elif name in self.names_defined_under_one_branch_only:
            self.names_defined_under_one_branch_only.remove(name)
        return if_branch_handles and else_branch_handles

    def _branch_handles_name(self, name: str, body: Iterable[nodes.NodeNG]) -> bool:
        return any(
            NamesConsumer._defines_name_raises_or_returns(name, if_body_stmt)
            or isinstance(
                if_body_stmt,
                (
                    nodes.If,
                    nodes.Try,
                    nodes.With,
                    nodes.For,
                    nodes.While,
                ),
            )
            and self._inferred_to_define_name_raise_or_return(name, if_body_stmt)
            for if_body_stmt in body
        )

    def _uncertain_nodes_if_tests(
        self, found_nodes: list[nodes.NodeNG], node: nodes.NodeNG
    ) -> list[nodes.NodeNG]:
        """Identify nodes of uncertain execution because they are defined under if
        tests.

        Don't identify a node if there is a path that is inferred to
        define the name, raise, or return (e.g. any executed if/elif/else branch).
        """
        uncertain_nodes = []
        for other_node in found_nodes:
            if isinstance(other_node, nodes.AssignName):
                name = other_node.name
            elif isinstance(other_node, (nodes.Import, nodes.ImportFrom)):
                name = node.name
            else:
                continue

            all_if = [
                n
                for n in other_node.node_ancestors()
                if isinstance(n, nodes.If) and not n.parent_of(node)
            ]
            if not all_if:
                continue

            closest_if = all_if[0]
            if (
                isinstance(node, nodes.AssignName)
                and node.frame() is not closest_if.frame()
            ):
                continue
            if closest_if.parent_of(node):
                continue

            outer_if = all_if[-1]
            if NamesConsumer._node_guarded_by_same_test(node, outer_if):
                continue

            # Name defined in the if/else control flow
            if self._inferred_to_define_name_raise_or_return(name, outer_if):
                continue

            uncertain_nodes.append(other_node)

        return uncertain_nodes

    @staticmethod
    def _node_guarded_by_same_test(node: nodes.NodeNG, other_if: nodes.If) -> bool:
        """Identify if `node` is guarded by an equivalent test as `other_if`.

        Two tests are equivalent if their string representations are identical
        or if their inferred values consist only of constants and those constants
        are identical, and the if test guarding `node` is not a Name.
        """
        other_if_test_as_string = other_if.test.as_string()
        other_if_test_all_inferred = utils.infer_all(other_if.test)
        for ancestor in node.node_ancestors():
            if not isinstance(ancestor, nodes.If):
                continue
            if ancestor.test.as_string() == other_if_test_as_string:
                return True
            if isinstance(ancestor.test, nodes.Name):
                continue
            all_inferred = utils.infer_all(ancestor.test)
            if len(all_inferred) == len(other_if_test_all_inferred):
                if any(
                    not isinstance(test, nodes.Const)
                    for test in (*all_inferred, *other_if_test_all_inferred)
                ):
                    continue
                if {test.value for test in all_inferred} != {
                    test.value for test in other_if_test_all_inferred
                }:
                    continue
                return True

        return False

    @staticmethod
    def _uncertain_nodes_in_except_blocks(
        found_nodes: list[nodes.NodeNG],
        node: nodes.NodeNG,
        node_statement: _base_nodes.Statement,
    ) -> list[nodes.NodeNG]:
        """Return any nodes in ``found_nodes`` that should be treated as uncertain
        because they are in an except block.
        """
        uncertain_nodes = []
        for other_node in found_nodes:
            other_node_statement = other_node.statement()
            # Only testing for statements in the except block of Try
            closest_except_handler = utils.get_node_first_ancestor_of_type(
                other_node_statement, nodes.ExceptHandler
            )
            if not closest_except_handler:
                continue
            # If the other node is in the same scope as this node, assume it executes
            if closest_except_handler.parent_of(node):
                continue
            closest_try_except: nodes.Try = closest_except_handler.parent
            # If the try or else blocks return, assume the except blocks execute.
            try_block_returns = any(
                isinstance(try_statement, nodes.Return)
                for try_statement in closest_try_except.body
            )
            else_block_returns = any(
                isinstance(else_statement, nodes.Return)
                for else_statement in closest_try_except.orelse
            )
            else_block_exits = any(
                isinstance(else_statement, nodes.Expr)
                and isinstance(else_statement.value, nodes.Call)
                and utils.is_terminating_func(else_statement.value)
                for else_statement in closest_try_except.orelse
            )
            else_block_continues = any(
                isinstance(else_statement, nodes.Continue)
                for else_statement in closest_try_except.orelse
            )
            if (
                else_block_continues
                and isinstance(node_statement.parent, (nodes.For, nodes.While))
                and closest_try_except.parent.parent_of(node_statement)
            ):
                continue

            if try_block_returns or else_block_returns or else_block_exits:
                # Exception: if this node is in the final block of the other_node_statement,
                # it will execute before returning. Assume the except statements are uncertain.
                if (
                    isinstance(node_statement.parent, nodes.Try)
                    and node_statement in node_statement.parent.finalbody
                    and closest_try_except.parent.parent_of(node_statement)
                ):
                    uncertain_nodes.append(other_node)
                # Or the node_statement is in the else block of the relevant Try
                elif (
                    isinstance(node_statement.parent, nodes.Try)
                    and node_statement in node_statement.parent.orelse
                    and closest_try_except.parent.parent_of(node_statement)
                ):
                    uncertain_nodes.append(other_node)
                # Assume the except blocks execute, so long as each handler
                # defines the name, raises, or returns.
                elif all(
                    NamesConsumer._defines_name_raises_or_returns_recursive(
                        node.name, handler
                    )
                    for handler in closest_try_except.handlers
                ):
                    continue

            if NamesConsumer._check_loop_finishes_via_except(node, closest_try_except):
                continue

            # Passed all tests for uncertain execution
            uncertain_nodes.append(other_node)
        return uncertain_nodes

    @staticmethod
    def _defines_name_raises_or_returns(name: str, node: nodes.NodeNG) -> bool:
        if isinstance(node, (nodes.Raise, nodes.Assert, nodes.Return, nodes.Continue)):
            return True
        if isinstance(node, nodes.Expr) and isinstance(node.value, nodes.Call):
            if utils.is_terminating_func(node.value):
                return True
            if (
                isinstance(node.value.func, nodes.Name)
                and node.value.func.name == "assert_never"
            ):
                return True
        if (
            isinstance(node, nodes.AnnAssign)
            and node.value
            and isinstance(node.target, nodes.AssignName)
            and node.target.name == name
        ):
            return True
        if isinstance(node, nodes.Assign):
            for target in node.targets:
                for elt in utils.get_all_elements(target):
                    if isinstance(elt, nodes.Starred):
                        elt = elt.value
                    if isinstance(elt, nodes.AssignName) and elt.name == name:
                        return True
        if isinstance(node, nodes.If):
            if any(
                child_named_expr.target.name == name
                for child_named_expr in node.nodes_of_class(nodes.NamedExpr)
            ):
                return True
        if isinstance(node, (nodes.Import, nodes.ImportFrom)) and any(
            (node_name[1] and node_name[1] == name)
            or (node_name[0] == name)
            or (node_name[0].startswith(name + "."))
            for node_name in node.names
        ):
            return True
        if isinstance(node, nodes.With) and any(
            isinstance(item[1], nodes.AssignName) and item[1].name == name
            for item in node.items
        ):
            return True
        if isinstance(node, (nodes.ClassDef, nodes.FunctionDef)) and node.name == name:
            return True
        if (
            isinstance(node, nodes.ExceptHandler)
            and node.name
            and node.name.name == name
        ):
            return True
        return False

    @staticmethod
    def _defines_name_raises_or_returns_recursive(
        name: str, node: nodes.NodeNG
    ) -> bool:
        """Return True if some child of `node` defines the name `name`,
        raises, or returns.
        """
        for stmt in node.get_children():
            if NamesConsumer._defines_name_raises_or_returns(name, stmt):
                return True
            if isinstance(stmt, (nodes.If, nodes.With)):
                if any(
                    NamesConsumer._defines_name_raises_or_returns(name, nested_stmt)
                    for nested_stmt in stmt.get_children()
                ):
                    return True
            if (
                isinstance(stmt, nodes.Try)
                and not stmt.finalbody
                and NamesConsumer._defines_name_raises_or_returns_recursive(name, stmt)
            ):
                return True
        return False

    @staticmethod
    def _check_loop_finishes_via_except(
        node: nodes.NodeNG, other_node_try_except: nodes.Try
    ) -> bool:
        """Check for a specific control flow scenario.

        Described in https://github.com/pylint-dev/pylint/issues/5683.

        A scenario where the only non-break exit from a loop consists of the very
        except handler we are examining, such that code in the `else` branch of
        the loop can depend on it being assigned.

        Example:
        for _ in range(3):
            try:
                do_something()
            except:
                name = 1  <-- only non-break exit from loop
            else:
                break
        else:
            print(name)
        """
        if not other_node_try_except.orelse:
            return False
        closest_loop: None | (nodes.For | nodes.While) = (
            utils.get_node_first_ancestor_of_type(node, (nodes.For, nodes.While))
        )
        if closest_loop is None:
            return False
        if not any(
            else_statement is node or else_statement.parent_of(node)
            for else_statement in closest_loop.orelse
        ):
            # `node` not guarded by `else`
            return False
        for inner_else_statement in other_node_try_except.orelse:
            if isinstance(inner_else_statement, nodes.Break):
                break_stmt = inner_else_statement
                break
        else:
            # No break statement
            return False

        def _try_in_loop_body(
            other_node_try_except: nodes.Try, loop: nodes.For | nodes.While
        ) -> bool:
            """Return True if `other_node_try_except` is a descendant of `loop`."""
            return any(
                loop_body_statement is other_node_try_except
                or loop_body_statement.parent_of(other_node_try_except)
                for loop_body_statement in loop.body
            )

        if not _try_in_loop_body(other_node_try_except, closest_loop):
            for ancestor in closest_loop.node_ancestors():
                if isinstance(ancestor, (nodes.For, nodes.While)):
                    if _try_in_loop_body(other_node_try_except, ancestor):
                        break
            else:
                # `other_node_try_except` didn't have a shared ancestor loop
                return False

        for loop_stmt in closest_loop.body:
            if NamesConsumer._recursive_search_for_continue_before_break(
                loop_stmt, break_stmt
            ):
                break
        else:
            # No continue found, so we arrived at our special case!
            return True
        return False

    @staticmethod
    def _recursive_search_for_continue_before_break(
        stmt: _base_nodes.Statement, break_stmt: nodes.Break
    ) -> bool:
        """Return True if any Continue node can be found in descendants of `stmt`
        before encountering `break_stmt`, ignoring any nested loops.
        """
        if stmt is break_stmt:
            return False
        if isinstance(stmt, nodes.Continue):
            return True
        for child in stmt.get_children():
            if isinstance(stmt, (nodes.For, nodes.While)):
                continue
            if NamesConsumer._recursive_search_for_continue_before_break(
                child, break_stmt
            ):
                return True
        return False

    @staticmethod
    def _uncertain_nodes_in_try_blocks_when_evaluating_except_blocks(
        found_nodes: list[nodes.NodeNG], node_statement: _base_nodes.Statement
    ) -> list[nodes.NodeNG]:
        """Return any nodes in ``found_nodes`` that should be treated as uncertain.

        Nodes are uncertain when they are in a try block and the ``node_statement``
        being evaluated is in one of its except handlers.
        """
        uncertain_nodes: list[nodes.NodeNG] = []
        closest_except_handler = utils.get_node_first_ancestor_of_type(
            node_statement, nodes.ExceptHandler
        )
        if closest_except_handler is None:
            return uncertain_nodes
        for other_node in found_nodes:
            other_node_statement = other_node.statement()
            # If the other statement is the except handler guarding `node`, it executes
            if other_node_statement is closest_except_handler:
                continue
            # Ensure other_node is in a try block
            (
                other_node_try_ancestor,
                other_node_try_ancestor_visited_child,
            ) = utils.get_node_first_ancestor_of_type_and_its_child(
                other_node_statement, nodes.Try
            )
            if other_node_try_ancestor is None:
                continue
            if (
                other_node_try_ancestor_visited_child
                not in other_node_try_ancestor.body
            ):
                continue
            # Make sure nesting is correct -- there should be at least one
            # except handler that is a sibling attached to the try ancestor,
            # or is an ancestor of the try ancestor.
            if not any(
                closest_except_handler in other_node_try_ancestor.handlers
                or other_node_try_ancestor_except_handler
                in closest_except_handler.node_ancestors()
                for other_node_try_ancestor_except_handler in other_node_try_ancestor.handlers
            ):
                continue
            # Passed all tests for uncertain execution
            uncertain_nodes.append(other_node)
        return uncertain_nodes

    @staticmethod
    def _uncertain_nodes_in_try_blocks_when_evaluating_finally_blocks(
        found_nodes: list[nodes.NodeNG],
        node_statement: _base_nodes.Statement,
        name: str,
    ) -> list[nodes.NodeNG]:
        uncertain_nodes: list[nodes.NodeNG] = []
        (
            closest_try_finally_ancestor,
            child_of_closest_try_finally_ancestor,
        ) = utils.get_node_first_ancestor_of_type_and_its_child(
            node_statement, nodes.Try
        )
        if closest_try_finally_ancestor is None:
            return uncertain_nodes
        if (
            child_of_closest_try_finally_ancestor
            not in closest_try_finally_ancestor.finalbody
        ):
            return uncertain_nodes
        for other_node in found_nodes:
            other_node_statement = other_node.statement()
            (
                other_node_try_finally_ancestor,
                child_of_other_node_try_finally_ancestor,
            ) = utils.get_node_first_ancestor_of_type_and_its_child(
                other_node_statement, nodes.Try
            )
            if other_node_try_finally_ancestor is None:
                continue
            # other_node needs to descend from the try of a try/finally.
            if (
                child_of_other_node_try_finally_ancestor
                not in other_node_try_finally_ancestor.body
            ):
                continue
            # If the two try/finally ancestors are not the same, then
            # node_statement's closest try/finally ancestor needs to be in
            # the final body of other_node's try/finally ancestor, or
            # descend from one of the statements in that final body.
            if (
                other_node_try_finally_ancestor is not closest_try_finally_ancestor
                and not any(
                    other_node_final_statement is closest_try_finally_ancestor
                    or other_node_final_statement.parent_of(
                        closest_try_finally_ancestor
                    )
                    for other_node_final_statement in other_node_try_finally_ancestor.finalbody
                )
            ):
                continue
            # Is the name defined in all exception clauses?
            if other_node_try_finally_ancestor.handlers and all(
                NamesConsumer._defines_name_raises_or_returns_recursive(name, handler)
                for handler in other_node_try_finally_ancestor.handlers
            ):
                continue
            # Passed all tests for uncertain execution
            uncertain_nodes.append(other_node)
        return uncertain_nodes


# pylint: disable=too-many-public-methods
class VariablesChecker(BaseChecker):
    """BaseChecker for variables.

    Checks for
    * unused variables / imports
    * undefined variables
    * redefinition of variable from builtins or from an outer scope or except handler
    * use of variable before assignment
    * __all__ consistency
    * self/cls assignment
    """

    name = "variables"
    msgs = MSGS
    options = (
        (
            "init-import",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Tells whether we should check for unused import in "
                "__init__ files.",
            },
        ),
        (
            "dummy-variables-rgx",
            {
                "default": "_+$|(_[a-zA-Z0-9_]*[a-zA-Z0-9]+?$)|dummy|^ignored_|^unused_",
                "type": "regexp",
                "metavar": "<regexp>",
                "help": "A regular expression matching the name of dummy "
                "variables (i.e. expected to not be used).",
            },
        ),
        (
            "additional-builtins",
            {
                "default": (),
                "type": "csv",
                "metavar": "<comma separated list>",
                "help": "List of additional names supposed to be defined in "
                "builtins. Remember that you should avoid defining new builtins "
                "when possible.",
            },
        ),
        (
            "callbacks",
            {
                "default": ("cb_", "_cb"),
                "type": "csv",
                "metavar": "<callbacks>",
                "help": "List of strings which can identify a callback "
                "function by name. A callback name must start or "
                "end with one of those strings.",
            },
        ),
        (
            "redefining-builtins-modules",
            {
                "default": (
                    "six.moves",
                    "past.builtins",
                    "future.builtins",
                    "builtins",
                    "io",
                ),
                "type": "csv",
                "metavar": "<comma separated list>",
                "help": "List of qualified module names which can have objects "
                "that can redefine builtins.",
            },
        ),
        (
            "ignored-argument-names",
            {
                "default": IGNORED_ARGUMENT_NAMES,
                "type": "regexp",
                "metavar": "<regexp>",
                "help": "Argument names that match this expression will be ignored.",
            },
        ),
        (
            "allow-global-unused-variables",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Tells whether unused global variables should be treated as a violation.",
            },
        ),
        (
            "allowed-redefined-builtins",
            {
                "default": (),
                "type": "csv",
                "metavar": "<comma separated list>",
                "help": "List of names allowed to shadow builtins",
            },
        ),
    )

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._to_consume: list[NamesConsumer] = []
        self._type_annotation_names: list[str] = []
        self._except_handler_names_queue: list[
            tuple[nodes.ExceptHandler, nodes.AssignName]
        ] = []
        """This is a queue, last in first out."""
        self._evaluated_type_checking_scopes: dict[
            str, list[nodes.LocalsDictNodeNG]
        ] = {}
        self._postponed_evaluation_enabled = False

    @utils.only_required_for_messages(
        "unbalanced-dict-unpacking",
    )
    def visit_for(self, node: nodes.For) -> None:
        if not isinstance(node.target, nodes.Tuple):
            return

        targets = node.target.elts

        inferred = utils.safe_infer(node.iter)
        if not isinstance(inferred, DICT_TYPES):
            return

        values = self._nodes_to_unpack(inferred)
        if not values:
            # no dict items returned
            return

        if isinstance(inferred, astroid.objects.DictItems):
            # dict.items() is a bit special because values will be a tuple
            # So as long as there are always 2 targets and values each are
            # a tuple with two items, this will unpack correctly.
            # Example: `for key, val in {1: 2, 3: 4}.items()`
            if len(targets) == 2 and all(len(x.elts) == 2 for x in values):
                return

            # Starred nodes indicate ambiguous unpacking
            # if `dict.items()` is used so we won't flag them.
            if any(isinstance(target, nodes.Starred) for target in targets):
                return

        if isinstance(inferred, nodes.Dict):
            if isinstance(node.iter, nodes.Name):
                # If this a case of 'dict-items-missing-iter', we don't want to
                # report it as an 'unbalanced-dict-unpacking' as well
                # TODO (performance), merging both checks would streamline this
                if len(targets) == 2:
                    return

        else:
            is_starred_targets = any(
                isinstance(target, nodes.Starred) for target in targets
            )
            for value in values:
                value_length = self._get_value_length(value)
                is_valid_star_unpack = is_starred_targets and value_length >= len(
                    targets
                )
                if len(targets) != value_length and not is_valid_star_unpack:
                    details = _get_unpacking_extra_info(node, inferred)
                    self._report_unbalanced_unpacking(
                        node, inferred, targets, value_length, details
                    )
                    break

    def leave_for(self, node: nodes.For) -> None:
        self._store_type_annotation_names(node)

    def visit_module(self, node: nodes.Module) -> None:
        """Visit module : update consumption analysis variable
        checks globals doesn't overrides builtins.
        """
        self._to_consume = [NamesConsumer(node, "module")]
        self._postponed_evaluation_enabled = is_postponed_evaluation_enabled(node)

        for name, stmts in node.locals.items():
            if utils.is_builtin(name):
                if self._should_ignore_redefined_builtin(stmts[0]) or name == "__doc__":
                    continue
                self.add_message("redefined-builtin", args=name, node=stmts[0])

    @utils.only_required_for_messages(
        "unused-import",
        "unused-wildcard-import",
        "redefined-builtin",
        "undefined-all-variable",
        "invalid-all-object",
        "invalid-all-format",
        "unused-variable",
        "undefined-variable",
    )
    def leave_module(self, node: nodes.Module) -> None:
        """Leave module: check globals."""
        assert len(self._to_consume) == 1

        self._check_metaclasses(node)
        not_consumed = self._to_consume.pop().to_consume
        # attempt to check for __all__ if defined
        if "__all__" in node.locals:
            self._check_all(node, not_consumed)

        # check for unused globals
        self._check_globals(not_consumed)

        # don't check unused imports in __init__ files
        if not self.linter.config.init_import and node.package:
            return

        self._check_imports(not_consumed)
        self._type_annotation_names = []

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Visit class: update consumption analysis variable."""
        self._to_consume.append(NamesConsumer(node, "class"))

    def leave_classdef(self, node: nodes.ClassDef) -> None:
        """Leave class: update consumption analysis variable."""
        # Check for hidden ancestor names
        # e.g. "six" in: Class X(six.with_metaclass(ABCMeta, object)):
        for name_node in node.nodes_of_class(nodes.Name):
            if (
                isinstance(name_node.parent, nodes.Call)
                and isinstance(name_node.parent.func, nodes.Attribute)
                and isinstance(name_node.parent.func.expr, nodes.Name)
            ):
                hidden_name_node = name_node.parent.func.expr
                for consumer in self._to_consume:
                    if hidden_name_node.name in consumer.to_consume:
                        consumer.mark_as_consumed(
                            hidden_name_node.name,
                            consumer.to_consume[hidden_name_node.name],
                        )
                        break
        self._to_consume.pop()

    def visit_lambda(self, node: nodes.Lambda) -> None:
        """Visit lambda: update consumption analysis variable."""
        self._to_consume.append(NamesConsumer(node, "lambda"))

    def leave_lambda(self, _: nodes.Lambda) -> None:
        """Leave lambda: update consumption analysis variable."""
        # do not check for not used locals here
        self._to_consume.pop()

    def visit_generatorexp(self, node: nodes.GeneratorExp) -> None:
        """Visit genexpr: update consumption analysis variable."""
        self._to_consume.append(NamesConsumer(node, "comprehension"))

    def leave_generatorexp(self, _: nodes.GeneratorExp) -> None:
        """Leave genexpr: update consumption analysis variable."""
        # do not check for not used locals here
        self._to_consume.pop()

    def visit_dictcomp(self, node: nodes.DictComp) -> None:
        """Visit dictcomp: update consumption analysis variable."""
        self._to_consume.append(NamesConsumer(node, "comprehension"))

    def leave_dictcomp(self, _: nodes.DictComp) -> None:
        """Leave dictcomp: update consumption analysis variable."""
        # do not check for not used locals here
        self._to_consume.pop()

    def visit_setcomp(self, node: nodes.SetComp) -> None:
        """Visit setcomp: update consumption analysis variable."""
        self._to_consume.append(NamesConsumer(node, "comprehension"))

    def leave_setcomp(self, _: nodes.SetComp) -> None:
        """Leave setcomp: update consumption analysis variable."""
        # do not check for not used locals here
        self._to_consume.pop()

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Visit function: update consumption analysis variable and check locals."""
        self._to_consume.append(NamesConsumer(node, "function"))
        if not (
            self.linter.is_message_enabled("redefined-outer-name")
            or self.linter.is_message_enabled("redefined-builtin")
        ):
            return
        globs = node.root().globals
        for name, stmt in node.items():
            if name in globs and not isinstance(stmt, nodes.Global):
                definition = globs[name][0]
                if (
                    isinstance(definition, nodes.ImportFrom)
                    and definition.modname == FUTURE
                ):
                    # It is a __future__ directive, not a symbol.
                    continue

                # Do not take in account redefined names for the purpose
                # of type checking.:
                if any(
                    in_type_checking_block(definition) for definition in globs[name]
                ):
                    continue

                # Suppress emitting the message if the outer name is in the
                # scope of an exception assignment.
                # For example: the `e` in `except ValueError as e`
                global_node = globs[name][0]
                if isinstance(global_node, nodes.AssignName) and isinstance(
                    global_node.parent, nodes.ExceptHandler
                ):
                    continue

                line = definition.fromlineno
                if not self._is_name_ignored(stmt, name):
                    self.add_message(
                        "redefined-outer-name", args=(name, line), node=stmt
                    )

            elif (
                utils.is_builtin(name)
                and not self._allowed_redefined_builtin(name)
                and not self._should_ignore_redefined_builtin(stmt)
            ):
                # do not print Redefining builtin for additional builtins
                self.add_message("redefined-builtin", args=name, node=stmt)

    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        """Leave function: check function's locals are consumed."""
        self._check_metaclasses(node)

        if node.type_comment_returns:
            self._store_type_annotation_node(node.type_comment_returns)
        if node.type_comment_args:
            for argument_annotation in node.type_comment_args:
                self._store_type_annotation_node(argument_annotation)

        not_consumed = self._to_consume.pop().to_consume
        if not (
            self.linter.is_message_enabled("unused-variable")
            or self.linter.is_message_enabled("possibly-unused-variable")
            or self.linter.is_message_enabled("unused-argument")
        ):
            return

        # Don't check arguments of function which are only raising an exception.
        if utils.is_error(node):
            return

        # Don't check arguments of abstract methods or within an interface.
        is_method = node.is_method()
        if is_method and node.is_abstract():
            return

        global_names = _flattened_scope_names(node.nodes_of_class(nodes.Global))
        nonlocal_names = _flattened_scope_names(node.nodes_of_class(nodes.Nonlocal))
        comprehension_target_names: set[str] = set()

        for comprehension_scope in node.nodes_of_class(nodes.ComprehensionScope):
            for generator in comprehension_scope.generators:
                for name in utils.find_assigned_names_recursive(generator.target):
                    comprehension_target_names.add(name)

        for name, stmts in not_consumed.items():
            self._check_is_unused(
                name,
                node,
                stmts[0],
                global_names,
                nonlocal_names,
                comprehension_target_names,
            )

    visit_asyncfunctiondef = visit_functiondef
    leave_asyncfunctiondef = leave_functiondef

    @utils.only_required_for_messages(
        "global-variable-undefined",
        "global-variable-not-assigned",
        "global-statement",
        "global-at-module-level",
        "redefined-builtin",
    )
    def visit_global(self, node: nodes.Global) -> None:
        """Check names imported exists in the global scope."""
        frame = node.frame()
        if isinstance(frame, nodes.Module):
            self.add_message("global-at-module-level", node=node, confidence=HIGH)
            return

        module = frame.root()
        default_message = True
        locals_ = node.scope().locals
        for name in node.names:
            try:
                assign_nodes = module.getattr(name)
            except astroid.NotFoundError:
                # unassigned global, skip
                assign_nodes = []

            not_defined_locally_by_import = not any(
                isinstance(local, (nodes.Import, nodes.ImportFrom))
                for local in locals_.get(name, ())
            )
            if (
                not utils.is_reassigned_after_current(node, name)
                and not utils.is_deleted_after_current(node, name)
                and not_defined_locally_by_import
            ):
                self.add_message(
                    "global-variable-not-assigned",
                    args=name,
                    node=node,
                    confidence=HIGH,
                )
                default_message = False
                continue

            for anode in assign_nodes:
                if (
                    isinstance(anode, nodes.AssignName)
                    and anode.name in module.special_attributes
                ):
                    self.add_message("redefined-builtin", args=name, node=node)
                    break
                if anode.frame() is module:
                    # module level assignment
                    break
                if (
                    isinstance(anode, (nodes.ClassDef, nodes.FunctionDef))
                    and anode.parent is module
                ):
                    # module level function assignment
                    break
            else:
                if not_defined_locally_by_import:
                    # global undefined at the module scope
                    self.add_message(
                        "global-variable-undefined",
                        args=name,
                        node=node,
                        confidence=HIGH,
                    )
                    default_message = False

        if default_message:
            self.add_message("global-statement", node=node, confidence=HIGH)

    def visit_assignname(self, node: nodes.AssignName) -> None:
        if isinstance(node.assign_type(), nodes.AugAssign):
            self.visit_name(node)

    def visit_delname(self, node: nodes.DelName) -> None:
        self.visit_name(node)

    def visit_name(self, node: nodes.Name | nodes.AssignName | nodes.DelName) -> None:
        """Don't add the 'utils.only_required_for_messages' decorator here!

        It's important that all 'Name' nodes are visited, otherwise the
        'NamesConsumers' won't be correct.
        """
        stmt = node.statement()
        if stmt.fromlineno is None:
            # name node from an astroid built from live code, skip
            assert not stmt.root().file.endswith(".py")
            return

        self._undefined_and_used_before_checker(node, stmt)
        self._loopvar_name(node)

    @utils.only_required_for_messages("redefined-outer-name")
    def visit_excepthandler(self, node: nodes.ExceptHandler) -> None:
        if not node.name or not isinstance(node.name, nodes.AssignName):
            return

        for outer_except, outer_except_assign_name in self._except_handler_names_queue:
            if node.name.name == outer_except_assign_name.name:
                self.add_message(
                    "redefined-outer-name",
                    args=(outer_except_assign_name.name, outer_except.fromlineno),
                    node=node,
                )
                break

        self._except_handler_names_queue.append((node, node.name))

    @utils.only_required_for_messages("redefined-outer-name")
    def leave_excepthandler(self, node: nodes.ExceptHandler) -> None:
        if not node.name or not isinstance(node.name, nodes.AssignName):
            return
        self._except_handler_names_queue.pop()

    def _undefined_and_used_before_checker(
        self, node: nodes.Name, stmt: nodes.NodeNG
    ) -> None:
        frame = stmt.scope()
        start_index = len(self._to_consume) - 1

        # iterates through parent scopes, from the inner to the outer
        base_scope_type = self._to_consume[start_index].scope_type

        for i in range(start_index, -1, -1):
            current_consumer = self._to_consume[i]

            # Certain nodes shouldn't be checked as they get checked another time
            if self._should_node_be_skipped(node, current_consumer, i == start_index):
                continue

            action, nodes_to_consume = self._check_consumer(
                node, stmt, frame, current_consumer, base_scope_type
            )
            if nodes_to_consume:
                # Any nodes added to consumed_uncertain by get_next_to_consume()
                # should be added back so that they are marked as used.
                # They will have already had a chance to emit used-before-assignment.
                # We check here instead of before every single return in _check_consumer()
                nodes_to_consume += current_consumer.consumed_uncertain[node.name]
                current_consumer.mark_as_consumed(node.name, nodes_to_consume)
            if action is VariableVisitConsumerAction.CONTINUE:
                continue
            if action is VariableVisitConsumerAction.RETURN:
                return

        # we have not found the name, if it isn't a builtin, that's an
        # undefined name !
        if not (
            node.name in nodes.Module.scope_attrs
            or utils.is_builtin(node.name)
            or node.name in self.linter.config.additional_builtins
            or (
                node.name == "__class__"
                and any(
                    i.is_method()
                    for i in node.node_ancestors()
                    if isinstance(i, nodes.FunctionDef)
                )
            )
        ) and not utils.node_ignores_exception(node, NameError):
            self.add_message("undefined-variable", args=node.name, node=node)

    def _should_node_be_skipped(
        self, node: nodes.Name, consumer: NamesConsumer, is_start_index: bool
    ) -> bool:
        """Tests a consumer and node for various conditions in which the node shouldn't
        be checked for the undefined-variable and used-before-assignment checks.
        """
        if consumer.scope_type == "class":
            # The list of base classes in the class definition is not part
            # of the class body.
            # If the current scope is a class scope but it's not the inner
            # scope, ignore it. This prevents to access this scope instead of
            # the globals one in function members when there are some common
            # names.
            if utils.is_ancestor_name(consumer.node, node) or (
                not is_start_index and self._ignore_class_scope(node)
            ):
                if any(
                    node.name == param.name.name for param in consumer.node.type_params
                ):
                    return False

                return True

            # Ignore inner class scope for keywords in class definition
            if isinstance(node.parent, nodes.Keyword) and isinstance(
                node.parent.parent, nodes.ClassDef
            ):
                return True

        elif consumer.scope_type == "function" and self._defined_in_function_definition(
            node, consumer.node
        ):
            if any(node.name == param.name.name for param in consumer.node.type_params):
                return False

            # If the name node is used as a function default argument's value or as
            # a decorator, then start from the parent frame of the function instead
            # of the function frame - and thus open an inner class scope
            return True

        elif consumer.scope_type == "lambda" and utils.is_default_argument(
            node, consumer.node
        ):
            return True

        return False

    # pylint: disable = too-many-return-statements, too-many-branches
    def _check_consumer(
        self,
        node: nodes.Name,
        stmt: nodes.NodeNG,
        frame: nodes.LocalsDictNodeNG,
        current_consumer: NamesConsumer,
        base_scope_type: str,
    ) -> tuple[VariableVisitConsumerAction, list[nodes.NodeNG] | None]:
        """Checks a consumer for conditions that should trigger messages."""
        # If the name has already been consumed, only check it's not a loop
        # variable used outside the loop.
        if node.name in current_consumer.consumed:
            # Avoid the case where there are homonyms inside function scope and
            # comprehension current scope (avoid bug #1731)
            if utils.is_func_decorator(current_consumer.node) or not isinstance(
                node, nodes.ComprehensionScope
            ):
                self._check_late_binding_closure(node)
                return (VariableVisitConsumerAction.RETURN, None)

        found_nodes = current_consumer.get_next_to_consume(node)
        if found_nodes is None:
            return (VariableVisitConsumerAction.CONTINUE, None)
        if not found_nodes:
            self._report_unfound_name_definition(node, current_consumer)
            # Mark for consumption any nodes added to consumed_uncertain by
            # get_next_to_consume() because they might not have executed.
            nodes_to_consume = current_consumer.consumed_uncertain[node.name]
            nodes_to_consume = self._filter_type_checking_import_from_consumption(
                node, nodes_to_consume
            )
            return (
                VariableVisitConsumerAction.RETURN,
                nodes_to_consume,
            )

        self._check_late_binding_closure(node)

        defnode = utils.assign_parent(found_nodes[0])
        defstmt = defnode.statement()
        defframe = defstmt.frame()

        # The class reuses itself in the class scope.
        is_recursive_klass: bool = (
            frame is defframe
            and defframe.parent_of(node)
            and isinstance(defframe, nodes.ClassDef)
            and node.name == defframe.name
        )

        if (
            is_recursive_klass
            and utils.get_node_first_ancestor_of_type(node, nodes.Lambda)
            and (
                not utils.is_default_argument(node)
                or node.scope().parent.scope() is not defframe
            )
        ):
            # Self-referential class references are fine in lambda's --
            # As long as they are not part of the default argument directly
            # under the scope of the parent self-referring class.
            # Example of valid default argument:
            # class MyName3:
            #     myattr = 1
            #     mylambda3 = lambda: lambda a=MyName3: a
            # Example of invalid default argument:
            # class MyName4:
            #     myattr = 1
            #     mylambda4 = lambda a=MyName4: lambda: a

            # If the above conditional is True,
            # there is no possibility of undefined-variable
            # Also do not consume class name
            # (since consuming blocks subsequent checks)
            # -- quit
            return (VariableVisitConsumerAction.RETURN, None)

        (
            maybe_before_assign,
            annotation_return,
            use_outer_definition,
        ) = self._is_variable_violation(
            node,
            defnode,
            stmt,
            defstmt,
            frame,
            defframe,
            base_scope_type,
            is_recursive_klass,
        )

        if use_outer_definition:
            return (VariableVisitConsumerAction.CONTINUE, None)

        if (
            maybe_before_assign
            and not utils.is_defined_before(node)
            and not astroid.are_exclusive(stmt, defstmt, ("NameError",))
        ):
            # Used and defined in the same place, e.g `x += 1` and `del x`
            defined_by_stmt = defstmt is stmt and isinstance(
                node, (nodes.DelName, nodes.AssignName)
            )
            if (
                is_recursive_klass
                or defined_by_stmt
                or annotation_return
                or isinstance(defstmt, nodes.Delete)
            ):
                if not utils.node_ignores_exception(node, NameError):
                    # Handle postponed evaluation of annotations
                    if not (
                        self._postponed_evaluation_enabled
                        and isinstance(
                            stmt,
                            (
                                nodes.AnnAssign,
                                nodes.FunctionDef,
                                nodes.Arguments,
                            ),
                        )
                        and node.name in node.root().locals
                    ):
                        if defined_by_stmt:
                            return (VariableVisitConsumerAction.CONTINUE, [node])
                        return (VariableVisitConsumerAction.CONTINUE, None)

            elif base_scope_type != "lambda":
                # E0601 may *not* occurs in lambda scope.

                # Skip postponed evaluation of annotations
                # and unevaluated annotations inside a function body
                if not (
                    self._postponed_evaluation_enabled
                    and isinstance(stmt, (nodes.AnnAssign, nodes.FunctionDef))
                ) and not (
                    isinstance(stmt, nodes.AnnAssign)
                    and utils.get_node_first_ancestor_of_type(stmt, nodes.FunctionDef)
                ):
                    self.add_message(
                        "used-before-assignment",
                        args=node.name,
                        node=node,
                        confidence=HIGH,
                    )
                    return (VariableVisitConsumerAction.RETURN, found_nodes)

            elif base_scope_type == "lambda":
                # E0601 can occur in class-level scope in lambdas, as in
                # the following example:
                #   class A:
                #      x = lambda attr: f + attr
                #      f = 42
                # We check lineno because doing the following is fine:
                #   class A:
                #      x = 42
                #      y = lambda attr: x + attr
                if (
                    isinstance(frame, nodes.ClassDef)
                    and node.name in frame.locals
                    and stmt.fromlineno <= defstmt.fromlineno
                ):
                    self.add_message(
                        "used-before-assignment",
                        args=node.name,
                        node=node,
                        confidence=HIGH,
                    )

        elif not self._is_builtin(node.name) and self._is_only_type_assignment(
            node, defstmt
        ):
            if node.scope().locals.get(node.name):
                self.add_message(
                    "used-before-assignment", args=node.name, node=node, confidence=HIGH
                )
            else:
                self.add_message(
                    "undefined-variable", args=node.name, node=node, confidence=HIGH
                )
            return (VariableVisitConsumerAction.RETURN, found_nodes)

        elif (
            isinstance(defstmt, nodes.ClassDef) and defnode not in defframe.type_params
        ):
            return self._is_first_level_self_reference(node, defstmt, found_nodes)

        elif isinstance(defnode, nodes.NamedExpr):
            if isinstance(defnode.parent, nodes.IfExp):
                if self._is_never_evaluated(defnode, defnode.parent):
                    self.add_message(
                        "undefined-variable",
                        args=node.name,
                        node=node,
                        confidence=INFERENCE,
                    )
                    return (VariableVisitConsumerAction.RETURN, found_nodes)

        return (VariableVisitConsumerAction.RETURN, found_nodes)

    def _report_unfound_name_definition(
        self, node: nodes.NodeNG, current_consumer: NamesConsumer
    ) -> None:
        """Reports used-before-assignment when all name definition nodes
        get filtered out by NamesConsumer.
        """
        if (
            self._postponed_evaluation_enabled
            and utils.is_node_in_type_annotation_context(node)
        ):
            return
        if self._is_builtin(node.name):
            return
        if self._is_variable_annotation_in_function(node):
            return
        if (
            node.name in self._evaluated_type_checking_scopes
            and node.scope() in self._evaluated_type_checking_scopes[node.name]
        ):
            return

        confidence = HIGH
        if node.name in current_consumer.names_under_always_false_test:
            confidence = INFERENCE
        elif node.name in current_consumer.consumed_uncertain:
            confidence = CONTROL_FLOW

        if node.name in current_consumer.names_defined_under_one_branch_only:
            msg = "possibly-used-before-assignment"
        else:
            msg = "used-before-assignment"

        self.add_message(
            msg,
            args=node.name,
            node=node,
            confidence=confidence,
        )

    def _filter_type_checking_import_from_consumption(
        self, node: nodes.NodeNG, nodes_to_consume: list[nodes.NodeNG]
    ) -> list[nodes.NodeNG]:
        """Do not consume type-checking import node as used-before-assignment
        may invoke in different scopes.
        """
        type_checking_import = next(
            (
                n
                for n in nodes_to_consume
                if isinstance(n, (nodes.Import, nodes.ImportFrom))
                and in_type_checking_block(n)
            ),
            None,
        )
        # If used-before-assignment reported for usage of type checking import
        # keep track of its scope
        if type_checking_import and not self._is_variable_annotation_in_function(node):
            self._evaluated_type_checking_scopes.setdefault(node.name, []).append(
                node.scope()
            )
        nodes_to_consume = [n for n in nodes_to_consume if n != type_checking_import]
        return nodes_to_consume

    @utils.only_required_for_messages("no-name-in-module")
    def visit_import(self, node: nodes.Import) -> None:
        """Check modules attribute accesses."""
        if not self._analyse_fallback_blocks and utils.is_from_fallback_block(node):
            # No need to verify this, since ImportError is already
            # handled by the client code.
            return
        # Don't verify import if part of guarded import block
        if in_type_checking_block(node):
            return
        if isinstance(node.parent, nodes.If) and is_sys_guard(node.parent):
            return

        for name, _ in node.names:
            parts = name.split(".")
            try:
                module = next(_infer_name_module(node, parts[0]))
            except astroid.ResolveError:
                continue
            if not isinstance(module, nodes.Module):
                continue
            self._check_module_attrs(node, module, parts[1:])

    @utils.only_required_for_messages("no-name-in-module")
    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Check modules attribute accesses."""
        if not self._analyse_fallback_blocks and utils.is_from_fallback_block(node):
            # No need to verify this, since ImportError is already
            # handled by the client code.
            return
        # Don't verify import if part of guarded import block
        # I.e. `sys.version_info` or `typing.TYPE_CHECKING`
        if in_type_checking_block(node):
            return
        if isinstance(node.parent, nodes.If) and is_sys_guard(node.parent):
            return

        name_parts = node.modname.split(".")
        try:
            module = node.do_import_module(name_parts[0])
        except astroid.AstroidBuildingError:
            return
        module = self._check_module_attrs(node, module, name_parts[1:])
        if not module:
            return
        for name, _ in node.names:
            if name == "*":
                continue
            self._check_module_attrs(node, module, name.split("."))

    @utils.only_required_for_messages(
        "unbalanced-tuple-unpacking",
        "unpacking-non-sequence",
        "self-cls-assignment",
        "unbalanced_dict_unpacking",
    )
    def visit_assign(self, node: nodes.Assign) -> None:
        """Check unbalanced tuple unpacking for assignments and unpacking
        non-sequences as well as in case self/cls get assigned.
        """
        self._check_self_cls_assign(node)
        if not isinstance(node.targets[0], (nodes.Tuple, nodes.List)):
            return

        targets = node.targets[0].itered()

        # Check if we have starred nodes.
        if any(isinstance(target, nodes.Starred) for target in targets):
            return

        try:
            inferred = utils.safe_infer(node.value)
            if inferred is not None:
                self._check_unpacking(inferred, node, targets)
        except astroid.InferenceError:
            return

    # listcomp have now also their scope
    def visit_listcomp(self, node: nodes.ListComp) -> None:
        """Visit listcomp: update consumption analysis variable."""
        self._to_consume.append(NamesConsumer(node, "comprehension"))

    def leave_listcomp(self, _: nodes.ListComp) -> None:
        """Leave listcomp: update consumption analysis variable."""
        # do not check for not used locals here
        self._to_consume.pop()

    def leave_assign(self, node: nodes.Assign) -> None:
        self._store_type_annotation_names(node)

    def leave_with(self, node: nodes.With) -> None:
        self._store_type_annotation_names(node)

    def visit_arguments(self, node: nodes.Arguments) -> None:
        for annotation in node.type_comment_args:
            self._store_type_annotation_node(annotation)

    # Relying on other checker's options, which might not have been initialized yet.
    @cached_property
    def _analyse_fallback_blocks(self) -> bool:
        return bool(self.linter.config.analyse_fallback_blocks)

    @cached_property
    def _ignored_modules(self) -> Iterable[str]:
        return self.linter.config.ignored_modules  # type: ignore[no-any-return]

    @cached_property
    def _allow_global_unused_variables(self) -> bool:
        return bool(self.linter.config.allow_global_unused_variables)

    @staticmethod
    def _defined_in_function_definition(
        node: nodes.NodeNG, frame: nodes.NodeNG
    ) -> bool:
        in_annotation_or_default_or_decorator = False
        if isinstance(frame, nodes.FunctionDef) and node.statement() is frame:
            in_annotation_or_default_or_decorator = (
                (
                    node in frame.args.annotations
                    or node in frame.args.posonlyargs_annotations
                    or node in frame.args.kwonlyargs_annotations
                    or node is frame.args.varargannotation
                    or node is frame.args.kwargannotation
                )
                or frame.args.parent_of(node)
                or (frame.decorators and frame.decorators.parent_of(node))
                or (
                    frame.returns
                    and (node is frame.returns or frame.returns.parent_of(node))
                )
            )
        return in_annotation_or_default_or_decorator

    @staticmethod
    def _in_lambda_or_comprehension_body(
        node: nodes.NodeNG, frame: nodes.NodeNG
    ) -> bool:
        """Return True if node within a lambda/comprehension body (or similar) and thus
        should not have access to class attributes in frame.
        """
        child = node
        parent = node.parent
        while parent is not None:
            if parent is frame:
                return False
            if isinstance(parent, nodes.Lambda) and child is not parent.args:
                # Body of lambda should not have access to class attributes.
                return True
            if isinstance(parent, nodes.Comprehension) and child is not parent.iter:
                # Only iter of list/set/dict/generator comprehension should have access.
                return True
            if isinstance(parent, nodes.ComprehensionScope) and not (
                parent.generators and child is parent.generators[0]
            ):
                # Body of list/set/dict/generator comprehension should not have access to class attributes.
                # Furthermore, only the first generator (if multiple) in comprehension should have access.
                return True
            child = parent
            parent = parent.parent
        return False

    @staticmethod
    def _is_variable_violation(
        node: nodes.Name,
        defnode: nodes.NodeNG,
        stmt: _base_nodes.Statement,
        defstmt: _base_nodes.Statement,
        frame: nodes.LocalsDictNodeNG,  # scope of statement of node
        defframe: nodes.LocalsDictNodeNG,
        base_scope_type: str,
        is_recursive_klass: bool,
    ) -> tuple[bool, bool, bool]:
        maybe_before_assign = True
        annotation_return = False
        use_outer_definition = False
        if frame is not defframe:
            maybe_before_assign = _detect_global_scope(node, frame, defframe)
        elif defframe.parent is None:
            # we are at the module level, check the name is not
            # defined in builtins
            if (
                node.name in defframe.scope_attrs
                or astroid.builtin_lookup(node.name)[1]
            ):
                maybe_before_assign = False
        else:
            # we are in a local scope, check the name is not
            # defined in global or builtin scope
            # skip this lookup if name is assigned later in function scope/lambda
            # Note: the node.frame() is not the same as the `frame` argument which is
            # equivalent to frame.statement().scope()
            forbid_lookup = (
                isinstance(frame, nodes.FunctionDef)
                or isinstance(node.frame(), nodes.Lambda)
            ) and _assigned_locally(node)
            if not forbid_lookup and defframe.root().lookup(node.name)[1]:
                maybe_before_assign = False
                use_outer_definition = stmt == defstmt and not isinstance(
                    defnode, nodes.Comprehension
                )
            # check if we have a nonlocal
            elif node.name in defframe.locals:
                maybe_before_assign = not any(
                    isinstance(child, nodes.Nonlocal) and node.name in child.names
                    for child in defframe.get_children()
                )

        if (
            base_scope_type == "lambda"
            and isinstance(frame, nodes.ClassDef)
            and node.name in frame.locals
        ):
            # This rule verifies that if the definition node of the
            # checked name is an Arguments node and if the name
            # is used a default value in the arguments defaults
            # and the actual definition of the variable label
            # is happening before the Arguments definition.
            #
            # bar = None
            # foo = lambda bar=bar: bar
            #
            # In this case, maybe_before_assign should be False, otherwise
            # it should be True.
            maybe_before_assign = not (
                isinstance(defnode, nodes.Arguments)
                and node in defnode.defaults
                and frame.locals[node.name][0].fromlineno < defstmt.fromlineno
            )
        elif isinstance(defframe, nodes.ClassDef) and isinstance(
            frame, nodes.FunctionDef
        ):
            # Special rules for function return annotations.
            if node is frame.returns:
                # Using a name defined earlier in the class containing the function.
                if defframe.parent_of(frame.returns):
                    annotation_return = True
                    if frame.returns.name in defframe.locals:
                        definition = defframe.locals[node.name][0]
                        # no warning raised if a name was defined earlier in the class
                        maybe_before_assign = (
                            definition.lineno is not None
                            and definition.lineno >= frame.lineno
                        )
                    else:
                        maybe_before_assign = True
                # Using a name defined in the module if this is a nested function.
                elif (
                    # defframe is the class containing the function.
                    # It shouldn't be nested: expect its parent to be a module.
                    (defframe_parent := next(defframe.node_ancestors()))
                    and isinstance(defframe_parent, nodes.Module)
                    # frame is the function inside the class.
                    and (frame_ancestors := tuple(frame.node_ancestors()))
                    # Does that function have any functions as ancestors?
                    and any(
                        isinstance(ancestor, nodes.FunctionDef)
                        for ancestor in frame_ancestors
                    )
                    # And is its last ancestor the same module as the class's?
                    and frame_ancestors[-1] is defframe_parent
                ):
                    annotation_return = True
                    maybe_before_assign = False
            if isinstance(node.parent, nodes.Arguments):
                maybe_before_assign = stmt.fromlineno <= defstmt.fromlineno
        elif is_recursive_klass:
            maybe_before_assign = True
        else:
            maybe_before_assign = (
                maybe_before_assign and stmt.fromlineno <= defstmt.fromlineno
            )
            if maybe_before_assign and stmt.fromlineno == defstmt.fromlineno:
                if (
                    isinstance(defframe, nodes.FunctionDef)
                    and frame is defframe
                    and defframe.parent_of(node)
                    and (
                        defnode in defframe.type_params
                        # Single statement function, with the statement on the
                        # same line as the function definition
                        or stmt is not defstmt
                    )
                ):
                    maybe_before_assign = False
                elif (
                    isinstance(defstmt, NODES_WITH_VALUE_ATTR)
                    and VariablesChecker._maybe_used_and_assigned_at_once(defstmt)
                    and frame is defframe
                    and defframe.parent_of(node)
                    and stmt is defstmt
                ):
                    # Single statement if, with assignment expression on same
                    # line as assignment
                    # x = b if (b := True) else False
                    maybe_before_assign = False
                elif (
                    isinstance(  # pylint: disable=too-many-boolean-expressions
                        defnode, nodes.NamedExpr
                    )
                    and frame is defframe
                    and defframe.parent_of(stmt)
                    and stmt is defstmt
                    and (
                        (
                            defnode.lineno == node.lineno
                            and defnode.col_offset < node.col_offset
                        )
                        or (defnode.lineno < node.lineno)
                    )
                ):
                    # Relation of a name to the same name in a named expression
                    # Could be used before assignment if self-referencing:
                    # (b := b)
                    # Otherwise, safe if used after assignment:
                    # (b := 2) and b
                    maybe_before_assign = defnode.value is node or any(
                        anc is defnode.value for anc in node.node_ancestors()
                    )
                elif (
                    isinstance(defframe, nodes.ClassDef)
                    and defnode in defframe.type_params
                ):
                    # Generic on parent class:
                    # class Child[_T](Parent[_T])
                    maybe_before_assign = False

        return maybe_before_assign, annotation_return, use_outer_definition

    @staticmethod
    def _maybe_used_and_assigned_at_once(defstmt: _base_nodes.Statement) -> bool:
        """Check if `defstmt` has the potential to use and assign a name in the
        same statement.
        """
        if isinstance(defstmt, nodes.Match):
            return any(case.guard for case in defstmt.cases)
        if isinstance(defstmt, nodes.IfExp):
            return True
        if isinstance(defstmt, nodes.TypeAlias):
            return True
        if isinstance(defstmt.value, nodes.BaseContainer):
            return any(
                VariablesChecker._maybe_used_and_assigned_at_once(elt)
                for elt in defstmt.value.elts
                if isinstance(elt, (*NODES_WITH_VALUE_ATTR, nodes.IfExp, nodes.Match))
            )
        value = defstmt.value
        if isinstance(value, nodes.IfExp):
            return True
        if isinstance(value, nodes.Lambda) and isinstance(value.body, nodes.IfExp):
            return True
        if isinstance(value, nodes.Dict) and any(
            isinstance(item[0], nodes.IfExp) or isinstance(item[1], nodes.IfExp)
            for item in value.items
        ):
            return True
        if not isinstance(value, nodes.Call):
            return False
        return any(
            any(isinstance(kwarg.value, nodes.IfExp) for kwarg in call.keywords)
            or any(isinstance(arg, nodes.IfExp) for arg in call.args)
            or (
                isinstance(call.func, nodes.Attribute)
                and isinstance(call.func.expr, nodes.IfExp)
            )
            for call in value.nodes_of_class(klass=nodes.Call)
        )

    def _is_builtin(self, name: str) -> bool:
        return name in self.linter.config.additional_builtins or utils.is_builtin(name)

    @staticmethod
    def _is_only_type_assignment(
        node: nodes.Name, defstmt: _base_nodes.Statement
    ) -> bool:
        """Check if variable only gets assigned a type and never a value."""
        if not isinstance(defstmt, nodes.AnnAssign) or defstmt.value:
            return False

        defstmt_frame = defstmt.frame()
        node_frame = node.frame()

        parent = node
        while parent is not defstmt_frame.parent:
            parent_scope = parent.scope()

            # Find out if any nonlocals receive values in nested functions
            for inner_func in parent_scope.nodes_of_class(nodes.FunctionDef):
                if inner_func is parent_scope:
                    continue
                if any(
                    node.name in nl.names
                    for nl in inner_func.nodes_of_class(nodes.Nonlocal)
                ) and any(
                    node.name == an.name
                    for an in inner_func.nodes_of_class(nodes.AssignName)
                ):
                    return False

            local_refs = parent_scope.locals.get(node.name, [])
            for ref_node in local_refs:
                # If local ref is in the same frame as our node, but on a later lineno
                # we don't actually care about this local ref.
                # Local refs are ordered, so we break.
                #     print(var)
                #     var = 1  # <- irrelevant
                if defstmt_frame == node_frame and ref_node.lineno > node.lineno:
                    break

                # If the parent of the local reference is anything but an AnnAssign
                # Or if the AnnAssign adds a value the variable will now have a value
                #     var = 1  # OR
                #     var: int = 1
                if (
                    not isinstance(ref_node.parent, nodes.AnnAssign)
                    or ref_node.parent.value
                ) and not (
                    # EXCEPTION: will not have a value if a self-referencing named expression
                    # var: int
                    # if (var := var * var)  <-- "var" still undefined
                    isinstance(ref_node.parent, nodes.NamedExpr)
                    and any(
                        anc is ref_node.parent.value for anc in node.node_ancestors()
                    )
                ):
                    return False
            parent = parent_scope.parent
        return True

    @staticmethod
    def _is_first_level_self_reference(
        node: nodes.Name, defstmt: nodes.ClassDef, found_nodes: list[nodes.NodeNG]
    ) -> tuple[VariableVisitConsumerAction, list[nodes.NodeNG] | None]:
        """Check if a first level method's annotation or default values
        refers to its own class, and return a consumer action.
        """
        if node.frame().parent == defstmt and node.statement() == node.frame():
            # Check if used as type annotation
            # Break if postponed evaluation is enabled
            if utils.is_node_in_type_annotation_context(node):
                if not utils.is_postponed_evaluation_enabled(node):
                    return (VariableVisitConsumerAction.CONTINUE, None)
                return (VariableVisitConsumerAction.RETURN, None)
            # Check if used as default value by calling the class
            if isinstance(node.parent, nodes.Call) and isinstance(
                node.parent.parent, nodes.Arguments
            ):
                return (VariableVisitConsumerAction.CONTINUE, None)
        return (VariableVisitConsumerAction.RETURN, found_nodes)

    @staticmethod
    def _is_never_evaluated(
        defnode: nodes.NamedExpr, defnode_parent: nodes.IfExp
    ) -> bool:
        """Check if a NamedExpr is inside a side of if ... else that never
        gets evaluated.
        """
        inferred_test = utils.safe_infer(defnode_parent.test)
        if isinstance(inferred_test, nodes.Const):
            if inferred_test.value is True and defnode == defnode_parent.orelse:
                return True
            if inferred_test.value is False and defnode == defnode_parent.body:
                return True
        return False

    @staticmethod
    def _is_variable_annotation_in_function(node: nodes.NodeNG) -> bool:
        is_annotation = utils.get_node_first_ancestor_of_type(node, nodes.AnnAssign)
        return (
            is_annotation
            and utils.get_node_first_ancestor_of_type(  # type: ignore[return-value]
                is_annotation, nodes.FunctionDef
            )
        )

    def _ignore_class_scope(self, node: nodes.NodeNG) -> bool:
        """Return True if the node is in a local class scope, as an assignment.

        Detect if we are in a local class scope, as an assignment.
        For example, the following is fair game.

        class A:
           b = 1
           c = lambda b=b: b * b

        class B:
           tp = 1
           def func(self, arg: tp):
               ...
        class C:
           tp = 2
           def func(self, arg=tp):
               ...
        class C:
           class Tp:
               pass
           class D(Tp):
               ...
        """
        name = node.name
        frame = node.statement().scope()
        in_annotation_or_default_or_decorator = self._defined_in_function_definition(
            node, frame
        )
        in_ancestor_list = utils.is_ancestor_name(frame, node)
        if in_annotation_or_default_or_decorator or in_ancestor_list:
            frame_locals = frame.parent.scope().locals
        else:
            frame_locals = frame.locals
        return not (
            (isinstance(frame, nodes.ClassDef) or in_annotation_or_default_or_decorator)
            and not self._in_lambda_or_comprehension_body(node, frame)
            and name in frame_locals
        )

    # pylint: disable-next=too-many-branches,too-many-statements
    def _loopvar_name(self, node: astroid.Name) -> None:
        # filter variables according to node's scope
        astmts = [s for s in node.lookup(node.name)[1] if hasattr(s, "assign_type")]
        # If this variable usage exists inside a function definition
        # that exists in the same loop,
        # the usage is safe because the function will not be defined either if
        # the variable is not defined.
        scope = node.scope()
        if isinstance(scope, (nodes.Lambda, nodes.FunctionDef)) and any(
            asmt.scope().parent_of(scope) for asmt in astmts
        ):
            return
        # Filter variables according to their respective scope. Test parent
        # and statement to avoid #74747. This is not a total fix, which would
        # introduce a mechanism similar to special attribute lookup in
        # modules. Also, in order to get correct inference in this case, the
        # scope lookup rules would need to be changed to return the initial
        # assignment (which does not exist in code per se) as well as any later
        # modifications.
        if (
            not astmts  # pylint: disable=too-many-boolean-expressions
            or (
                astmts[0].parent == astmts[0].root()
                and astmts[0].parent.parent_of(node)
            )
            or (
                astmts[0].is_statement
                or not isinstance(astmts[0].parent, nodes.Module)
                and astmts[0].statement().parent_of(node)
            )
        ):
            _astmts = []
        else:
            _astmts = astmts[:1]
        for i, stmt in enumerate(astmts[1:]):
            try:
                astmt_statement = astmts[i].statement()
            except astroid.exceptions.ParentMissingError:
                continue
            if astmt_statement.parent_of(stmt) and not utils.in_for_else_branch(
                astmt_statement, stmt
            ):
                continue
            _astmts.append(stmt)
        astmts = _astmts
        if len(astmts) != 1:
            return

        assign = astmts[0].assign_type()
        if not (
            isinstance(assign, (nodes.For, nodes.Comprehension, nodes.GeneratorExp))
            and assign.statement() is not node.statement()
        ):
            return

        if not isinstance(assign, nodes.For):
            self.add_message("undefined-loop-variable", args=node.name, node=node)
            return
        for else_stmt in assign.orelse:
            if isinstance(
                else_stmt, (nodes.Return, nodes.Raise, nodes.Break, nodes.Continue)
            ):
                return
            # TODO: 4.0: Consider using utils.is_terminating_func
            # after merging it with RefactoringChecker._is_function_def_never_returning
            if isinstance(else_stmt, nodes.Expr) and isinstance(
                else_stmt.value, nodes.Call
            ):
                inferred_func = utils.safe_infer(else_stmt.value.func)
                if (
                    isinstance(inferred_func, nodes.FunctionDef)
                    and inferred_func.returns
                ):
                    inferred_return = utils.safe_infer(inferred_func.returns)
                    if isinstance(
                        inferred_return, nodes.FunctionDef
                    ) and inferred_return.qname() in {
                        *TYPING_NORETURN,
                        *TYPING_NEVER,
                        "typing._SpecialForm",
                    }:
                        return
                    # typing_extensions.NoReturn returns a _SpecialForm
                    if (
                        isinstance(inferred_return, bases.Instance)
                        and inferred_return.qname() == "typing._SpecialForm"
                    ):
                        return

        maybe_walrus = utils.get_node_first_ancestor_of_type(node, nodes.NamedExpr)
        if maybe_walrus:
            maybe_comprehension = utils.get_node_first_ancestor_of_type(
                maybe_walrus, nodes.Comprehension
            )
            if maybe_comprehension:
                comprehension_scope = utils.get_node_first_ancestor_of_type(
                    maybe_comprehension, nodes.ComprehensionScope
                )
                if comprehension_scope is None:
                    # Should not be possible.
                    pass
                elif (
                    comprehension_scope.parent.scope() is scope
                    and node.name in comprehension_scope.locals
                ):
                    return

        # For functions we can do more by inferring the length of the itered object
        try:
            inferred = next(assign.iter.infer())
            # Prefer the target of enumerate() rather than the enumerate object itself
            if (
                isinstance(inferred, astroid.Instance)
                and inferred.qname() == "builtins.enumerate"
            ):
                likely_call = assign.iter
                if isinstance(assign.iter, nodes.IfExp):
                    likely_call = assign.iter.body
                if isinstance(likely_call, nodes.Call) and likely_call.args:
                    inferred = next(likely_call.args[0].infer())
        except astroid.InferenceError:
            self.add_message("undefined-loop-variable", args=node.name, node=node)
        else:
            if (
                isinstance(inferred, astroid.Instance)
                and inferred.qname() == BUILTIN_RANGE
            ):
                # Consider range() objects safe, even if they might not yield any results.
                return

            # Consider sequences.
            sequences = (
                nodes.List,
                nodes.Tuple,
                nodes.Dict,
                nodes.Set,
                astroid.objects.FrozenSet,
            )
            if not isinstance(inferred, sequences):
                self.add_message("undefined-loop-variable", args=node.name, node=node)
                return

            elements = getattr(inferred, "elts", getattr(inferred, "items", []))
            if not elements:
                self.add_message("undefined-loop-variable", args=node.name, node=node)

    # pylint: disable = too-many-branches
    def _check_is_unused(
        self,
        name: str,
        node: nodes.FunctionDef,
        stmt: nodes.NodeNG,
        global_names: set[str],
        nonlocal_names: Iterable[str],
        comprehension_target_names: Iterable[str],
    ) -> None:
        # Ignore some special names specified by user configuration.
        if self._is_name_ignored(stmt, name):
            return
        # Ignore names that were added dynamically to the Function scope
        if (
            isinstance(node, nodes.FunctionDef)
            and name == "__class__"
            and len(node.locals["__class__"]) == 1
            and isinstance(node.locals["__class__"][0], nodes.ClassDef)
        ):
            return

        # Ignore names imported by the global statement.
        if isinstance(stmt, (nodes.Global, nodes.Import, nodes.ImportFrom)):
            # Detect imports, assigned to global statements.
            if global_names and _import_name_is_global(stmt, global_names):
                return

        # Ignore names in comprehension targets
        if name in comprehension_target_names:
            return

        # Ignore names in string literal type annotation.
        if name in self._type_annotation_names:
            return

        argnames = node.argnames()
        # Care about functions with unknown argument (builtins)
        if name in argnames:
            if node.name == "__new__":
                is_init_def = False
                # Look for the `__init__` method in all the methods of the same class.
                for n in node.parent.get_children():
                    is_init_def = hasattr(n, "name") and (n.name == "__init__")
                    if is_init_def:
                        break
                # Ignore unused arguments check for `__new__` if `__init__` is defined.
                if is_init_def:
                    return
            self._check_unused_arguments(name, node, stmt, argnames, nonlocal_names)
        else:
            if stmt.parent and isinstance(
                stmt.parent, (nodes.Assign, nodes.AnnAssign, nodes.Tuple, nodes.For)
            ):
                if name in nonlocal_names:
                    return

            qname = asname = None
            if isinstance(stmt, (nodes.Import, nodes.ImportFrom)):
                # Need the complete name, which we don't have in .locals.
                if len(stmt.names) > 1:
                    import_names = next(
                        (names for names in stmt.names if name in names), None
                    )
                else:
                    import_names = stmt.names[0]
                if import_names:
                    qname, asname = import_names
                    name = asname or qname

            if _has_locals_call_after_node(stmt, node.scope()):
                message_name = "possibly-unused-variable"
            else:
                if isinstance(stmt, nodes.Import):
                    if asname is not None:
                        msg = f"{qname} imported as {asname}"
                    else:
                        msg = f"import {name}"
                    self.add_message("unused-import", args=msg, node=stmt)
                    return
                if isinstance(stmt, nodes.ImportFrom):
                    if asname is not None:
                        msg = f"{qname} imported from {stmt.modname} as {asname}"
                    else:
                        msg = f"{name} imported from {stmt.modname}"
                    self.add_message("unused-import", args=msg, node=stmt)
                    return
                message_name = "unused-variable"

            if isinstance(stmt, nodes.FunctionDef) and stmt.decorators:
                return

            # Don't check function stubs created only for type information
            if utils.is_overload_stub(node):
                return

            # Special case for exception variable
            if isinstance(stmt.parent, nodes.ExceptHandler) and any(
                n.name == name for n in stmt.parent.nodes_of_class(nodes.Name)
            ):
                return

            self.add_message(message_name, args=name, node=stmt)

    def _is_name_ignored(
        self, stmt: nodes.NodeNG, name: str
    ) -> re.Pattern[str] | re.Match[str] | None:
        authorized_rgx = self.linter.config.dummy_variables_rgx
        if (
            isinstance(stmt, nodes.AssignName)
            and isinstance(stmt.parent, nodes.Arguments)
            or isinstance(stmt, nodes.Arguments)
        ):
            regex: re.Pattern[str] = self.linter.config.ignored_argument_names
        else:
            regex = authorized_rgx
        # See https://stackoverflow.com/a/47007761/2519059 to
        # understand what this function return. Please do NOT use
        # this elsewhere, this is confusing for no benefit
        return regex and regex.match(name)

    def _check_unused_arguments(
        self,
        name: str,
        node: nodes.FunctionDef,
        stmt: nodes.NodeNG,
        argnames: list[str],
        nonlocal_names: Iterable[str],
    ) -> None:
        is_method = node.is_method()
        klass = node.parent.frame()
        if is_method and isinstance(klass, nodes.ClassDef):
            confidence = (
                INFERENCE if utils.has_known_bases(klass) else INFERENCE_FAILURE
            )
        else:
            confidence = HIGH

        if is_method:
            # Don't warn for the first argument of a (non static) method
            if node.type != "staticmethod" and name == argnames[0]:
                return
            # Don't warn for argument of an overridden method
            overridden = overridden_method(klass, node.name)
            if overridden is not None and name in overridden.argnames():
                return
            if node.name in utils.PYMETHODS and node.name not in (
                "__init__",
                "__new__",
            ):
                return
        # Don't check callback arguments
        if any(
            node.name.startswith(cb) or node.name.endswith(cb)
            for cb in self.linter.config.callbacks
        ):
            return
        # Don't check arguments of singledispatch.register function.
        if utils.is_registered_in_singledispatch_function(node):
            return

        # Don't check function stubs created only for type information
        if utils.is_overload_stub(node):
            return

        # Don't check protocol classes
        if utils.is_protocol_class(klass):
            return

        if name in nonlocal_names:
            return

        self.add_message("unused-argument", args=name, node=stmt, confidence=confidence)

    def _check_late_binding_closure(self, node: nodes.Name) -> None:
        """Check whether node is a cell var that is assigned within a containing loop.

        Special cases where we don't care about the error:
        1. When the node's function is immediately called, e.g. (lambda: i)()
        2. When the node's function is returned from within the loop, e.g. return lambda: i
        """
        if not self.linter.is_message_enabled("cell-var-from-loop"):
            return

        node_scope = node.frame()

        # If node appears in a default argument expression,
        # look at the next enclosing frame instead
        if utils.is_default_argument(node, node_scope):
            node_scope = node_scope.parent.frame()

        # Check if node is a cell var
        if (
            not isinstance(node_scope, (nodes.Lambda, nodes.FunctionDef))
            or node.name in node_scope.locals
        ):
            return

        assign_scope, stmts = node.lookup(node.name)
        if not stmts or not assign_scope.parent_of(node_scope):
            return

        if utils.is_comprehension(assign_scope):
            self.add_message("cell-var-from-loop", node=node, args=node.name)
        else:
            # Look for an enclosing For loop.
            # Currently, we only consider the first assignment
            assignment_node = stmts[0]

            maybe_for = assignment_node
            while maybe_for and not isinstance(maybe_for, nodes.For):
                if maybe_for is assign_scope:
                    break
                maybe_for = maybe_for.parent
            else:
                if (
                    maybe_for
                    and maybe_for.parent_of(node_scope)
                    and not utils.is_being_called(node_scope)
                    and node_scope.parent
                    and not isinstance(node_scope.statement(), nodes.Return)
                ):
                    self.add_message("cell-var-from-loop", node=node, args=node.name)

    def _should_ignore_redefined_builtin(self, stmt: nodes.NodeNG) -> bool:
        if not isinstance(stmt, nodes.ImportFrom):
            return False
        return stmt.modname in self.linter.config.redefining_builtins_modules

    def _allowed_redefined_builtin(self, name: str) -> bool:
        return name in self.linter.config.allowed_redefined_builtins

    @staticmethod
    def _comprehension_between_frame_and_node(node: nodes.Name) -> bool:
        """Return True if a ComprehensionScope intervenes between `node` and its
        frame.
        """
        closest_comprehension_scope = utils.get_node_first_ancestor_of_type(
            node, nodes.ComprehensionScope
        )
        return closest_comprehension_scope is not None and node.frame().parent_of(
            closest_comprehension_scope
        )

    def _store_type_annotation_node(self, type_annotation: nodes.NodeNG) -> None:
        """Given a type annotation, store all the name nodes it refers to."""
        if isinstance(type_annotation, nodes.Name):
            self._type_annotation_names.append(type_annotation.name)
            return

        if isinstance(type_annotation, nodes.Attribute):
            self._store_type_annotation_node(type_annotation.expr)
            return

        if not isinstance(type_annotation, nodes.Subscript):
            return

        if (
            isinstance(type_annotation.value, nodes.Attribute)
            and isinstance(type_annotation.value.expr, nodes.Name)
            and type_annotation.value.expr.name == TYPING_MODULE
        ):
            self._type_annotation_names.append(TYPING_MODULE)
            return

        self._type_annotation_names.extend(
            annotation.name for annotation in type_annotation.nodes_of_class(nodes.Name)
        )

    def _store_type_annotation_names(
        self, node: nodes.For | nodes.Assign | nodes.With
    ) -> None:
        type_annotation = node.type_annotation
        if not type_annotation:
            return
        self._store_type_annotation_node(node.type_annotation)

    def _check_self_cls_assign(self, node: nodes.Assign) -> None:
        """Check that self/cls don't get assigned."""
        assign_names: set[str | None] = set()
        for target in node.targets:
            if isinstance(target, nodes.AssignName):
                assign_names.add(target.name)
            elif isinstance(target, nodes.Tuple):
                assign_names.update(
                    elt.name for elt in target.elts if isinstance(elt, nodes.AssignName)
                )
        scope = node.scope()
        nonlocals_with_same_name = node.scope().parent and any(
            child for child in scope.body if isinstance(child, nodes.Nonlocal)
        )
        if nonlocals_with_same_name:
            scope = node.scope().parent.scope()

        if not (
            isinstance(scope, nodes.FunctionDef)
            and scope.is_method()
            and "builtins.staticmethod" not in scope.decoratornames()
        ):
            return
        argument_names = scope.argnames()
        if not argument_names:
            return
        self_cls_name = argument_names[0]
        if self_cls_name in assign_names:
            self.add_message("self-cls-assignment", node=node, args=(self_cls_name,))

    def _check_unpacking(
        self, inferred: InferenceResult, node: nodes.Assign, targets: list[nodes.NodeNG]
    ) -> None:
        """Check for unbalanced tuple unpacking
        and unpacking non sequences.
        """
        if utils.is_inside_abstract_class(node):
            return
        if utils.is_comprehension(node):
            return
        if isinstance(inferred, util.UninferableBase):
            return
        if (
            isinstance(inferred.parent, nodes.Arguments)
            and isinstance(node.value, nodes.Name)
            and node.value.name == inferred.parent.vararg
        ):
            # Variable-length argument, we can't determine the length.
            return

        # Attempt to check unpacking is properly balanced
        values = self._nodes_to_unpack(inferred)
        details = _get_unpacking_extra_info(node, inferred)

        if values is not None:
            if len(targets) != len(values):
                self._report_unbalanced_unpacking(
                    node, inferred, targets, len(values), details
                )
        # attempt to check unpacking may be possible (i.e. RHS is iterable)
        elif not utils.is_iterable(inferred):
            self._report_unpacking_non_sequence(node, details)

    @staticmethod
    def _get_value_length(value_node: nodes.NodeNG) -> int:
        value_subnodes = VariablesChecker._nodes_to_unpack(value_node)
        if value_subnodes is not None:
            return len(value_subnodes)
        if isinstance(value_node, nodes.Const) and isinstance(
            value_node.value, (str, bytes)
        ):
            return len(value_node.value)
        if isinstance(value_node, nodes.Subscript):
            step = value_node.slice.step or 1
            splice_range = value_node.slice.upper.value - value_node.slice.lower.value
            splice_length = int(math.ceil(splice_range / step))
            return splice_length
        return 1

    @staticmethod
    def _nodes_to_unpack(node: nodes.NodeNG) -> list[nodes.NodeNG] | None:
        """Return the list of values of the `Assign` node."""
        if isinstance(node, (nodes.Tuple, nodes.List, nodes.Set, *DICT_TYPES)):
            return node.itered()  # type: ignore[no-any-return]
        if isinstance(node, astroid.Instance) and any(
            ancestor.qname() == "typing.NamedTuple" for ancestor in node.ancestors()
        ):
            return [i for i in node.values() if isinstance(i, nodes.AssignName)]
        return None

    def _report_unbalanced_unpacking(
        self,
        node: nodes.NodeNG,
        inferred: InferenceResult,
        targets: list[nodes.NodeNG],
        values_count: int,
        details: str,
    ) -> None:
        args = (
            details,
            len(targets),
            "" if len(targets) == 1 else "s",
            values_count,
            "" if values_count == 1 else "s",
        )

        symbol = (
            "unbalanced-dict-unpacking"
            if isinstance(inferred, DICT_TYPES)
            else "unbalanced-tuple-unpacking"
        )
        self.add_message(symbol, node=node, args=args, confidence=INFERENCE)

    def _report_unpacking_non_sequence(self, node: nodes.NodeNG, details: str) -> None:
        if details and not details.startswith(" "):
            details = f" {details}"
        self.add_message("unpacking-non-sequence", node=node, args=details)

    def _check_module_attrs(
        self,
        node: _base_nodes.ImportNode,
        module: nodes.Module,
        module_names: list[str],
    ) -> nodes.Module | None:
        """Check that module_names (list of string) are accessible through the
        given module, if the latest access name corresponds to a module, return it.
        """
        while module_names:
            name = module_names.pop(0)
            if name == "__dict__":
                module = None
                break
            try:
                module = module.getattr(name)[0]
                if not isinstance(module, nodes.Module):
                    module = next(module.infer())
                    if not isinstance(module, nodes.Module):
                        return None
            except astroid.NotFoundError:
                # Unable to import `name` from `module`. Since `name` may itself be a
                # module, we first check if it matches the ignored modules.
                if is_module_ignored(f"{module.qname()}.{name}", self._ignored_modules):
                    return None
                self.add_message(
                    "no-name-in-module", args=(name, module.name), node=node
                )
                return None
            except astroid.InferenceError:
                return None
        if module_names:
            modname = module.name if module else "__dict__"
            self.add_message(
                "no-name-in-module", node=node, args=(".".join(module_names), modname)
            )
            return None
        if isinstance(module, nodes.Module):
            return module
        return None

    def _check_all(
        self, node: nodes.Module, not_consumed: dict[str, list[nodes.NodeNG]]
    ) -> None:
        try:
            assigned = next(node.igetattr("__all__"))
        except astroid.InferenceError:
            return
        if isinstance(assigned, util.UninferableBase):
            return
        if assigned.pytype() not in {"builtins.list", "builtins.tuple"}:
            line, col = assigned.tolineno, assigned.col_offset
            self.add_message("invalid-all-format", line=line, col_offset=col, node=node)
            return
        for elt in getattr(assigned, "elts", ()):
            try:
                elt_name = next(elt.infer())
            except astroid.InferenceError:
                continue
            if isinstance(elt_name, util.UninferableBase):
                continue
            if not elt_name.parent:
                continue

            if not isinstance(elt_name, nodes.Const) or not isinstance(
                elt_name.value, str
            ):
                self.add_message("invalid-all-object", args=elt.as_string(), node=elt)
                continue

            elt_name = elt_name.value
            # If elt is in not_consumed, remove it from not_consumed
            if elt_name in not_consumed:
                del not_consumed[elt_name]
                continue

            if elt_name not in node.locals:
                if not node.package:
                    self.add_message(
                        "undefined-all-variable", args=(elt_name,), node=elt
                    )
                else:
                    basename = os.path.splitext(node.file)[0]
                    if os.path.basename(basename) == "__init__":
                        name = node.name + "." + elt_name
                        try:
                            astroid.modutils.file_from_modpath(name.split("."))
                        except ImportError:
                            self.add_message(
                                "undefined-all-variable", args=(elt_name,), node=elt
                            )
                        except SyntaxError:
                            # don't yield a syntax-error warning,
                            # because it will be later yielded
                            # when the file will be checked
                            pass

    def _check_globals(self, not_consumed: dict[str, nodes.NodeNG]) -> None:
        if self._allow_global_unused_variables:
            return
        for name, node_lst in not_consumed.items():
            for node in node_lst:
                if in_type_checking_block(node):
                    continue
                self.add_message("unused-variable", args=(name,), node=node)

    # pylint: disable = too-many-branches
    def _check_imports(self, not_consumed: dict[str, list[nodes.NodeNG]]) -> None:
        local_names = _fix_dot_imports(not_consumed)
        checked = set()
        unused_wildcard_imports: defaultdict[
            tuple[str, nodes.ImportFrom], list[str]
        ] = collections.defaultdict(list)
        for name, stmt in local_names:
            for imports in stmt.names:
                real_name = imported_name = imports[0]
                if imported_name == "*":
                    real_name = name
                as_name = imports[1]
                if real_name in checked:
                    continue
                if name not in (real_name, as_name):
                    continue
                checked.add(real_name)

                is_type_annotation_import = (
                    imported_name in self._type_annotation_names
                    or as_name in self._type_annotation_names
                )

                is_dummy_import = (
                    as_name
                    and self.linter.config.dummy_variables_rgx
                    and self.linter.config.dummy_variables_rgx.match(as_name)
                )

                if isinstance(stmt, nodes.Import) or (
                    isinstance(stmt, nodes.ImportFrom) and not stmt.modname
                ):
                    if isinstance(stmt, nodes.ImportFrom) and SPECIAL_OBJ.search(
                        imported_name
                    ):
                        # Filter special objects (__doc__, __all__) etc.,
                        # because they can be imported for exporting.
                        continue

                    if is_type_annotation_import or is_dummy_import:
                        # Most likely a typing import if it wasn't used so far.
                        # Also filter dummy variables.
                        continue

                    if as_name is None:
                        msg = f"import {imported_name}"
                    else:
                        msg = f"{imported_name} imported as {as_name}"
                    if not in_type_checking_block(stmt):
                        self.add_message("unused-import", args=msg, node=stmt)
                elif isinstance(stmt, nodes.ImportFrom) and stmt.modname != FUTURE:
                    if SPECIAL_OBJ.search(imported_name):
                        # Filter special objects (__doc__, __all__) etc.,
                        # because they can be imported for exporting.
                        continue

                    if _is_from_future_import(stmt, name):
                        # Check if the name is in fact loaded from a
                        # __future__ import in another module.
                        continue

                    if is_type_annotation_import or is_dummy_import:
                        # Most likely a typing import if it wasn't used so far.
                        # Also filter dummy variables.
                        continue

                    if imported_name == "*":
                        unused_wildcard_imports[(stmt.modname, stmt)].append(name)
                    else:
                        if as_name is None:
                            msg = f"{imported_name} imported from {stmt.modname}"
                        else:
                            msg = f"{imported_name} imported from {stmt.modname} as {as_name}"
                        if not in_type_checking_block(stmt):
                            self.add_message("unused-import", args=msg, node=stmt)

        # Construct string for unused-wildcard-import message
        for module, unused_list in unused_wildcard_imports.items():
            if len(unused_list) == 1:
                arg_string = unused_list[0]
            else:
                arg_string = (
                    f"{', '.join(i for i in unused_list[:-1])} and {unused_list[-1]}"
                )
            self.add_message(
                "unused-wildcard-import", args=(arg_string, module[0]), node=module[1]
            )
        del self._to_consume

    def _check_metaclasses(self, node: nodes.Module | nodes.FunctionDef) -> None:
        """Update consumption analysis for metaclasses."""
        consumed: list[tuple[dict[str, list[nodes.NodeNG]], str]] = []

        for child_node in node.get_children():
            if isinstance(child_node, nodes.ClassDef):
                consumed.extend(self._check_classdef_metaclasses(child_node, node))

        # Pop the consumed items, in order to avoid having
        # unused-import and unused-variable false positives
        for scope_locals, name in consumed:
            scope_locals.pop(name, None)

    def _check_classdef_metaclasses(
        self, klass: nodes.ClassDef, parent_node: nodes.Module | nodes.FunctionDef
    ) -> list[tuple[dict[str, list[nodes.NodeNG]], str]]:
        if not klass._metaclass:
            # Skip if this class doesn't use explicitly a metaclass, but inherits it from ancestors
            return []

        consumed: list[tuple[dict[str, list[nodes.NodeNG]], str]] = []
        metaclass = klass.metaclass()
        name = ""
        if isinstance(klass._metaclass, nodes.Name):
            name = klass._metaclass.name
        elif isinstance(klass._metaclass, nodes.Attribute) and klass._metaclass.expr:
            attr = klass._metaclass.expr
            while not isinstance(attr, nodes.Name):
                attr = attr.expr
            name = attr.name
        elif isinstance(klass._metaclass, nodes.Call) and isinstance(
            klass._metaclass.func, nodes.Name
        ):
            name = klass._metaclass.func.name
        elif metaclass:
            name = metaclass.root().name

        found = False
        name = METACLASS_NAME_TRANSFORMS.get(name, name)
        if name:
            # check enclosing scopes starting from most local
            for scope_locals, _, _, _ in self._to_consume[::-1]:
                found_nodes = scope_locals.get(name, [])
                for found_node in found_nodes:
                    if found_node.lineno <= klass.lineno:
                        consumed.append((scope_locals, name))
                        found = True
                        break
            # Check parent scope
            nodes_in_parent_scope = parent_node.locals.get(name, [])
            for found_node_parent in nodes_in_parent_scope:
                if found_node_parent.lineno <= klass.lineno:
                    found = True
                    break
        if (
            not found
            and not metaclass
            and not (
                name in nodes.Module.scope_attrs
                or utils.is_builtin(name)
                or name in self.linter.config.additional_builtins
            )
        ):
            self.add_message("undefined-variable", node=klass, args=(name,))

        return consumed

    def visit_subscript(self, node: nodes.Subscript) -> None:
        inferred_slice = utils.safe_infer(node.slice)

        self._check_potential_index_error(node, inferred_slice)

    def _inferred_iterable_length(self, iterable: nodes.Tuple | nodes.List) -> int:
        length = 0
        for elt in iterable.elts:
            if not isinstance(elt, nodes.Starred):
                length += 1
                continue
            unpacked = utils.safe_infer(elt.value)
            if isinstance(unpacked, nodes.BaseContainer):
                length += len(unpacked.elts)
            else:
                length += 1
        return length

    def _check_potential_index_error(
        self, node: nodes.Subscript, inferred_slice: nodes.NodeNG | None
    ) -> None:
        """Check for the potential-index-error message."""
        # Currently we only check simple slices of a single integer
        if not isinstance(inferred_slice, nodes.Const) or not isinstance(
            inferred_slice.value, int
        ):
            return

        # If the node.value is a Tuple or List without inference it is defined in place
        if isinstance(node.value, (nodes.Tuple, nodes.List)):
            # Add 1 because iterables are 0-indexed
            if self._inferred_iterable_length(node.value) < inferred_slice.value + 1:
                self.add_message(
                    "potential-index-error", node=node, confidence=INFERENCE
                )
            return

    @utils.only_required_for_messages(
        "unused-import",
        "unused-variable",
    )
    def visit_const(self, node: nodes.Const) -> None:
        """Take note of names that appear inside string literal type annotations
        unless the string is a parameter to `typing.Literal` or `typing.Annotation`.
        """
        if node.pytype() != "builtins.str":
            return
        if not utils.is_node_in_type_annotation_context(node):
            return

        # Check if parent's or grandparent's first child is typing.Literal
        parent = node.parent
        if isinstance(parent, nodes.Tuple):
            parent = parent.parent
        if isinstance(parent, nodes.Subscript):
            origin = next(parent.get_children(), None)
            if origin is not None and utils.is_typing_member(
                origin, ("Annotated", "Literal")
            ):
                return

        try:
            annotation = extract_node(node.value)
            self._store_type_annotation_node(annotation)
        except ValueError:
            # e.g. node.value is white space
            pass
        except astroid.AstroidSyntaxError:
            # e.g. "?" or ":" in typing.Literal["?", ":"]
            pass


def register(linter: PyLinter) -> None:
    linter.register_checker(VariablesChecker(linter))
