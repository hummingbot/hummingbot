"""
 Copyright (C) 2021 Gianni Tedesco.
 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at http://mozilla.org/MPL/2.0/.

 This file is a plugin for mypy that adds support for dataclassy.
"""
from typing import (
    Generator, Optional, Iterable, Callable, NamedTuple, Mapping, Type, Tuple,
    List, TypeVar,
)
from operator import or_
from functools import reduce

from mypy.plugin import (
    SemanticAnalyzerPluginInterface, Plugin, ClassDefContext,
)
from mypy.nodes import (
    ARG_POS, ARG_OPT, MDEF, JsonDict, TypeInfo, Argument, AssignmentStmt,
    PlaceholderNode, SymbolTableNode, TempNode, NameExpr, Var,
)
from mypy.plugins.common import (
    add_method, _get_decorator_bool_argument, deserialize_and_fixup_type,
)
from mypy.types import NoneType, get_proper_type

__all__ = (
    'DataclassyPlugin',
    'plugin',
)


T = TypeVar('T')


def partition(pred: Callable[[T], bool],
              it: Iterable[T],
              ) -> Tuple[List[T], List[T]]:
    ts: List[T] = []
    fs: List[T] = []
    t = ts.append
    f = fs.append
    for item in it:
        (t if pred(item) else f)(item)
    return fs, ts


ClassDefCallback = Optional[Callable[[ClassDefContext], None]]
_meta_key = 'dataclassy'


class ClassyArgs(NamedTuple):
    init: bool = True
    repr: bool = True
    eq: bool = True
    iter: bool = False
    frozen: bool = False
    kwargs: bool = False
    slots: bool = False
    order: bool = False
    unsafe_hash: bool = True
    hide_internals: bool = True


class ClassyField(NamedTuple):
    name: str
    type: Type
    has_default: bool = False

    @property
    def var(self):
        return Var(self.name, self.type)

    @property
    def metharg(self):
        kind = ARG_POS if not self.has_default else ARG_OPT
        return Argument(
            variable=self.var,
            type_annotation=self.type,
            initializer=None,
            kind=kind,
        )

    def serialize(self) -> JsonDict:
        return {
            'name': self.name,
            'type': self.type.serialize(),
            'has_default': self.has_default,
        }

    @classmethod
    def deserialize(cls,
                    info: TypeInfo,
                    data: JsonDict,
                    api: SemanticAnalyzerPluginInterface,
                    ) -> 'ClassyField':
        return cls(
            name=data['name'],
            type=deserialize_and_fixup_type(data['type'], api),
            has_default=data['has_default'],
        )


class ClassyInfo(NamedTuple):
    fields: Mapping[str, ClassyField]
    args: ClassyArgs
    is_root: bool = False

    def serialize(self) -> JsonDict:
        return {
            'fields': {name: f.serialize() for name, f in self.fields.items()},
            'args': self.args._asdict(),
            'is_root': self.is_root,
        }

    @classmethod
    def deserialize(cls,
                    info: TypeInfo,
                    data: JsonDict,
                    api: SemanticAnalyzerPluginInterface,
                    ) -> 'ClassyInfo':
        return cls(
            fields={k: ClassyField.deserialize(info, v, api)
                    for k, v in data['fields'].items()},
            args=ClassyArgs(**data['args']),
            is_root=data['is_root'],
        )


def _gather_attributes(cls) -> Generator[ClassyField, None, None]:
    info = cls.info

    defaults: List[ClassyField] = []

    for s in cls.defs.body:
        if not (isinstance(s, AssignmentStmt) and s.new_syntax):
            continue

        lhs = s.lvalues[0]
        if not isinstance(lhs, NameExpr):
            continue

        name = lhs.name

        sym = info.names.get(name)
        if sym is None:
            continue

        node = sym.node
        if isinstance(node, PlaceholderNode):
            return None

        assert isinstance(node, Var)

        if node.is_classvar:
            continue

        node_type = get_proper_type(node.type)

        rexpr = s.rvalue
        if not isinstance(rexpr, TempNode):
            # print('DEFAULT:', name, node_type, type(rexpr))
            defaults.append(ClassyField(name, sym.type, True))
            continue

        yield ClassyField(name, sym.type)

    yield from defaults


def _munge_dataclassy(ctx: ClassDefContext,
                      classy: ClassyInfo,
                      ) -> None:
    cls = ctx.cls
    info = cls.info
    fields = classy.fields

    # We store the dataclassy info here so that we can figure out later which
    # classes are dataclassy classes
    info.metadata[_meta_key] = classy.serialize()

    # Add the __init__ method if we have to
    if classy.args.init:
        add_method(
            ctx,
            '__init__',
            args=[f.metharg for f in fields.values()],
            return_type=NoneType(),
        )

    # Add the fields
    for field in fields.values():
        var = field.var
        var.info = info
        var.is_property = True
        var._fullname = f'{info.fullname}.{var.name}'
        info.names[field.name] = SymbolTableNode(MDEF, var)


def _make_dataclassy(ctx: ClassDefContext) -> None:
    """
    This class has the @dataclassy decorator. It is going to be the root-class
    of a dataclassy hierarchy.

    """

    cls = ctx.cls
    info = cls.info

    name = cls.name
    bases = info.bases

    # Get the decorator arguments
    args_dict = {a: _get_decorator_bool_argument(ctx, a, d)
                 for (a, d) in ClassyArgs._field_defaults.items()}
    args = ClassyArgs(**args_dict)

    # Then the fields
    fields = {f.name: f for f in _gather_attributes(cls)}

    # Finally, annotate the thing
    classy = ClassyInfo(fields, args, is_root=True)
    _munge_dataclassy(ctx, classy)


def _check_dataclassy(ctx: ClassDefContext) -> None:
    """
    If this class has a @dataclassy-decorated class in one of it's base-classes
    then we need to look at all the fields in all dataclassy parent classes,
    and we need to get the decorator-args for the root-dataclassy type in the
    hierarchy and combine all that together to figure out how to annotate this
    one.
    """
    cls = ctx.cls
    info = cls.info

    name = cls.name

    # gather metadata from all parent classes in MRO
    all_metas = (t.metadata.get(_meta_key) for t in reversed(info.mro))
    parents = [ClassyInfo.deserialize(info, t, ctx.api)
               for t in all_metas if t is not None]

    # There are no dataclassy classes, so we're done
    if not parents:
        return

    # Figure out which of the parents is the root, we need this to get
    # decorator args
    args = [t for t in parents if t.is_root][0].args

    # Collect together all fields from parents, and finally from this class
    order: List[ClassyField] = []
    for t in parents:
        order.extend(t.fields.values())
    order.extend(_gather_attributes(cls))

    # Now partition the fields so we can put those with default values at the
    # end of the list
    order, defaults = partition(lambda f: f.has_default, order)
    order.extend(defaults)

    fields = {f.name: f for f in order}

    # Finally, we can annotate the current class
    classy = ClassyInfo(fields, args, is_root=False)
    _munge_dataclassy(ctx, classy)


class DataclassyPlugin(Plugin):
    _decorators = {
        'dataclassy.decorator.dataclass',
    }

    def get_class_decorator_hook(self, fullname: str) -> ClassDefCallback:
        if fullname not in self._decorators:
            return None
        return _make_dataclassy

    def get_base_class_hook(self, fullname: str) -> ClassDefCallback:
        return _check_dataclassy


def plugin(version: str):
    return DataclassyPlugin
