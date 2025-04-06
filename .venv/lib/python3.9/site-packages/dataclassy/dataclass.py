"""
 Copyright (C) 2020, 2021 biqqles.
 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at http://mozilla.org/MPL/2.0/.

 This file contains the internal mechanism that makes data classes
 work, as well as functions which operate on them.
"""
from types import FunctionType as Function
from typing import Any, Callable, Dict, List, Type, TypeVar, Union, cast
from reprlib import recursive_repr

DataClass = Any  # type hint representing a generic data class instance


class Hint(type):
    """Metaclass for a type hint "wrapper". Wraps the actual type of a field to convey information about how it is
    intended to be used, much like typing.ClassVar. Usage is like Hint[some_type].
    This is a metaclass because __class_getitem__ is not recognised in Python 3.6."""
    Wrapped = TypeVar('Wrapped')

    def __getitem__(cls, item: Wrapped) -> Union['Hint', Wrapped]:
        """Create a new Union of the wrapper and the wrapped type. Union is smart enough to flatten nested
        unions automatically."""
        return Union[cls, item]

    def is_hinted(cls, hint: Union[Type, str]) -> bool:
        """Check whether a type hint represents this Hint."""
        return ((hasattr(hint, '__args__') and cls in (hint.__args__ or [])) or
                (type(hint) is str and f'{cls.__name__}[' in hint))


class Internal(metaclass=Hint):
    """Marks that a field is internal to the class and so should not in a repr."""


class Hashed(metaclass=Hint):
    """Marks that a field should be included in the generated __hash__."""


class Factory:
    """This class takes a zero-argument callable. When a Factory instance is set as the default value of a field, this
    callable is executed and the instance variable set to the result."""
    Produces = TypeVar('Produces')

    def __init__(self, producer: Callable[[], Produces]):
        """The generated __init__ checks for the existence of a `copy` method to determine whether a default value
        should be copied upon class instantiation. This is because the built-in mutable collections have a method like
        this. This class (ab)uses this behaviour to elegantly implement the factory."""
        self.copy = producer


def factory(producer: Callable[[], Factory.Produces]) -> Factory.Produces:
    """Takes a zero-argument callable and creates a Factory that executes this callable to generate a default value for
    the field at class initialisation time. Casts the resulting Factory to keep mypy happy."""
    return cast(Factory.Produces, Factory(producer))


class DataClassMeta(type):
    """The metaclass that implements data class behaviour."""
    DEFAULT_OPTIONS = dict(init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False,
                           hide_internals=True, iter=False, kwargs=False, slots=False)

    def __new__(mcs, name, bases, dict_, **kwargs):
        """Create a new data class."""

        # delete what may become stale references so that Python creates new ones

        dict_.pop('__dict__', None)
        dict_ = {f: v for f, v in dict_.items() if type(v).__name__ != 'member_descriptor'}

        # collect functions, annotations, defaults, slots and options from this class' ancestors, in definition order

        all_annotations = {}
        all_defaults = {}
        all_slots = set()
        options = dict(mcs.DEFAULT_OPTIONS)

        # record all functions defined by the user up through the inheritance chain
        all_attrs = {a for b in bases for a in dir(b) if is_user_func(getattr(b, a, None))} | dict_.keys()

        dataclass_bases = [vars(b) for b in bases if isinstance(b, mcs)]
        for b in dataclass_bases + [dict_]:
            all_annotations.update(b.get('__annotations__', {}))
            all_defaults.update(b.get('__defaults__', {}))
            all_slots.update(b.get('__slots__', set()))
            options.update(b.get('__dataclass__', {}))

        post_init = '__post_init__' in all_attrs

        # update options and defaults for *this* class

        options.update(kwargs)
        all_defaults.update({f: v for f, v in dict_.items() if f in all_annotations})

        # store defaults, annotations and decorator options for future subclasses

        dict_['__defaults__'] = all_defaults
        dict_['__annotations__'] = all_annotations
        dict_['__dataclass__'] = options

        # create and apply generated methods and attributes

        if options['slots']:
            # if the slots option is added, add __slots__. Values with default values must only be present in slots,
            # not dict, otherwise Python will interpret them as read only
            for d in all_annotations.keys() & dict_.keys():
                del dict_[d]
            dict_.setdefault('__slots__', tuple(all_annotations.keys() - all_slots))
        elif '__slots__' in dict_:
            # if the slots option gets removed, remove __slots__
            del dict_['__slots__']

        if options['init'] and all_annotations and '__init__' not in all_attrs:
            dict_.setdefault('__init__', generate_init(all_annotations, all_defaults, options, post_init))

        if options['repr']:
            '__repr__' in all_attrs or dict_.setdefault('__repr__', recursive_repr()(__repr__))

        if options['eq']:
            '__eq__' in all_attrs or dict_.setdefault('__eq__', __eq__)

        if options['iter']:
            '__iter__' in all_attrs or dict_.setdefault('__iter__', __iter__)

        if options['frozen']:
            '__delattr__' in all_attrs or dict_.setdefault('__delattr__', __setattr__)
            '__setattr__' in all_attrs or dict_.setdefault('__setattr__', __setattr__)

        if options['order']:
            '__lt__' in all_attrs or dict_.setdefault('__lt__', __lt__)

        if (options['eq'] and options['frozen']) or options['unsafe_hash']:
            '__hash__' in all_attrs or dict_.setdefault('__hash__', generate_hash(all_annotations))

        return super().__new__(mcs, name, bases, dict_)

    # noinspection PyMissingConstructor,PyUnresolvedReferences,PyTypeChecker,PyUnusedLocal
    def __init__(cls, *args, **kwargs):
        if cls.__dataclass__['eq'] and cls.__dataclass__['order']:
            from functools import total_ordering
            total_ordering(cls)

        # determine a static expression for an instance's fields as a tuple, then evaluate this to create a property
        # allowing efficient representation for internal methods
        internals = not cls.__dataclass__['hide_internals']
        tuple_expr = ' '.join(f'self.{f},' for f in fields(cls, internals))
        cls.__tuple__ = property(eval(f'lambda self: ({tuple_expr})'))


def eval_function(name: str, lines: List[str], annotations: Dict, locals_: Dict, globals_: Dict) -> Function:
    """Evaluate a function definition, returning the resulting object."""
    exec('\n\t'.join(lines), globals_, locals_)
    function = locals_.pop(name)
    function.__annotations__ = annotations
    function.__dataclass__ = True  # add a marker showing this function was generated by dataclassy
    return function


def is_user_func(obj: Any, object_methods=frozenset(vars(object).values())) -> bool:
    """Given an object, returns true if it is a function explicitly defined by the user (i.e. not generated by
    dataclassy and not a wrapper/descriptor). Otherwise, returns False.
    The unusual check against object_methods is because PyPy returns True for methods on object (unlike CPython)."""
    return type(obj) is Function and obj not in object_methods and not hasattr(obj, '__dataclass__')


def generate_init(annotations: Dict, defaults: Dict, options: Dict, user_init: bool) -> Function:
    """Generate and return an __init__ method for a data class. This method has as parameters all fields of the data
    class. When the data class is initialised, arguments to this function are applied to the fields of the new instance.
    A user-defined __init__, if present, must be aliased to avoid conflicting."""
    arguments = [a for a in annotations if a not in defaults]
    default_arguments = [f'{a}={a}' for a in defaults]
    args = ['*args'] if user_init else []
    kwargs = ['**kwargs'] if user_init or options['kwargs'] else []

    parameters = ', '.join(arguments + default_arguments + args + kwargs)

    # surprisingly, given global lookups are slow, using them is the fastest way to compare a field to its default
    # the alternatives are to look up on self (which wouldn't work when slots=True) or look up self.__defaults__
    default_names = {f'default_{n}': v for n, v in defaults.items()}

    # determine what to do with arguments before assignment. If the argument matches a mutable default, make a copy
    references = {n: f'{n}.copy() if {n} is default_{n} else {n}' if n in defaults and hasattr(defaults[n], 'copy')
                  else n for n in annotations}

    # if the class is frozen, use the necessary but far slower object.__setattr__
    assignments = [f'object.__setattr__(self, {n!r}, {r})' if options['frozen']
                   else f'self.{n} = {r}' for n, r in references.items()]

    # generate the function
    lines = [f'def __init__(self, {parameters}):',
             *assignments,
             'self.__post_init__(*args, **kwargs)' if user_init else '']

    return eval_function('__init__', lines, annotations, defaults, default_names)


def generate_hash(annotations: Dict[str, Type]) -> Function:
    """Generate a __hash__ method for a data class. The hashed value consists of a tuple of the instance's type
    followed by any fields marked as "Hashed"."""
    hash_of = ', '.join(['self.__class__', *(f'self.{f}' for f, h in annotations.items() if Hashed.is_hinted(h))])
    return eval_function('__hash__', ['def __hash__(self):',
                                      f'return hash(({hash_of}))'], dict(self=DataClass), {}, {})


# generic method implementations common to all data classes
from .functions import values, fields


def __eq__(self: DataClass, other: DataClass):
    return type(self) is type(other) and self.__tuple__ == other.__tuple__


def __lt__(self: DataClass, other: DataClass):
    if isinstance(other, type(self)):
        return self.__tuple__ < other.__tuple__
    return NotImplemented


def __iter__(self):
    return iter(self.__tuple__)


def __repr__(self):
    show_internals = not self.__dataclass__['hide_internals']
    field_values = ', '.join(f'{f}={v!r}' for f, v in values(self, show_internals).items())
    return f'{type(self).__name__}({field_values})'


# noinspection PyUnusedLocal
def __setattr__(self, *args):
    raise AttributeError('Frozen class')
