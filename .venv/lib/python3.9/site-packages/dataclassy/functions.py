"""
 Copyright (C) 2020, 2021 biqqles.
 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at http://mozilla.org/MPL/2.0/.

 This file defines functions which operate on data classes.
"""
from typing import Any, Callable, Dict, Tuple, Type, Union

from .dataclass import DataClassMeta, DataClass, Internal


def is_dataclass(obj: Any) -> bool:
    """Return True if the given object is a data class as implemented in this package, otherwise False."""
    return isinstance(obj, DataClassMeta) or is_dataclass_instance(obj)


def is_dataclass_instance(obj: Any) -> bool:
    """Return True if the given object is an instance of a data class, otherwise False."""
    return isinstance(type(obj), DataClassMeta)


def fields(dataclass: Union[DataClass, Type[DataClass]], internals=False) -> Dict[str, Type]:
    """Return a dict of `dataclass`'s fields and their types. `internals` selects whether to include internal fields.
    `dataclass` can be either a data class or an instance of a data class. A field is defined as a class-level variable
    with a type annotation."""
    assert is_dataclass(dataclass)
    return _filter_annotations(dataclass.__annotations__, internals)


def values(dataclass: DataClass, internals=False) -> Dict[str, Any]:
    """Return a dict of `dataclass`'s fields and their values. `internals` selects whether to include internal fields.
    `dataclass` must be an instance of a data class. A field is defined as a class-level variable with a type
    annotation."""
    assert is_dataclass_instance(dataclass)
    return {f: getattr(dataclass, f) for f in fields(dataclass, internals)}


def as_dict(dataclass: DataClass, dict_factory=dict) -> Dict[str, Any]:
    """Recursively create a dict of a dataclass instance's fields and their values.
    This function is recursively called on data classes, named tuples and iterables."""
    assert is_dataclass_instance(dataclass)
    return _recurse_structure(dataclass, dict_factory)


def as_tuple(dataclass: DataClass) -> Tuple:
    """Recursively create a tuple of the values of a dataclass instance's fields, in definition order.
    This function is recursively called on data classes, named tuples and iterables."""
    assert is_dataclass_instance(dataclass)
    return _recurse_structure(dataclass, lambda k_v: tuple(v for k, v in k_v))


def replace(dataclass: DataClass, **changes) -> DataClass:
    """Return a new copy of `dataclass` with field values replaced as specified in `changes`."""
    return type(dataclass)(**dict(values(dataclass, internals=True), **changes))


def _filter_annotations(annotations: Dict[str, Type], internals: bool) -> Dict[str, Type]:
    """Filter an annotations dict for to remove or keep internal fields."""
    return annotations if internals else {f: a for f, a in annotations.items()
                                          if not f.startswith('_') and not Internal.is_hinted(a)}


def _recurse_structure(var: Any, iter_proc: Callable) -> Any:
    """Recursively convert an arbitrarily nested structure beginning at `var`, copying and processing any iterables
    encountered with `iter_proc`."""
    if is_dataclass(var):
        var = values(var, internals=True)
    if hasattr(var, '_asdict'):  # handle named tuples
        # noinspection PyCallingNonCallable, PyProtectedMember
        var = var._asdict()
    if isinstance(var, dict):
        return iter_proc((_recurse_structure(k, iter_proc), _recurse_structure(v, iter_proc)) for k, v in var.items())
    if isinstance(var, (list, tuple)):
        return type(var)(_recurse_structure(e, iter_proc) for e in var)
    return var
