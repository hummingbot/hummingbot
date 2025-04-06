# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""Check for use of nested min/max functions."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from astroid import nodes, objects
from astroid.const import Context

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages, safe_infer
from pylint.interfaces import INFERENCE

if TYPE_CHECKING:
    from pylint.lint import PyLinter

DICT_TYPES = (
    objects.DictValues,
    objects.DictKeys,
    objects.DictItems,
    nodes.node_classes.Dict,
)


class NestedMinMaxChecker(BaseChecker):
    """Multiple nested min/max calls on the same line will raise multiple messages.

    This behaviour is intended as it would slow down the checker to check
    for nested call with minimal benefits.
    """

    FUNC_NAMES = ("builtins.min", "builtins.max")

    name = "nested_min_max"
    msgs = {
        "W3301": (
            "Do not use nested call of '%s'; it's possible to do '%s' instead",
            "nested-min-max",
            "Nested calls ``min(1, min(2, 3))`` can be rewritten as ``min(1, 2, 3)``.",
        )
    }

    @classmethod
    def is_min_max_call(cls, node: nodes.NodeNG) -> bool:
        if not isinstance(node, nodes.Call):
            return False

        inferred = safe_infer(node.func)
        return (
            isinstance(inferred, nodes.FunctionDef)
            and inferred.qname() in cls.FUNC_NAMES
        )

    @classmethod
    def get_redundant_calls(cls, node: nodes.Call) -> list[nodes.Call]:
        return [
            arg
            for arg in node.args
            if (
                cls.is_min_max_call(arg)
                and arg.func.name == node.func.name
                # Nesting is useful for finding the maximum in a matrix.
                # Allow: max(max([[1, 2, 3], [4, 5, 6]]))
                # Meaning, redundant call only if parent max call has more than 1 arg.
                and len(arg.parent.args) > 1
            )
        ]

    @only_required_for_messages("nested-min-max")
    def visit_call(self, node: nodes.Call) -> None:
        if not self.is_min_max_call(node):
            return

        redundant_calls = self.get_redundant_calls(node)
        if not redundant_calls:
            return

        fixed_node = copy.copy(node)
        while len(redundant_calls) > 0:
            for i, arg in enumerate(fixed_node.args):
                # Exclude any calls with generator expressions as there is no
                # clear better suggestion for them.
                if isinstance(arg, nodes.Call) and any(
                    isinstance(a, nodes.GeneratorExp) for a in arg.args
                ):
                    return

                if arg in redundant_calls:
                    fixed_node.args = (
                        fixed_node.args[:i] + arg.args + fixed_node.args[i + 1 :]
                    )
                    break

            redundant_calls = self.get_redundant_calls(fixed_node)

        for idx, arg in enumerate(fixed_node.args):
            if not isinstance(arg, nodes.Const):
                if self._is_splattable_expression(arg):
                    splat_node = nodes.Starred(
                        ctx=Context.Load,
                        lineno=arg.lineno,
                        col_offset=0,
                        parent=nodes.NodeNG(
                            lineno=None,
                            col_offset=None,
                            end_lineno=None,
                            end_col_offset=None,
                            parent=None,
                        ),
                        end_lineno=0,
                        end_col_offset=0,
                    )
                    splat_node.value = arg
                    fixed_node.args = (
                        fixed_node.args[:idx]
                        + [splat_node]
                        + fixed_node.args[idx + 1 : idx]
                    )

        self.add_message(
            "nested-min-max",
            node=node,
            args=(node.func.name, fixed_node.as_string()),
            confidence=INFERENCE,
        )

    def _is_splattable_expression(self, arg: nodes.NodeNG) -> bool:
        """Returns true if expression under min/max could be converted to splat
        expression.
        """
        # Support sequence addition (operator __add__)
        if isinstance(arg, nodes.BinOp) and arg.op == "+":
            return self._is_splattable_expression(
                arg.left
            ) and self._is_splattable_expression(arg.right)
        # Support dict merge (operator __or__)
        if isinstance(arg, nodes.BinOp) and arg.op == "|":
            return self._is_splattable_expression(
                arg.left
            ) and self._is_splattable_expression(arg.right)

        inferred = safe_infer(arg)
        if inferred and inferred.pytype() in {"builtins.list", "builtins.tuple"}:
            return True
        if isinstance(
            inferred or arg,
            (
                nodes.List,
                nodes.Tuple,
                nodes.Set,
                nodes.ListComp,
                nodes.DictComp,
                *DICT_TYPES,
            ),
        ):
            return True

        return False


def register(linter: PyLinter) -> None:
    linter.register_checker(NestedMinMaxChecker(linter))
