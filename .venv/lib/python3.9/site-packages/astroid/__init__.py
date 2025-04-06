# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Python Abstract Syntax Tree New Generation.

The aim of this module is to provide a common base representation of
python source code for projects such as pychecker, pyreverse,
pylint... Well, actually the development of this library is essentially
governed by pylint's needs.

It mimics the class defined in the python's _ast module with some
additional methods and attributes. New nodes instances are not fully
compatible with python's _ast.

Instance attributes are added by a
builder object, which can either generate extended ast (let's call
them astroid ;) by visiting an existent ast tree or by inspecting living
object.

Main modules are:

* nodes and scoped_nodes for more information about methods and
  attributes added to different node classes

* the manager contains a high level object to get astroid trees from
  source files and living objects. It maintains a cache of previously
  constructed tree for quick access

* builder contains the class responsible to build astroid trees
"""

import functools
import tokenize

# isort: off
# We have an isort: off on 'astroid.nodes' because of a circular import.
from astroid.nodes import node_classes, scoped_nodes

# isort: on

from astroid import raw_building
from astroid.__pkginfo__ import __version__, version
from astroid.bases import BaseInstance, BoundMethod, Instance, UnboundMethod
from astroid.brain.helpers import register_module_extender
from astroid.builder import extract_node, parse
from astroid.const import PY310_PLUS, Context
from astroid.exceptions import (
    AstroidBuildingError,
    AstroidError,
    AstroidImportError,
    AstroidIndexError,
    AstroidSyntaxError,
    AstroidTypeError,
    AstroidValueError,
    AttributeInferenceError,
    DuplicateBasesError,
    InconsistentMroError,
    InferenceError,
    InferenceOverwriteError,
    MroError,
    NameInferenceError,
    NoDefault,
    NotFoundError,
    ParentMissingError,
    ResolveError,
    StatementMissing,
    SuperArgumentTypeError,
    SuperError,
    TooManyLevelsError,
    UnresolvableName,
    UseInferenceDefault,
)
from astroid.inference_tip import _inference_tip_cached, inference_tip
from astroid.objects import ExceptionInstance

# isort: off
# It's impossible to import from astroid.nodes with a wildcard, because
# there is a cyclic import that prevent creating an __all__ in astroid/nodes
# and we need astroid/scoped_nodes and astroid/node_classes to work. So
# importing with a wildcard would clash with astroid/nodes/scoped_nodes
# and astroid/nodes/node_classes.
from astroid.astroid_manager import MANAGER
from astroid.nodes import (
    CONST_CLS,
    AnnAssign,
    Arguments,
    Assert,
    Assign,
    AssignAttr,
    AssignName,
    AsyncFor,
    AsyncFunctionDef,
    AsyncWith,
    Attribute,
    AugAssign,
    Await,
    BinOp,
    BoolOp,
    Break,
    Call,
    ClassDef,
    Compare,
    Comprehension,
    ComprehensionScope,
    Const,
    Continue,
    Decorators,
    DelAttr,
    Delete,
    DelName,
    Dict,
    DictComp,
    DictUnpack,
    EmptyNode,
    EvaluatedObject,
    ExceptHandler,
    Expr,
    For,
    FormattedValue,
    FunctionDef,
    GeneratorExp,
    Global,
    If,
    IfExp,
    Import,
    ImportFrom,
    JoinedStr,
    Keyword,
    Lambda,
    List,
    ListComp,
    Match,
    MatchAs,
    MatchCase,
    MatchClass,
    MatchMapping,
    MatchOr,
    MatchSequence,
    MatchSingleton,
    MatchStar,
    MatchValue,
    Module,
    Name,
    NamedExpr,
    NodeNG,
    Nonlocal,
    ParamSpec,
    Pass,
    Raise,
    Return,
    Set,
    SetComp,
    Slice,
    Starred,
    Subscript,
    Try,
    TryStar,
    Tuple,
    TypeAlias,
    TypeVar,
    TypeVarTuple,
    UnaryOp,
    Unknown,
    While,
    With,
    Yield,
    YieldFrom,
    are_exclusive,
    builtin_lookup,
    unpack_infer,
    function_to_method,
)

# isort: on

from astroid.util import Uninferable

# Performance hack for tokenize. See https://bugs.python.org/issue43014
# Adapted from https://github.com/PyCQA/pycodestyle/pull/993
if (
    not PY310_PLUS
    and callable(getattr(tokenize, "_compile", None))
    and getattr(tokenize._compile, "__wrapped__", None) is None  # type: ignore[attr-defined]
):
    tokenize._compile = functools.lru_cache(tokenize._compile)  # type: ignore[attr-defined]
