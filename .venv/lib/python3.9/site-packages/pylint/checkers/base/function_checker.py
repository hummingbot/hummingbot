# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/pylint-dev/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/pylint/blob/main/CONTRIBUTORS.txt

"""Function checker for Python code."""

from __future__ import annotations

from itertools import chain

from astroid import nodes

from pylint.checkers import utils
from pylint.checkers.base.basic_checker import _BasicChecker


class FunctionChecker(_BasicChecker):
    """Check if a function definition handles possible side effects."""

    msgs = {
        "W0135": (
            "The context used in function %r will not be exited.",
            "contextmanager-generator-missing-cleanup",
            "Used when a contextmanager is used inside a generator function"
            " and the cleanup is not handled.",
        )
    }

    @utils.only_required_for_messages("contextmanager-generator-missing-cleanup")
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        self._check_contextmanager_generator_missing_cleanup(node)

    @utils.only_required_for_messages("contextmanager-generator-missing-cleanup")
    def visit_asyncfunctiondef(self, node: nodes.AsyncFunctionDef) -> None:
        self._check_contextmanager_generator_missing_cleanup(node)

    def _check_contextmanager_generator_missing_cleanup(
        self, node: nodes.FunctionDef
    ) -> None:
        """Check a FunctionDef to find if it is a generator
        that uses a contextmanager internally.

        If it is, check if the contextmanager is properly cleaned up. Otherwise, add message.

        :param node: FunctionDef node to check
        :type node: nodes.FunctionDef
        """
        # if function does not use a Yield statement, it can't be a generator
        with_nodes = list(node.nodes_of_class(nodes.With))
        if not with_nodes:
            return
        # check for Yield inside the With statement
        yield_nodes = list(
            chain.from_iterable(
                with_node.nodes_of_class(nodes.Yield) for with_node in with_nodes
            )
        )
        if not yield_nodes:
            return

        # infer the call that yields a value, and check if it is a contextmanager
        for with_node in with_nodes:
            for call, held in with_node.items:
                if held is None:
                    # if we discard the value, then we can skip checking it
                    continue

                # safe infer is a generator
                inferred_node = getattr(utils.safe_infer(call), "parent", None)
                if not isinstance(inferred_node, nodes.FunctionDef):
                    continue
                if self._node_fails_contextmanager_cleanup(inferred_node, yield_nodes):
                    self.add_message(
                        "contextmanager-generator-missing-cleanup",
                        node=with_node,
                        args=(node.name,),
                    )

    @staticmethod
    def _node_fails_contextmanager_cleanup(
        node: nodes.FunctionDef, yield_nodes: list[nodes.Yield]
    ) -> bool:
        """Check if a node fails contextmanager cleanup.

        Current checks for a contextmanager:
            - only if the context manager yields a non-constant value
            - only if the context manager lacks a finally, or does not catch GeneratorExit
            - only if some statement follows the yield, some manually cleanup happens

        :param node: Node to check
        :type node: nodes.FunctionDef
        :return: True if fails, False otherwise
        :param yield_nodes: List of Yield nodes in the function body
        :type yield_nodes: list[nodes.Yield]
        :rtype: bool
        """

        def check_handles_generator_exceptions(try_node: nodes.Try) -> bool:
            # needs to handle either GeneratorExit, Exception, or bare except
            for handler in try_node.handlers:
                if handler.type is None:
                    # handles all exceptions (bare except)
                    return True
                inferred = utils.safe_infer(handler.type)
                if inferred and inferred.qname() in {
                    "builtins.GeneratorExit",
                    "builtins.Exception",
                }:
                    return True
            return False

        # if context manager yields a non-constant value, then continue checking
        if any(
            yield_node.value is None or isinstance(yield_node.value, nodes.Const)
            for yield_node in yield_nodes
        ):
            return False

        # Check if yield expression is last statement
        yield_nodes = list(node.nodes_of_class(nodes.Yield))
        if len(yield_nodes) == 1:
            n = yield_nodes[0].parent
            while n is not node:
                if n.next_sibling() is not None:
                    break
                n = n.parent
            else:
                # No next statement found
                return False

        # if function body has multiple Try, filter down to the ones that have a yield node
        try_with_yield_nodes = [
            try_node
            for try_node in node.nodes_of_class(nodes.Try)
            if any(try_node.nodes_of_class(nodes.Yield))
        ]
        if not try_with_yield_nodes:
            # no try blocks at all, so checks after this line do not apply
            return True
        # if the contextmanager has a finally block, then it is fine
        if all(try_node.finalbody for try_node in try_with_yield_nodes):
            return False
        # if the contextmanager catches GeneratorExit, then it is fine
        if all(
            check_handles_generator_exceptions(try_node)
            for try_node in try_with_yield_nodes
        ):
            return False
        return True
