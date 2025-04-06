# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""Dataclass checkers for Python code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes
from astroid.brain.brain_dataclasses import DATACLASS_MODULES

from pylint.checkers import BaseChecker, utils
from pylint.interfaces import INFERENCE

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def _is_dataclasses_module(node: nodes.Module) -> bool:
    """Utility function to check if node is from dataclasses_module."""
    return node.name in DATACLASS_MODULES


def _check_name_or_attrname_eq_to(
    node: nodes.Name | nodes.Attribute, check_with: str
) -> bool:
    """Utility function to check either a Name/Attribute node's name/attrname with a
    given string.
    """
    if isinstance(node, nodes.Name):
        return str(node.name) == check_with
    return str(node.attrname) == check_with


class DataclassChecker(BaseChecker):
    """Checker that detects invalid or problematic usage in dataclasses.

    Checks for
    * invalid-field-call
    """

    name = "dataclass"
    msgs = {
        "E3701": (
            "Invalid usage of field(), %s",
            "invalid-field-call",
            "The dataclasses.field() specifier should only be used as the value of "
            "an assignment within a dataclass, or within the make_dataclass() function.",
        ),
    }

    @utils.only_required_for_messages("invalid-field-call")
    def visit_call(self, node: nodes.Call) -> None:
        self._check_invalid_field_call(node)

    def _check_invalid_field_call(self, node: nodes.Call) -> None:
        """Checks for correct usage of the dataclasses.field() specifier in
        dataclasses or within the make_dataclass() function.

        Emits message
        when field() is detected to be used outside a class decorated with
        @dataclass decorator and outside make_dataclass() function, or when it
        is used improperly within a dataclass.
        """
        if not isinstance(node.func, (nodes.Name, nodes.Attribute)):
            return
        if not _check_name_or_attrname_eq_to(node.func, "field"):
            return
        inferred_func = utils.safe_infer(node.func)
        if not (
            isinstance(inferred_func, nodes.FunctionDef)
            and _is_dataclasses_module(inferred_func.root())
        ):
            return
        scope_node = node.parent
        while scope_node and not isinstance(scope_node, (nodes.ClassDef, nodes.Call)):
            scope_node = scope_node.parent

        if isinstance(scope_node, nodes.Call):
            self._check_invalid_field_call_within_call(node, scope_node)
            return

        if not scope_node or not scope_node.is_dataclass:
            self.add_message(
                "invalid-field-call",
                node=node,
                args=(
                    "it should be used within a dataclass or the make_dataclass() function.",
                ),
                confidence=INFERENCE,
            )
            return

        if not (isinstance(node.parent, nodes.AnnAssign) and node == node.parent.value):
            self.add_message(
                "invalid-field-call",
                node=node,
                args=("it should be the value of an assignment within a dataclass.",),
                confidence=INFERENCE,
            )

    def _check_invalid_field_call_within_call(
        self, node: nodes.Call, scope_node: nodes.Call
    ) -> None:
        """Checks for special case where calling field is valid as an argument of the
        make_dataclass() function.
        """
        inferred_func = utils.safe_infer(scope_node.func)
        if (
            isinstance(scope_node.func, (nodes.Name, nodes.AssignName))
            and scope_node.func.name == "make_dataclass"
            and isinstance(inferred_func, nodes.FunctionDef)
            and _is_dataclasses_module(inferred_func.root())
        ):
            return
        self.add_message(
            "invalid-field-call",
            node=node,
            args=(
                "it should be used within a dataclass or the make_dataclass() function.",
            ),
            confidence=INFERENCE,
        )


def register(linter: PyLinter) -> None:
    linter.register_checker(DataclassChecker(linter))
