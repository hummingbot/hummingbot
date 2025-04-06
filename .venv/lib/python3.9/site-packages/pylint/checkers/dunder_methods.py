# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import Instance, nodes
from astroid.util import UninferableBase

from pylint.checkers import BaseChecker
from pylint.checkers.utils import safe_infer
from pylint.constants import DUNDER_METHODS, UNNECESSARY_DUNDER_CALL_LAMBDA_EXCEPTIONS
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class DunderCallChecker(BaseChecker):
    """Check for unnecessary dunder method calls.

    Docs: https://docs.python.org/3/reference/datamodel.html#basic-customization
    We exclude names in list pylint.constants.EXTRA_DUNDER_METHODS such as
    __index__ (see https://github.com/pylint-dev/pylint/issues/6795)
    since these either have no alternative method of being called or
    have a genuine use case for being called manually.

    Additionally, we exclude classes that are not instantiated since these
    might be used to access the dunder methods of a base class of an instance.
    We also exclude dunder method calls on super() since
    these can't be written in an alternative manner.
    """

    name = "unnecessary-dunder-call"
    msgs = {
        "C2801": (
            "Unnecessarily calls dunder method %s. %s.",
            "unnecessary-dunder-call",
            "Used when a dunder method is manually called instead "
            "of using the corresponding function/method/operator.",
        ),
    }
    options = ()

    def open(self) -> None:
        self._dunder_methods: dict[str, str] = {}
        for since_vers, dunder_methods in DUNDER_METHODS.items():
            if since_vers <= self.linter.config.py_version:
                self._dunder_methods.update(dunder_methods)

    @staticmethod
    def within_dunder_or_lambda_def(node: nodes.NodeNG) -> bool:
        """Check if dunder method call is within a dunder method definition."""
        parent = node.parent
        while parent is not None:
            if (
                isinstance(parent, nodes.FunctionDef)
                and parent.name.startswith("__")
                and parent.name.endswith("__")
                or DunderCallChecker.is_lambda_rule_exception(parent, node)
            ):
                return True
            parent = parent.parent
        return False

    @staticmethod
    def is_lambda_rule_exception(ancestor: nodes.NodeNG, node: nodes.NodeNG) -> bool:
        return (
            isinstance(ancestor, nodes.Lambda)
            and node.func.attrname in UNNECESSARY_DUNDER_CALL_LAMBDA_EXCEPTIONS
        )

    def visit_call(self, node: nodes.Call) -> None:
        """Check if method being called is an unnecessary dunder method."""
        if (
            isinstance(node.func, nodes.Attribute)
            and node.func.attrname in self._dunder_methods
            and not self.within_dunder_or_lambda_def(node)
            and not (
                isinstance(node.func.expr, nodes.Call)
                and isinstance(node.func.expr.func, nodes.Name)
                and node.func.expr.func.name == "super"
            )
        ):
            inf_expr = safe_infer(node.func.expr)
            if not (
                inf_expr is None or isinstance(inf_expr, (Instance, UninferableBase))
            ):
                # Skip dunder calls to non instantiated classes.
                return

            self.add_message(
                "unnecessary-dunder-call",
                node=node,
                args=(node.func.attrname, self._dunder_methods[node.func.attrname]),
                confidence=HIGH,
            )


def register(linter: PyLinter) -> None:
    linter.register_checker(DunderCallChecker(linter))
