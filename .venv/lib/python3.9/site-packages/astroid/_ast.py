# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import ast
from typing import NamedTuple

from astroid.const import Context


class FunctionType(NamedTuple):
    argtypes: list[ast.expr]
    returns: ast.expr


class ParserModule(NamedTuple):
    unary_op_classes: dict[type[ast.unaryop], str]
    cmp_op_classes: dict[type[ast.cmpop], str]
    bool_op_classes: dict[type[ast.boolop], str]
    bin_op_classes: dict[type[ast.operator], str]
    context_classes: dict[type[ast.expr_context], Context]

    def parse(
        self, string: str, type_comments: bool = True, filename: str | None = None
    ) -> ast.Module:
        if filename:
            return ast.parse(string, filename=filename, type_comments=type_comments)
        return ast.parse(string, type_comments=type_comments)


def parse_function_type_comment(type_comment: str) -> FunctionType | None:
    """Given a correct type comment, obtain a FunctionType object."""
    func_type = ast.parse(type_comment, "<type_comment>", "func_type")  # type: ignore[attr-defined]
    return FunctionType(argtypes=func_type.argtypes, returns=func_type.returns)


def get_parser_module(type_comments: bool = True) -> ParserModule:
    unary_op_classes = _unary_operators_from_module()
    cmp_op_classes = _compare_operators_from_module()
    bool_op_classes = _bool_operators_from_module()
    bin_op_classes = _binary_operators_from_module()
    context_classes = _contexts_from_module()

    return ParserModule(
        unary_op_classes,
        cmp_op_classes,
        bool_op_classes,
        bin_op_classes,
        context_classes,
    )


def _unary_operators_from_module() -> dict[type[ast.unaryop], str]:
    return {ast.UAdd: "+", ast.USub: "-", ast.Not: "not", ast.Invert: "~"}


def _binary_operators_from_module() -> dict[type[ast.operator], str]:
    return {
        ast.Add: "+",
        ast.BitAnd: "&",
        ast.BitOr: "|",
        ast.BitXor: "^",
        ast.Div: "/",
        ast.FloorDiv: "//",
        ast.MatMult: "@",
        ast.Mod: "%",
        ast.Mult: "*",
        ast.Pow: "**",
        ast.Sub: "-",
        ast.LShift: "<<",
        ast.RShift: ">>",
    }


def _bool_operators_from_module() -> dict[type[ast.boolop], str]:
    return {ast.And: "and", ast.Or: "or"}


def _compare_operators_from_module() -> dict[type[ast.cmpop], str]:
    return {
        ast.Eq: "==",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.In: "in",
        ast.Is: "is",
        ast.IsNot: "is not",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.NotEq: "!=",
        ast.NotIn: "not in",
    }


def _contexts_from_module() -> dict[type[ast.expr_context], Context]:
    return {
        ast.Load: Context.Load,
        ast.Store: Context.Store,
        ast.Del: Context.Del,
        ast.Param: Context.Store,
    }
